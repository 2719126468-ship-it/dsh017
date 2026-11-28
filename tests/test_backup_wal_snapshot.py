"""Regression coverage for SQLite WAL-aware backup snapshots.

The backup CLI must include committed transactions still present in the source
WAL file, without requiring the running application to checkpoint or close it.
"""
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "data_backup.py"


class BackupWalSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-backup-wal-")
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "source-data"
        self.preset_dir = self.root / "source-presets"
        self.backup_dir = self.root / "backups"
        self.data_dir.mkdir()
        self.preset_dir.mkdir()
        self.db_path = self.data_dir / "bili_data.db"

        # Keep a live WAL-mode connection open while the backup subprocess runs.
        # Disabling auto-checkpointing makes the committed rows remain in -wal.
        self.connection = sqlite3.connect(self.db_path)
        mode = self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if mode.lower() != "wal":
            self.connection.close()
            self.temp.cleanup()
            self.skipTest("SQLite WAL mode is unavailable in this environment")
        self.connection.execute("PRAGMA wal_autocheckpoint=0")
        self.connection.execute(
            "CREATE TABLE snapshot_probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.connection.execute(
            "INSERT INTO snapshot_probe(id, value) VALUES (1, 'before-wal-update')"
        )
        self.connection.commit()
        self.connection.execute(
            "UPDATE snapshot_probe SET value='committed-wal-update' WHERE id=1"
        )
        self.connection.execute(
            "INSERT INTO snapshot_probe(id, value) VALUES (2, 'committed-wal-insert')"
        )
        self.connection.commit()
        self.wal_path = Path(str(self.db_path) + "-wal")

    def tearDown(self):
        if getattr(self, "connection", None) is not None:
            self.connection.close()
        self.temp.cleanup()

    def test_backup_includes_committed_wal_transactions_without_checkpointing_source(self):
        self.assertTrue(self.wal_path.is_file(), "source WAL must remain present during backup")
        self.assertGreater(self.wal_path.stat().st_size, 32, "source WAL must contain frames")

        result = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "backup",
                "--data-dir",
                str(self.data_dir),
                "--db-path",
                str(self.db_path),
                "--preset-dir",
                str(self.preset_dir),
                "--backup-dir",
                str(self.backup_dir),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        archive_path = Path(result.stdout.strip())
        self.assertTrue(archive_path.is_file())
        snapshot_path = self.root / "snapshot.sqlite3"
        with tarfile.open(archive_path, "r:gz") as archive:
            names = set(archive.getnames())
            self.assertIn("database.sqlite3", names)
            self.assertNotIn("database.sqlite3-wal", names)
            member = archive.extractfile("database.sqlite3")
            self.assertIsNotNone(member)
            snapshot_path.write_bytes(member.read())

        with sqlite3.connect(snapshot_path) as snapshot:
            self.assertEqual(
                snapshot.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            rows = snapshot.execute(
                "SELECT id, value FROM snapshot_probe ORDER BY id"
            ).fetchall()

        self.assertEqual(
            rows,
            [
                (1, "committed-wal-update"),
                (2, "committed-wal-insert"),
            ],
        )
        # The backup is a standalone database snapshot; the running source
        # connection and its WAL are not modified by the backup operation.
        self.assertTrue(self.wal_path.is_file())
        self.assertGreater(self.wal_path.stat().st_size, 32)
        self.assertEqual(
            self.connection.execute(
                "SELECT value FROM snapshot_probe WHERE id=1"
            ).fetchone()[0],
            "committed-wal-update",
        )


if __name__ == "__main__":
    unittest.main()
