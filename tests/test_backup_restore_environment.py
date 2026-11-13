"""Regression tests for backup/restore environment path resolution.

All paths are isolated under TemporaryDirectory; no live DSH-017 data is used.
"""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "data_backup.py"


class BackupRestoreEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-backup-env-")
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "source data"
        self.preset_dir = self.root / "source presets"
        self.backup_dir = self.root / "custom backups"
        self.db_name = "profile #1.sqlite3"
        self.db_path = self.data_dir / self.db_name
        self.data_dir.mkdir()
        self.preset_dir.mkdir()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("CREATE TABLE recovery_probe (value TEXT NOT NULL)")
            connection.execute("INSERT INTO recovery_probe VALUES (?)", ("env-path-ok",))
        (self.preset_dir / "Custom.txt").write_text("private preset", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, command, *args, env):
        return subprocess.run(
            [sys.executable, str(TOOL), command, *map(str, args)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_backup_uses_all_configured_environment_paths_and_restores_custom_db_name(self):
        env = os.environ.copy()
        env.update({
            "DSH017_DATA_DIR": str(self.data_dir),
            "DSH017_DB_PATH": str(self.db_path),
            "DSH017_PRESET_DIR": str(self.preset_dir),
            "DSH017_BACKUP_DIR": str(self.backup_dir),
        })
        result = self.run_tool("backup", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        archive_path = Path(result.stdout.strip())
        self.assertTrue(archive_path.is_file())
        self.assertEqual(archive_path.parent, self.backup_dir)
        self.assertEqual(archive_path.stat().st_mode & 0o777, 0o600)

        restored_data = self.root / "recovered data"
        restored_presets = self.root / "recovered presets"
        restore = self.run_tool(
            "restore",
            env=env,
            "--archive", archive_path,
            "--data-dir", restored_data,
            "--preset-dir", restored_presets,
            "--db-name", self.db_name,
        )
        self.assertEqual(restore.returncode, 0, restore.stdout + restore.stderr)

        restored_db = restored_data / self.db_name
        self.assertTrue(restored_db.is_file())
        with sqlite3.connect(restored_db) as connection:
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(
                connection.execute("SELECT value FROM recovery_probe").fetchone()[0],
                "env-path-ok",
            )
        self.assertEqual(
            (restored_presets / "Custom.txt").read_text(encoding="utf-8"),
            "private preset",
        )

    def test_environment_backup_never_exports_device_or_provider_secrets(self):
        (self.data_dir / "provider_secrets.json").write_text(
            '{"provider":"FAKE-SECRET-MUST-NOT-LEAK"}', encoding="utf-8"
        )
        (self.data_dir / "auth_token").write_text("A" * 48, encoding="utf-8")
        (self.data_dir / "admin_token").write_text("B" * 48, encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "DSH017_DATA_DIR": str(self.data_dir),
            "DSH017_DB_PATH": str(self.db_path),
            "DSH017_PRESET_DIR": str(self.preset_dir),
            "DSH017_BACKUP_DIR": str(self.backup_dir),
        })
        result = self.run_tool("backup", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        import tarfile
        import json

        archive_path = Path(result.stdout.strip())
        with tarfile.open(archive_path, "r:gz") as archive:
            names = set(archive.getnames())
            self.assertNotIn("provider_secrets.json", names)
            self.assertNotIn("auth_token", names)
            self.assertNotIn("admin_token", names)
            manifest = json.load(archive.extractfile("manifest.json"))
            self.assertIn("provider_secrets.json", manifest["excluded"])
            self.assertIn("auth_token", manifest["excluded"])
            self.assertIn("admin_token", manifest["excluded"])


if __name__ == "__main__":
    unittest.main()
