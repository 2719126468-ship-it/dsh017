import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
import io


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "data_backup.py"


def load_backup_module():
    spec = importlib.util.spec_from_file_location("dsh017_data_backup_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 26, 9, 8, 13, 123456, tzinfo=tz)


def create_source_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE search_history(q TEXT PRIMARY KEY, ts INTEGER NOT NULL);
            CREATE TABLE favorites(bvid TEXT PRIMARY KEY, title TEXT, cover TEXT, author TEXT, ts INTEGER NOT NULL);
            CREATE TABLE watch_progress(bvid TEXT NOT NULL, cid INTEGER NOT NULL, position REAL, duration REAL, ts INTEGER NOT NULL);
            CREATE TABLE workspace_projects(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
            CREATE TABLE workspace_files(id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_id INTEGER, workspace_id TEXT, content TEXT NOT NULL, version INTEGER NOT NULL, deleted_at INTEGER, updated_at INTEGER, kind TEXT NOT NULL);
            CREATE TABLE workspace_file_versions(id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, base_version INTEGER, created_at INTEGER);
            CREATE TABLE workspace_rules(id INTEGER PRIMARY KEY, file_pattern TEXT NOT NULL, operation TEXT NOT NULL, action TEXT NOT NULL, created_at INTEGER);
            CREATE TABLE chat_conversations(id TEXT PRIMARY KEY, title TEXT NOT NULL, messages TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
            INSERT INTO search_history VALUES('backup drill query', 100);
            INSERT INTO favorites VALUES('BVbackup001', 'saved favorite', '', 'test', 100);
            INSERT INTO watch_progress VALUES('BVbackup001', 11, 42.5, 120, 100);
            INSERT INTO workspace_projects VALUES('project-1', 'Backup project', '', 100, 100);
            INSERT INTO workspace_files VALUES(7, 'plan.md', NULL, 'project-1', 'keep this workspace data', 3, NULL, 100, 'file');
            INSERT INTO workspace_file_versions VALUES(9, 7, 'older revision', 'manual', 2, 90);
            INSERT INTO workspace_rules VALUES(1, '*.md', 'write', 'ask', 100);
            INSERT INTO chat_conversations VALUES('chat-1', 'backup chat', '[{"role":"user","content":"remember this"}]', 100, 100);
        """)


class IsolatedBackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-backup-drill-")
        self.root = Path(self.temp.name)
        self.source_data = self.root / "source-data"
        self.source_presets = self.root / "source-presets"
        self.backups = self.root / "backups"
        self.source_data.mkdir()
        self.source_presets.mkdir()
        create_source_database(self.source_data / "bili_data.db")
        (self.source_data / "providers.json").write_text(
            json.dumps([{"id": "test-provider", "base_url": "https://api.example.test/v1", "models": ["test-chat"]}]),
            encoding="utf-8",
        )
        (self.source_data / "provider_secrets.json").write_text(
            '{"test-provider":"DO_NOT_BACK_UP_FAKE_SECRET"}', encoding="utf-8"
        )
        (self.source_data / "auth_token").write_text("A" * 48, encoding="utf-8")
        (self.source_data / "admin_token").write_text("B" * 48, encoding="utf-8")
        (self.source_presets / "Writing.txt").write_text("private writing preset", encoding="utf-8")
        (self.source_presets / "Coding.txt").write_text("private coding preset", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(TOOL), *map(str, args)],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def create_backup(self):
        result = self.run_tool(
            "backup", "--data-dir", self.source_data, "--db-path",
            self.source_data / "bili_data.db", "--preset-dir",
            self.source_presets, "--backup-dir", self.backups,
        )
        archive_path = Path(result.stdout.strip())
        self.assertTrue(archive_path.is_file())
        self.assertEqual(archive_path.stat().st_mode & 0o777, 0o600)
        return archive_path

    def test_backup_restores_database_presets_and_provider_metadata_to_fresh_dirs(self):
        archive_path = self.create_backup()
        with tarfile.open(archive_path, "r:gz") as archive:
            names = set(archive.getnames())
            self.assertIn("database.sqlite3", names)
            self.assertIn("providers.json", names)
            self.assertIn("presets/Writing.txt", names)
            self.assertIn("presets/Coding.txt", names)
            self.assertNotIn("provider_secrets.json", names)
            self.assertNotIn("auth_token", names)
            self.assertNotIn("admin_token", names)
            manifest = json.load(archive.extractfile("manifest.json"))
            self.assertEqual(manifest["format"], "dsh017-data-backup")
            self.assertEqual(manifest["version"], 1)

        restored_data = self.root / "restored-data"
        restored_presets = self.root / "restored-presets"
        self.run_tool(
            "restore", "--archive", archive_path, "--data-dir",
            restored_data, "--preset-dir", restored_presets,
        )
        with sqlite3.connect(restored_data / "bili_data.db") as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT content FROM workspace_files WHERE id=7").fetchone()[0], "keep this workspace data")
            self.assertEqual(connection.execute("SELECT title FROM chat_conversations WHERE id='chat-1'").fetchone()[0], "backup chat")
            self.assertEqual(connection.execute("SELECT position FROM watch_progress WHERE bvid='BVbackup001'").fetchone()[0], 42.5)
            self.assertEqual(connection.execute("SELECT content FROM workspace_file_versions WHERE id=9").fetchone()[0], "older revision")
            self.assertEqual(connection.execute("SELECT action FROM workspace_rules WHERE id=1").fetchone()[0], "ask")
            self.assertEqual(connection.execute("SELECT title FROM favorites WHERE bvid='BVbackup001'").fetchone()[0], "saved favorite")
            self.assertEqual(connection.execute("SELECT q FROM search_history").fetchone()[0], "backup drill query")
        self.assertEqual((restored_presets / "Writing.txt").read_text(encoding="utf-8"), "private writing preset")
        self.assertEqual((restored_data / "providers.json").read_text(encoding="utf-8"), (self.source_data / "providers.json").read_text(encoding="utf-8"))
        self.assertFalse((restored_data / "provider_secrets.json").exists())
        self.assertFalse((restored_data / "auth_token").exists())
        self.assertFalse((restored_data / "admin_token").exists())
        self.assertFalse((restored_data / "database.sqlite3").exists())

    def test_backup_does_not_follow_predictable_temporary_symlink(self):
        self.backups.mkdir()
        archive_name = "dsh017-backup-20261126T090813123456Z.tar.gz"
        sentinel = self.root / "outside-sentinel.txt"
        sentinel.write_text("preserve this unrelated file", encoding="utf-8")
        predictable_temp = self.backups / (archive_name + ".tmp")
        try:
            os.symlink(sentinel, predictable_temp)
        except (NotImplementedError, OSError) as error:
            self.skipTest("symlinks are unavailable in this environment: " + str(error))

        module = load_backup_module()
        module.datetime = FrozenDateTime
        args = argparse.Namespace(
            data_dir=str(self.source_data),
            db_path=str(self.source_data / "bili_data.db"),
            preset_dir=str(self.source_presets),
            backup_dir=str(self.backups),
        )
        archive_path = module._backup(args)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve this unrelated file")
        self.assertTrue(predictable_temp.is_symlink())
        self.assertEqual(archive_path.name, archive_name)
        self.assertTrue(archive_path.is_file())
        self.assertFalse(archive_path.is_symlink())
        self.assertEqual(archive_path.stat().st_mode & 0o777, 0o600)
        with tarfile.open(archive_path, "r:gz") as archive:
            self.assertIn("database.sqlite3", archive.getnames())

    def test_backup_refuses_to_replace_existing_timestamped_archive(self):
        self.backups.mkdir()
        archive_path = self.backups / "dsh017-backup-20261126T090813123456Z.tar.gz"
        archive_path.write_text("keep the earlier backup", encoding="utf-8")

        module = load_backup_module()
        module.datetime = FrozenDateTime
        args = argparse.Namespace(
            data_dir=str(self.source_data),
            db_path=str(self.source_data / "bili_data.db"),
            preset_dir=str(self.source_presets),
            backup_dir=str(self.backups),
        )
        with self.assertRaisesRegex(module.BackupError, "refusing to overwrite"):
            module._backup(args)

        self.assertEqual(archive_path.read_text(encoding="utf-8"), "keep the earlier backup")
        self.assertEqual(list(self.backups.glob(".dsh017-backup-*.tmp")), [])

    def test_backup_handles_database_paths_with_uri_reserved_characters(self):
        source = self.source_data / "database # ? data.sqlite3"
        source.write_bytes((self.source_data / "bili_data.db").read_bytes())
        result = self.run_tool(
            "backup", "--data-dir", self.source_data, "--db-path",
            source, "--preset-dir", self.source_presets, "--backup-dir", self.backups,
        )
        archive_path = Path(result.stdout.strip())
        restored_data = self.root / "special-path-restored-data"
        restored_presets = self.root / "special-path-restored-presets"
        self.run_tool(
            "restore", "--archive", archive_path, "--data-dir",
            restored_data, "--preset-dir", restored_presets,
        )
        with sqlite3.connect(restored_data / "bili_data.db") as connection:
            self.assertEqual(
                connection.execute("SELECT title FROM chat_conversations WHERE id='chat-1'").fetchone()[0],
                "backup chat",
            )

    def test_restore_supports_custom_database_name_and_rejects_unsafe_names(self):
        archive_path = self.create_backup()
        restored_data = self.root / "custom-db-restored-data"
        restored_presets = self.root / "custom-db-restored-presets"
        self.run_tool(
            "restore", "--archive", archive_path, "--data-dir",
            restored_data, "--preset-dir", restored_presets,
            "--db-name", "profile-data.sqlite3",
        )
        restored_db = restored_data / "profile-data.sqlite3"
        self.assertTrue(restored_db.is_file())
        with sqlite3.connect(restored_db) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT title FROM chat_conversations WHERE id='chat-1'").fetchone()[0], "backup chat")

        invalid_names = ("../outside.db", "subdir/app.db", "providers.json", "auth_token", "backup", "")
        for index, invalid_name in enumerate(invalid_names):
            with self.subTest(db_name=invalid_name):
                target_data = self.root / ("invalid-db-name-%d" % index)
                target_presets = self.root / (target_data.name + "-presets")
                self.run_tool(
                    "restore", "--archive", archive_path, "--data-dir",
                    target_data, "--preset-dir", target_presets,
                    "--db-name", invalid_name, expected=2,
                )
                self.assertFalse(target_data.exists())
                self.assertFalse(target_presets.exists())
    def test_corrupt_archive_is_rejected_without_creating_destination(self):
        archive_path = self.create_backup()
        corrupt = self.root / "corrupt.tar.gz"
        with tarfile.open(archive_path, "r:gz") as source, tarfile.open(corrupt, "w:gz") as target:
            for member in source.getmembers():
                stream = source.extractfile(member)
                data = stream.read() if stream is not None else b""
                if member.name == "database.sqlite3":
                    data = b"not a database"
                info = tarfile.TarInfo(member.name)
                info.size = len(data)
                info.mode = 0o600
                target.addfile(info, io.BytesIO(data))

        restored_data = self.root / "must-stay-absent-data"
        restored_presets = self.root / "must-stay-absent-presets"
        self.run_tool(
            "restore", "--archive", corrupt, "--data-dir",
            restored_data, "--preset-dir", restored_presets, expected=2,
        )
        self.assertFalse(restored_data.exists())
        self.assertFalse(restored_presets.exists())

    def test_restore_refuses_to_overwrite_non_empty_destination(self):
        archive_path = self.create_backup()
        target_data = self.root / "existing-data"
        target_presets = self.root / "new-presets"
        target_data.mkdir()
        sentinel = target_data / "keep.txt"
        sentinel.write_text("existing user data", encoding="utf-8")
        self.run_tool(
            "restore", "--archive", archive_path, "--data-dir",
            target_data, "--preset-dir", target_presets, expected=2,
        )
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing user data")
        self.assertFalse(target_presets.exists())


if __name__ == "__main__":
    unittest.main()
