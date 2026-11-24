#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export an installed legacy DSH-017 Debug app through read-only ADB access.

The helper is intended for the published v0.1.2 package
com.dsh017.android.debug, which predates the in-app SAF export action.
It never installs, uninstalls, stops, or writes files on the Android device.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BACKUP_TOOL = ROOT / "scripts" / "data_backup.py"
DEFAULT_PACKAGE = "com.dsh017.android.debug"
PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")

MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2052
MAX_TRANSFER_BYTES = 520 * 1024 * 1024
_DB_SIDE_FILES = {
    "bili_data.db",
    "bili_data.db-wal",
    "bili_data.db-shm",
    "bili_data.db-journal",
    "providers.json",
}

# run-as starts in the app's private data directory. Prefixing every path with
# "./" prevents a user preset beginning with "-" from becoming a tar option.
_REMOTE_EXPORT_SCRIPT = (
    "cd files/dsh017 || exit 20; "
    "[ -f bili_data.db ] || exit 21; "
    "set --; "
    "for item in ./bili_data.db ./bili_data.db-wal ./bili_data.db-shm "
    "./bili_data.db-journal ./providers.json ./presets/*.txt; do "
    "[ -f \"$item\" ] && set -- \"$@\" \"$item\"; "
    "done; "
    "[ \"$#\" -gt 0 ] || exit 22; "
    "tar -cf - \"$@\""
)


class LegacyExportError(RuntimeError):
    """A safe legacy export could not be completed."""


def _adb_command(adb: str, serial: str | None, *parts: str) -> list[str]:
    command = [adb]
    if serial:
        command.extend(["-s", serial])
    command.extend(parts)
    return command


def _run_capture(adb: str, serial: str | None, *parts: str, timeout: int = 30):
    try:
        return subprocess.run(
            _adb_command(adb, serial, *parts),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LegacyExportError(
            "找不到 adb。请安装 Android platform-tools，或通过 --adb 指定 adb 路径。"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise LegacyExportError("ADB 命令超时；设备可能未响应。") from exc


def _select_device(adb: str, serial: str | None) -> str:
    result = _run_capture(adb, None, "devices", "-l")
    if result.returncode != 0:
        raise LegacyExportError("无法读取 ADB 设备列表：" + result.stderr.strip())

    devices: dict[str, str] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] != "List":
            devices[fields[0]] = fields[1]

    if serial:
        state = devices.get(serial)
        if state != "device":
            raise LegacyExportError(
                "指定设备未处于已授权的 device 状态：" + serial + " (" + str(state or "not found") + ")"
            )
        return serial

    ready = [device for device, state in devices.items() if state == "device"]
    if len(ready) != 1:
        if not ready:
            detail = ", ".join(device + "=" + state for device, state in devices.items()) or "未发现设备"
            raise LegacyExportError("没有已授权的 ADB 设备：" + detail)
        raise LegacyExportError(
            "检测到多个已授权设备，请使用 --serial 指定一个：" + ", ".join(ready)
        )
    return ready[0]


def _verify_legacy_package(adb: str, serial: str, package: str) -> None:
    installed = _run_capture(adb, serial, "shell", "pm", "path", package)
    if installed.returncode != 0 or "package:" not in installed.stdout:
        raise LegacyExportError("设备上没有安装目标应用：" + package)

    run_as = _run_capture(adb, serial, "shell", "run-as", package, "id")
    if run_as.returncode != 0:
        raise LegacyExportError(
            "run-as 无法访问该应用。此导出方式仅适用于可调试的旧 Debug APK；"
            "不要卸载旧应用，也不要尝试读取其他应用的数据。"
        )


def _assert_app_stopped(adb: str, serial: str, package: str) -> None:
    """Require the app process to be stopped so SQLite files cannot change mid-copy."""
    pid = _run_capture(adb, serial, "shell", "pidof", package)
    if pid.returncode == 0 and pid.stdout.strip():
        raise LegacyExportError(
            "旧版 DSH-017 仍在运行。请先在设备上正常退出应用，再重新导出；脚本不会替你停止应用。"
        )
    if pid.returncode == 1 and not pid.stdout.strip():
        return

    # Some older Android shell images lack pidof. Fall back to ps, and fail
    # closed if process state still cannot be determined.
    processes = _run_capture(adb, serial, "shell", "ps", "-A")
    if processes.returncode != 0:
        raise LegacyExportError("无法确认旧版应用是否已停止；为避免复制正在变化的 SQLite 文件，已中止。")
    for line in processes.stdout.splitlines():
        columns = line.split()
        if any(column == package or column.startswith(package + ":") for column in columns):
            raise LegacyExportError(
                "旧版 DSH-017 仍在运行。请先在设备上正常退出应用，再重新导出；脚本不会替你停止应用。"
            )


def _normalise_member_name(name: str) -> str | None:
    if name.startswith("./"):
        name = name[2:]
    if not name or name.startswith("/") or "\\" in name or "\x00" in name:
        return None

    path = PurePosixPath(name)
    if (
        path.as_posix() != name
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        return None

    if name in _DB_SIDE_FILES:
        return name
    if len(path.parts) == 2 and path.parts[0] == "presets" and path.parts[1].endswith(".txt"):
        return name
    return None


def _extract_legacy_tar(archive_path: Path, data_dir: Path) -> None:
    """Extract only the documented, non-secret legacy data files."""
    if data_dir.exists() and any(data_dir.iterdir()):
        raise LegacyExportError("临时导出目录必须为空；拒绝覆盖已有文件。")
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "presets").mkdir(exist_ok=True)

    try:
        with tarfile.open(archive_path, "r:*") as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_ARCHIVE_MEMBERS:
                raise LegacyExportError("设备归档文件数量无效。")

            seen: set[str] = set()
            total_size = 0
            normalized: list[tuple[tarfile.TarInfo, str]] = []
            for member in members:
                if not member.isfile():
                    raise LegacyExportError("设备归档包含非普通文件，已拒绝导出。")
                name = _normalise_member_name(member.name)
                if name is None:
                    raise LegacyExportError("设备归档包含未允许的路径或文件：" + member.name)
                if name in seen:
                    raise LegacyExportError("设备归档包含重复文件：" + name)
                seen.add(name)
                if member.size < 0 or member.size > MAX_FILE_BYTES:
                    raise LegacyExportError("设备文件超过单文件大小限制：" + name)
                total_size += member.size
                if total_size > MAX_TOTAL_BYTES:
                    raise LegacyExportError("设备数据超过 512 MiB 总大小限制。")
                normalized.append((member, name))

            if "bili_data.db" not in seen:
                raise LegacyExportError("旧版应用数据目录中没有 bili_data.db。")

            for member, name in normalized:
                target = data_dir.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = archive.extractfile(member)
                if stream is None:
                    raise LegacyExportError("无法读取设备文件：" + name)
                copied = 0
                with target.open("xb") as output:
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > member.size or copied > MAX_FILE_BYTES:
                            raise LegacyExportError("设备文件超出归档声明大小：" + name)
                        output.write(chunk)
                if copied != member.size:
                    raise LegacyExportError("设备文件不完整：" + name)
                os.chmod(target, 0o600)
    except LegacyExportError:
        raise
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise LegacyExportError("设备导出数据损坏或无法读取。") from exc


def _stream_device_files(adb: str, serial: str, package: str, destination: Path) -> None:
    command = _adb_command(
        adb,
        serial,
        "exec-out",
        "run-as",
        package,
        "sh",
        "-c",
        _REMOTE_EXPORT_SCRIPT,
    )
    try:
        with destination.open("wb") as output:
            result = subprocess.run(
                command,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
    except FileNotFoundError as exc:
        raise LegacyExportError("找不到 adb；请安装 Android platform-tools。") from exc
    except subprocess.TimeoutExpired as exc:
        raise LegacyExportError("读取设备数据超时；没有修改设备上的文件。") from exc

    error = (result.stderr or b"").decode("utf-8", "replace").strip()
    if result.returncode != 0:
        raise LegacyExportError(
            "无法读取旧版应用数据（run-as/tar 失败，退出码 "
            + str(result.returncode)
            + "）："
            + (error or "请确认应用数据目录存在且设备已授权。")
        )

    size = destination.stat().st_size
    if size <= 0 or size > MAX_TRANSFER_BYTES:
        raise LegacyExportError("设备导出流为空或超过 520 MiB 安全上限。")


def _create_portable_backup(data_dir: Path, output_dir: Path) -> Path:
    if not BACKUP_TOOL.is_file():
        raise LegacyExportError("仓库内缺少 scripts/data_backup.py，无法生成标准备份。")
    if output_dir.is_symlink():
        raise LegacyExportError("备份输出目录不能是符号链接。")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise LegacyExportError("备份输出路径不是目录。")

    command = [
        sys.executable,
        str(BACKUP_TOOL),
        "backup",
        "--data-dir",
        str(data_dir),
        "--db-path",
        str(data_dir / "bili_data.db"),
        "--preset-dir",
        str(data_dir / "presets"),
        "--backup-dir",
        str(output_dir),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LegacyExportError("生成标准备份超时。") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "未知备份错误"
        raise LegacyExportError("标准备份校验失败：" + detail)

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise LegacyExportError("标准备份工具没有返回归档路径。")
    archive_path = Path(lines[-1]).expanduser()
    if not archive_path.is_absolute():
        archive_path = output_dir / archive_path
    if archive_path.is_symlink() or not archive_path.is_file():
        raise LegacyExportError("标准备份工具返回的归档不存在或不是普通文件。")
    if archive_path.parent.resolve() != output_dir.resolve():
        raise LegacyExportError("标准备份工具返回了输出目录之外的路径。")
    return archive_path


def export_legacy_data(
    *,
    adb: str = "adb",
    serial: str | None = None,
    package: str = DEFAULT_PACKAGE,
    output_dir: str | os.PathLike,
) -> Path:
    if not PACKAGE_RE.fullmatch(package):
        raise LegacyExportError("Android package 名称格式无效。")

    selected = _select_device(adb, serial)
    _verify_legacy_package(adb, selected, package)
    _assert_app_stopped(adb, selected, package)

    with tempfile.TemporaryDirectory(prefix="dsh017-legacy-adb-export-") as temp_name:
        temp = Path(temp_name)
        transfer = temp / "legacy-files.tar"
        data_dir = temp / "data"
        _stream_device_files(adb, selected, package, transfer)
        _extract_legacy_tar(transfer, data_dir)
        return _create_portable_backup(data_dir, Path(output_dir).expanduser().absolute())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="ADB device serial when more than one device is connected")
    parser.add_argument("--package", default=DEFAULT_PACKAGE, help="legacy debuggable Android package ID")
    parser.add_argument("--adb", default="adb", help="adb executable path")
    parser.add_argument("--output-dir", required=True, help="local directory for the portable backup archive")
    args = parser.parse_args()

    try:
        archive = export_legacy_data(
            adb=args.adb,
            serial=args.serial,
            package=args.package,
            output_dir=args.output_dir,
        )
    except (LegacyExportError, OSError, subprocess.SubprocessError, tarfile.TarError, EOFError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2

    print("Legacy Android data exported to: " + str(archive))
    print("The device was not modified. API keys, auth tokens and Android Keystore entries were excluded.")
    print("Keep the old app installed until the new Release app has imported and verified this archive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
