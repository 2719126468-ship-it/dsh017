#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create and restore a private DSH-017 data archive without overwriting live data."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MAX_FILES = 2048
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class BackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _integrity_check(path: Path) -> None:
    if not _regular_file(path):
        raise BackupError("database snapshot is missing or not a regular file")
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise BackupError("SQLite integrity_check failed")
    except sqlite3.DatabaseError as exc:
        raise BackupError("SQLite database is invalid") from exc


def _resolve_sources(args):
    data_dir = Path(args.data_dir or os.environ.get("DSH017_DATA_DIR", ROOT / "data")).expanduser().resolve()
    db_path = Path(args.db_path or os.environ.get("DSH017_DB_PATH", data_dir / "bili_data.db")).expanduser().absolute()
    preset_dir = Path(args.preset_dir or os.environ.get("DSH017_PRESET_DIR", ROOT / "presets")).expanduser().absolute()
    backup_dir = Path(args.backup_dir or os.environ.get("DSH017_BACKUP_DIR", data_dir / "backup")).expanduser().absolute()
    return data_dir, db_path, preset_dir, backup_dir


def _backup(args) -> Path:
    data_dir, db_path, preset_dir, backup_dir = _resolve_sources(args)
    if not _regular_file(db_path):
        raise BackupError("database file not found or is a symlink: " + str(db_path))
    if preset_dir.is_symlink():
        raise BackupError("preset directory must not be a symlink")
    backup_dir.mkdir(parents=True, exist_ok=True)
    if backup_dir.is_symlink():
        raise BackupError("backup directory must not be a symlink")

    with tempfile.TemporaryDirectory(prefix="dsh017-backup-") as temp_name:
        temp = Path(temp_name)
        db_snapshot = temp / "database.sqlite3"
        try:
            with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=15) as source:
                with sqlite3.connect(db_snapshot) as target:
                    source.backup(target)
            _integrity_check(db_snapshot)
        except sqlite3.DatabaseError as exc:
            raise BackupError("could not create a consistent SQLite snapshot") from exc

        payloads = {"database.sqlite3": db_snapshot}
        provider_config = data_dir / "providers.json"
        if provider_config.exists():
            if not _regular_file(provider_config):
                raise BackupError("providers.json is not a regular file")
            try:
                parsed = json.loads(provider_config.read_text(encoding="utf-8"))
                if not isinstance(parsed, list):
                    raise ValueError("provider config must be an array")
            except (OSError, UnicodeError, ValueError) as exc:
                raise BackupError("providers.json is invalid") from exc
            payloads["providers.json"] = provider_config

        if preset_dir.exists():
            if not preset_dir.is_dir():
                raise BackupError("preset path is not a directory")
            for item in sorted(preset_dir.iterdir(), key=lambda p: p.name):
                if item.suffix != ".txt":
                    continue
                if not _regular_file(item):
                    raise BackupError("preset is not a regular file: " + item.name)
                if item.name in ("", ".", "..") or "/" in item.name or "\\" in item.name:
                    raise BackupError("unsafe preset filename")
                try:
                    item.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise BackupError("preset is not valid UTF-8: " + item.name) from exc
                payloads["presets/" + item.name] = item

        if len(payloads) > MAX_FILES:
            raise BackupError("too many backup files")
        manifest_files = []
        total_size = 0
        for name, path in sorted(payloads.items()):
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise BackupError("file exceeds backup size limit: " + name)
            total_size += size
            manifest_files.append({"path": name, "size": size, "sha256": _sha256(path)})
        if total_size > MAX_TOTAL_BYTES:
            raise BackupError("backup exceeds total size limit")

        manifest = {
            "format": "dsh017-data-backup",
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": manifest_files,
            "excluded": [
                "provider_secrets.json",
                "auth_token",
                "admin_token",
                "Android Keystore entries",
                "runtime environment secrets",
            ],
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archive_path = backup_dir / ("dsh017-backup-" + stamp + ".tar.gz")
        temp_archive = backup_dir / (archive_path.name + ".tmp")
        try:
            with tarfile.open(temp_archive, "w:gz") as archive:
                info = tarfile.TarInfo("manifest.json")
                info.size = len(manifest_bytes)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(manifest_bytes))
                for name, path in sorted(payloads.items()):
                    archive.add(path, arcname=name, recursive=False)
            os.chmod(temp_archive, 0o600)
            os.replace(temp_archive, archive_path)
        finally:
            if temp_archive.exists():
                temp_archive.unlink()
        return archive_path


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        return False
    if name in ("manifest.json", "database.sqlite3", "providers.json"):
        return True
    return len(path.parts) == 2 and path.parts[0] == "presets" and path.name.endswith(".txt")


def _check_empty_destination(path: Path, label: str) -> None:
    if path.is_symlink():
        raise BackupError(label + " destination must not be a symlink")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise BackupError(label + " destination must be a new or empty directory")


def _restore(args) -> tuple[Path, Path]:
    archive_path = Path(args.archive).expanduser().absolute()
    data_dir = Path(args.data_dir).expanduser().absolute()
    preset_dir = Path(args.preset_dir).expanduser().absolute()
    if not _regular_file(archive_path):
        raise BackupError("backup archive not found or is not a regular file")
    data_resolved = data_dir.resolve()
    preset_resolved = preset_dir.resolve()
    if data_resolved == preset_resolved or data_resolved in preset_resolved.parents or preset_resolved in data_resolved.parents:
        raise BackupError("data and preset destinations must be separate directories")
    _check_empty_destination(data_dir, "data")
    _check_empty_destination(preset_dir, "preset")

    with tempfile.TemporaryDirectory(prefix="dsh017-restore-") as temp_name:
        stage = Path(temp_name)
        staged_data = stage / "data"
        staged_presets = stage / "presets"
        staged_data.mkdir()
        staged_presets.mkdir()
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                if len(members) < 2 or len(members) > MAX_FILES + 1:
                    raise BackupError("invalid archive file count")
                seen = set()
                total_size = 0
                for member in members:
                    if not member.isfile() or not _safe_member_name(member.name):
                        raise BackupError("archive contains an unsafe member")
                    if member.name in seen:
                        raise BackupError("archive contains duplicate paths")
                    seen.add(member.name)
                    if member.size < 0 or member.size > MAX_FILE_BYTES:
                        raise BackupError("archive member exceeds size limit")
                    total_size += member.size
                if total_size > MAX_TOTAL_BYTES:
                    raise BackupError("archive exceeds total size limit")

                manifest_stream = archive.extractfile("manifest.json")
                if manifest_stream is None:
                    raise BackupError("manifest.json is missing")
                manifest = json.loads(manifest_stream.read(1024 * 1024 + 1).decode("utf-8"))
                if not isinstance(manifest, dict) or manifest.get("format") != "dsh017-data-backup" or manifest.get("version") != 1:
                    raise BackupError("unsupported backup format")
                listed = manifest.get("files")
                if not isinstance(listed, list):
                    raise BackupError("backup manifest is invalid")
                expected = {entry.get("path"): entry for entry in listed if isinstance(entry, dict)}
                if len(expected) != len(listed) or set(expected) != (seen - {"manifest.json"}):
                    raise BackupError("archive contents do not match the manifest")

                for name, entry in expected.items():
                    member = archive.getmember(name)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise BackupError("could not read archive member: " + name)
                    destination = staged_data / name if not name.startswith("presets/") else staged_presets / name.split("/", 1)[1]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    copied = 0
                    with destination.open("xb") as output:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            copied += len(chunk)
                            if copied > member.size or copied > MAX_FILE_BYTES:
                                raise BackupError("archive member expanded beyond its declared size")
                            digest.update(chunk)
                            output.write(chunk)
                    if copied != member.size or copied != entry.get("size") or digest.hexdigest() != entry.get("sha256"):
                        raise BackupError("backup file integrity mismatch: " + name)

            database = staged_data / "database.sqlite3"
            _integrity_check(database)
            provider_config = staged_data / "providers.json"
            if provider_config.exists():
                parsed = json.loads(provider_config.read_text(encoding="utf-8"))
                if not isinstance(parsed, list):
                    raise BackupError("provider metadata is invalid")
            for preset in staged_presets.iterdir():
                preset.read_text(encoding="utf-8")

            data_dir.mkdir(parents=True, exist_ok=True)
            preset_dir.mkdir(parents=True, exist_ok=True)
            copied = []
            try:
                for item in staged_data.iterdir():
                    # The archive uses a stable internal filename, but the app's
                    # default database contract is data/bili_data.db.
                    target_name = "bili_data.db" if item.name == "database.sqlite3" else item.name
                    target = data_dir / target_name
                    with item.open("rb") as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    os.chmod(target, 0o600)
                    copied.append(target)
                for item in staged_presets.iterdir():
                    target = preset_dir / item.name
                    with item.open("rb") as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    os.chmod(target, 0o600)
                    copied.append(target)
            except Exception:
                for target in reversed(copied):
                    try:
                        target.unlink()
                    except OSError:
                        pass
                raise
        except (tarfile.TarError, OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, BackupError):
                raise
            raise BackupError("backup archive is corrupt or unreadable") from exc

    return data_dir, preset_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup", help="create a consistent local backup archive")
    backup.add_argument("--data-dir")
    backup.add_argument("--db-path")
    backup.add_argument("--preset-dir")
    backup.add_argument("--backup-dir")
    restore = sub.add_parser("restore", help="restore only into new or empty directories")
    restore.add_argument("--archive", required=True)
    restore.add_argument("--data-dir", required=True)
    restore.add_argument("--preset-dir", required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup":
            print(_backup(args))
        else:
            data_dir, preset_dir = _restore(args)
            print("Restored data to: " + str(data_dir))
            print("Restored presets to: " + str(preset_dir))
            print("Provider API keys and auth tokens were intentionally not restored.")
        return 0
    except (BackupError, OSError, tarfile.TarError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
