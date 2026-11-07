#!/usr/bin/env python3
"""Export the legacy debuggable Android app's private data via authorized ADB run-as.

This host-side compatibility path is needed for already-installed v0.1.2 APKs:
those APKs predate the in-app SAF export action and cannot be updated because
their CI-generated debug signing certificate was ephemeral.
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace

from data_backup import _backup

MAX_RAW_TAR_BYTES = 512 * 1024 * 1024
MAX_FILES = 2048
MAX_FILE_BYTES = 256 * 1024 * 1024
DEFAULT_PACKAGE = "com.dsh017.android.debug"


class LegacyExportError(RuntimeError):
    pass


def _adb_serial(adb: str, requested: str | None) -> str:
    result = subprocess.run(
        [adb, "devices", "-l"], capture_output=True, text=True,
        timeout=30, check=False,
    )
    if result.returncode != 0:
        raise LegacyExportError("adb devices failed: " + result.stderr[:300])
    devices = []
    for line in result.stdout.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 2 and columns[1] == "device":
            devices.append(columns[0])
    if requested:
        if requested not in devices:
            raise LegacyExportError("the requested ADB device is not connected and authorized")
        return requested
    if len(devices) != 1:
        raise LegacyExportError(
            "connect exactly one authorized Android device or pass --serial; found %d" % len(devices)
        )
    return devices[0]


def _safe_relative_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or path.as_posix() != name.rstrip("/")
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
        or path.parts[0] != "dsh017"
    ):
        raise LegacyExportError("legacy app archive contains an unsafe path")
    return path


def _extract_legacy_archive(stream, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    seen = set()
    total_size = 0
    count = 0
    try:
        with tarfile.open(fileobj=stream, mode="r:") as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_FILES + 1:
                raise LegacyExportError("legacy archive has an invalid file count")
            for member in members:
                relative = _safe_relative_path(member.name)
                if member.name in seen:
                    raise LegacyExportError("legacy archive contains duplicate paths")
                seen.add(member.name)
                if member.isdir():
                    target = destination.joinpath(*relative.parts[1:])
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise LegacyExportError("legacy archive contains a link or special file")
                count += 1
                if count > MAX_FILES or member.size < 0 or member.size > MAX_FILE_BYTES:
                    raise LegacyExportError("legacy archive member exceeds its file limit")
                total_size += member.size
                if total_size > MAX_RAW_TAR_BYTES:
                    raise LegacyExportError("legacy archive exceeds the total size limit")
                target = destination.joinpath(*relative.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise LegacyExportError("could not read legacy app data")
                with source, target.open("xb") as output:
                    remaining = member.size
                    while remaining:
                        chunk = source.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise LegacyExportError("truncated legacy archive member")
                        output.write(chunk)
                        remaining -= len(chunk)
            if "dsh017" not in seen and not any(x.startswith("dsh017/") for x in seen):
                raise LegacyExportError("legacy archive does not contain the DSH017 data directory")
    except (tarfile.TarError, OSError) as exc:
        if isinstance(exc, LegacyExportError):
            raise
        raise LegacyExportError("legacy ADB archive is corrupt or unreadable") from exc


def export_legacy(args) -> Path:
    adb = shutil.which(args.adb)
    if not adb:
        raise LegacyExportError("ADB executable was not found; install Android platform-tools")
    serial = _adb_serial(adb, args.serial)
    package = args.package
    if package != "com.dsh017.android.debug":
        raise LegacyExportError("unsupported DSH017 package ID")
    command = [
        adb, "-s", serial, "exec-out", "run-as", package,
        "sh", "-c", "tar -C files -cf - dsh017",
    ]
    with tempfile.TemporaryFile() as raw, tempfile.TemporaryDirectory(prefix="dsh017-legacy-") as temp_name:
        result = subprocess.run(
            command, stdout=raw, stderr=subprocess.PIPE, timeout=300, check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", "replace")[:300]
            raise LegacyExportError(
                "Android run-as export failed. The installed package must be debuggable "
                "and ADB-authorized. " + detail
            )
        raw.seek(0, os.SEEK_END)
        raw_size = raw.tell()
        if raw_size <= 0 or raw_size > MAX_RAW_TAR_BYTES:
            raise LegacyExportError("ADB returned an empty archive or exceeded 512 MB")
        raw.seek(0)
        data_dir = Path(temp_name) / "dsh017"
        _extract_legacy_archive(raw, data_dir)
        if not (data_dir / args.db_name).is_file():
            raise LegacyExportError(
                "legacy data export is missing the configured SQLite database: " + args.db_name
            )
        backup_dir = Path(args.backup_dir).expanduser().absolute()
        backup = _backup(SimpleNamespace(
            data_dir=str(data_dir),
            db_path=str(data_dir / args.db_name),
            preset_dir=str(data_dir / "presets"),
            backup_dir=str(backup_dir),
        ))
        return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="ADB serial; auto-detected when exactly one device is authorized")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--db-name", default="bili_data.db")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--backup-dir", required=True)
    args = parser.parse_args()
    if (
        not args.db_name or args.db_name in (".", "..")
        or Path(args.db_name).name != args.db_name
        or "/" in args.db_name or "\\" in args.db_name
        or args.db_name in ("providers.json", "provider_secrets.json", "auth_token", "admin_token", "backup")
    ):
        print("ERROR: unsafe database filename", file=sys.stderr)
        return 2
    try:
        print(export_legacy(args))
        return 0
    except (LegacyExportError, OSError, subprocess.SubprocessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
