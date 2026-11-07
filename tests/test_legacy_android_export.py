import io
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest

from scripts.export_legacy_android_backup import (
    DEFAULT_PACKAGE,
    LegacyExportError,
    _extract_legacy_archive,
)


def make_tar(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as archive:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o700
                archive.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "/data/user/0/other-app"
                archive.addfile(info)
            else:
                info.size = len(data)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(data))
    buffer.seek(0)
    return buffer


class LegacyAndroidExportTests(unittest.TestCase):
    def test_default_legacy_package_is_v012_debug_application_id(self):
        self.assertEqual(DEFAULT_PACKAGE, "com.dsh017.android.debug")

    def test_extracts_only_app_private_dsh017_tree(self):
        with tempfile.TemporaryDirectory(prefix="dsh017-legacy-test-") as temp:
            root = Path(temp)
            db = root / "source.sqlite3"
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE chat_conversations (id TEXT PRIMARY KEY)")
                connection.execute("INSERT INTO chat_conversations VALUES ('chat-1')")
            payload = db.read_bytes()
            archive = make_tar([
                ("dsh017", b"", "dir"),
                ("dsh017/bili_data.db", payload, "file"),
                ("dsh017/presets", b"", "dir"),
                ("dsh017/presets/Writing.txt", b"private preset", "file"),
                ("dsh017/providers.json", b"[]", "file"),
            ])
            destination = root / "extracted"
            _extract_legacy_archive(archive, destination)
            with sqlite3.connect(destination / "bili_data.db") as connection:
                self.assertEqual(
                    connection.execute("SELECT id FROM chat_conversations").fetchone()[0],
                    "chat-1",
                )
            self.assertEqual(
                (destination / "presets" / "Writing.txt").read_text(encoding="utf-8"),
                "private preset",
            )
            self.assertEqual((destination / "providers.json").read_text(encoding="utf-8"), "[]")

    def test_rejects_path_traversal_and_never_writes_outside_destination(self):
        with tempfile.TemporaryDirectory(prefix="dsh017-legacy-traversal-") as temp:
            root = Path(temp)
            destination = root / "extracted"
            archive = make_tar([
                ("dsh017", b"", "dir"),
                ("dsh017/../../escaped.txt", b"do not write", "file"),
            ])
            with self.assertRaises(LegacyExportError):
                _extract_legacy_archive(archive, destination)
            self.assertFalse((root / "escaped.txt").exists())

    def test_rejects_symlinks_and_members_outside_private_tree(self):
        cases = [
            [("dsh017", b"", "dir"), ("dsh017/link", b"", "symlink")],
            [("dsh017", b"", "dir"), ("outside.txt", b"no", "file")],
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                with tempfile.TemporaryDirectory(prefix="dsh017-legacy-unsafe-") as temp:
                    with self.assertRaises(LegacyExportError):
                        _extract_legacy_archive(make_tar(entries), Path(temp) / "out")


if __name__ == "__main__":
    unittest.main()
