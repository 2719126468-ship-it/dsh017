import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "data_backup.py"


class BackupArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-archive-integrity-")
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "source-data"
        self.preset_dir = self.root / "source-presets"
        self.backup_dir = self.root / "backups"
        self.data_dir.mkdir()
        self.preset_dir.mkdir()

        with sqlite3.connect(self.data_dir / "bili_data.db") as connection:
            connection.execute("CREATE TABLE archive_probe (value TEXT NOT NULL)")
            connection.execute(
                "INSERT INTO archive_probe VALUES (?)",
                (os.urandom(64 * 1024).hex(),),
            )

    def tearDown(self):
        self.temp.cleanup()

    def create_archive(self):
        result = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "backup",
                "--data-dir",
                str(self.data_dir),
                "--db-path",
                str(self.data_dir / "bili_data.db"),
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
        return archive_path

    def rewrite_manifest(self, source, destination, mutate):
        with tarfile.open(source, "r:gz") as original, tarfile.open(destination, "w:gz") as rewritten:
            for member in original.getmembers():
                stream = original.extractfile(member)
                self.assertIsNotNone(stream, member.name)
                payload = stream.read()
                if member.name == "manifest.json":
                    manifest = json.loads(payload.decode("utf-8"))
                    mutate(manifest)
                    payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

                replacement = tarfile.TarInfo(member.name)
                replacement.size = len(payload)
                replacement.mode = 0o600
                rewritten.addfile(replacement, io.BytesIO(payload))

    def run_restore(self, archive, suffix):
        restored_data = self.root / (suffix + "-data")
        restored_presets = self.root / (suffix + "-presets")
        result = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "restore",
                "--archive",
                str(archive),
                "--data-dir",
                str(restored_data),
                "--preset-dir",
                str(restored_presets),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(restored_data.exists(), result.stdout + result.stderr)
        self.assertFalse(restored_presets.exists(), result.stdout + result.stderr)
        return result

    def test_restore_rejects_manifest_hash_and_size_tampering(self):
        archive = self.create_archive()

        def corrupt_hash(manifest):
            manifest["files"][0]["sha256"] = "0" * 64

        def corrupt_size(manifest):
            manifest["files"][0]["size"] += 1

        for label, mutation in (("hash", corrupt_hash), ("size", corrupt_size)):
            with self.subTest(manifest_field=label):
                tampered = self.root / ("tampered-" + label + ".tar.gz")
                self.rewrite_manifest(archive, tampered, mutation)
                result = self.run_restore(tampered, "rejected-" + label)
                self.assertIn("integrity mismatch", result.stderr)

    def test_restore_rejects_truncated_gzip_archive_without_traceback_or_destination(self):
        archive = self.create_archive()
        truncated = self.root / "truncated.tar.gz"
        archive_bytes = archive.read_bytes()
        self.assertGreater(len(archive_bytes), 100)
        # The database contains incompressible synthetic data, so removing
        # bytes from the gzip stream forces EOFError while reading its member.
        truncated.write_bytes(archive_bytes[:-100])

        result = self.run_restore(truncated, "rejected-truncated")
        self.assertIn("backup archive is corrupt or unreadable", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
