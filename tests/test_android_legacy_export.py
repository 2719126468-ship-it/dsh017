import io
import json
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import export_legacy_android_data as exporter


def make_sqlite_bytes():
    with tempfile.TemporaryDirectory(prefix="dsh017-legacy-db-") as directory:
        path = Path(directory) / "bili_data.db"
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE migration_probe (value TEXT NOT NULL)")
            connection.execute("INSERT INTO migration_probe VALUES ('preserve-me')")
        return path.read_bytes()


def make_tar(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


class LegacyAndroidAdbExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-legacy-export-test-")
        self.root = Path(self.temp.name)
        self.database = make_sqlite_bytes()
        self.device_tar = make_tar([
            ("./bili_data.db", self.database),
            ("./providers.json", b'[{"id":"test","base_url":"https://api.example.test/v1","models":["test-model"]}]'),
            ("./presets/Writing.txt", b"private preset content"),
        ])

    def tearDown(self):
        self.temp.cleanup()

    def run_export_with_fake_adb(self, *, active=False, devices=None):
        real_run = subprocess.run
        commands = []
        device_list = devices or "List of devices attached\nserial-1 device product:test model:test\n"

        def fake_run(command, **kwargs):
            commands.append(command)
            if command[0] != "fake-adb":
                return real_run(command, **kwargs)

            joined = " ".join(command)
            if joined.endswith("devices -l"):
                return subprocess.CompletedProcess(command, 0, stdout=device_list, stderr="")
            if "shell pm path " in joined:
                return subprocess.CompletedProcess(command, 0, stdout="package:/data/app/test/base.apk\n", stderr="")
            if "shell run-as " in joined and "test -d files/dsh017" in joined:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if "shell run-as " in joined and joined.endswith(" id"):
                return subprocess.CompletedProcess(command, 0, stdout="uid=10123(u0_a123) gid=10123(u0_a123)\n", stderr="")
            if "shell pidof " in joined:
                if active:
                    return subprocess.CompletedProcess(command, 0, stdout="12345\n", stderr="")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            if "exec-out run-as " in joined:
                kwargs["stdout"].write(self.device_tar)
                return subprocess.CompletedProcess(command, 0, stderr=b"")
            raise AssertionError("Unexpected ADB command: " + joined)

        output_dir = self.root / "output"
        with patch.object(exporter.subprocess, "run", side_effect=fake_run):
            archive = exporter.export_legacy_data(
                adb="fake-adb",
                output_dir=output_dir,
            )
        return archive, output_dir, commands

    def test_exports_standard_archive_without_secrets_or_device_writes(self):
        archive_path, output_dir, commands = self.run_export_with_fake_adb()
        self.assertTrue(archive_path.is_file())
        self.assertEqual(archive_path.parent, output_dir)
        self.assertEqual(archive_path.stat().st_mode & 0o777, 0o600)

        with tarfile.open(archive_path, "r:gz") as archive:
            names = set(archive.getnames())
            self.assertEqual(
                names,
                {"manifest.json", "database.sqlite3", "providers.json", "presets/Writing.txt"},
            )
            self.assertFalse({"auth_token", "admin_token", "provider_secrets.json"} & names)
            manifest = json.load(archive.extractfile("manifest.json"))
            self.assertEqual(manifest["format"], "dsh017-data-backup")
            self.assertEqual(manifest["version"], 1)
            self.assertIn("auth_token", manifest["excluded"])
            restored_db = self.root / "restored.sqlite3"
            restored_db.write_bytes(archive.extractfile("database.sqlite3").read())

        with sqlite3.connect(restored_db) as connection:
            self.assertEqual(
                connection.execute("SELECT value FROM migration_probe").fetchone()[0],
                "preserve-me",
            )

        joined_commands = [" ".join(command) for command in commands]
        self.assertTrue(any("pm path com.dsh017.android.debug" in item for item in joined_commands))
        self.assertTrue(any("run-as com.dsh017.android.debug id" in item for item in joined_commands))
        self.assertTrue(any("exec-out run-as com.dsh017.android.debug" in item for item in joined_commands))
        forbidden = (" install ", " uninstall ", " push ", " pull ", " force-stop ", " rm ", " mv ")
        self.assertFalse(
            any(token in " " + item + " " for item in joined_commands for token in forbidden),
            joined_commands,
        )

    def test_refuses_to_copy_while_legacy_app_is_running(self):
        real_run = subprocess.run
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            if command[0] != "fake-adb":
                return real_run(command, **kwargs)
            joined = " ".join(command)
            if joined.endswith("devices -l"):
                return subprocess.CompletedProcess(command, 0, stdout="List of devices attached\nserial-1 device\n", stderr="")
            if "shell pm path " in joined:
                return subprocess.CompletedProcess(command, 0, stdout="package:/data/app/test/base.apk\n", stderr="")
            if "shell run-as " in joined and "test -d files/dsh017" in joined:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if "shell run-as " in joined and joined.endswith(" id"):
                return subprocess.CompletedProcess(command, 0, stdout="uid=10123\n", stderr="")
            if "shell pidof " in joined:
                return subprocess.CompletedProcess(command, 0, stdout="12345\n", stderr="")
            raise AssertionError("The export stream must not start while the app is running")

        with patch.object(exporter.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(exporter.LegacyExportError, "仍在运行"):
                exporter.export_legacy_data(adb="fake-adb", output_dir=self.root / "output")
        self.assertFalse(any("exec-out" in command for command in commands))

    def test_requires_explicit_serial_when_multiple_devices_are_authorized(self):
        with patch.object(exporter, "_run_capture") as run_capture:
            run_capture.return_value = subprocess.CompletedProcess(
                [], 0,
                stdout="List of devices attached\nserial-1 device\nserial-2 device\n",
                stderr="",
            )
            with self.assertRaisesRegex(exporter.LegacyExportError, "--serial"):
                exporter._select_device("adb", None)

    def test_rejects_secret_and_unexpected_members(self):
        payload = make_tar([
            ("bili_data.db", self.database),
            ("auth_token", b"must-never-be-exported"),
        ])
        archive_path = self.root / "secret.tar"
        archive_path.write_bytes(payload)
        with self.assertRaisesRegex(exporter.LegacyExportError, "未允许"):
            exporter._extract_legacy_tar(archive_path, self.root / "stage-secret")

    def test_rejects_path_traversal_and_duplicate_normalized_members(self):
        traversal = make_tar([
            ("bili_data.db", self.database),
            ("../outside.txt", b"no"),
        ])
        traversal_path = self.root / "traversal.tar"
        traversal_path.write_bytes(traversal)
        with self.assertRaisesRegex(exporter.LegacyExportError, "未允许"):
            exporter._extract_legacy_tar(traversal_path, self.root / "stage-traversal")

        duplicate = make_tar([
            ("bili_data.db", self.database),
            ("./bili_data.db", self.database),
        ])
        duplicate_path = self.root / "duplicate.tar"
        duplicate_path.write_bytes(duplicate)
        with self.assertRaisesRegex(exporter.LegacyExportError, "重复"):
            exporter._extract_legacy_tar(duplicate_path, self.root / "stage-duplicate")

    def test_rejects_symlinks_and_archives_without_database(self):
        symlink_path = self.root / "symlink.tar"
        with tarfile.open(symlink_path, "w") as archive:
            link = tarfile.TarInfo("bili_data.db")
            link.type = tarfile.SYMTYPE
            link.linkname = "outside"
            archive.addfile(link)
        with self.assertRaisesRegex(exporter.LegacyExportError, "非普通文件"):
            exporter._extract_legacy_tar(symlink_path, self.root / "stage-symlink")

        missing_db = self.root / "missing-db.tar"
        missing_db.write_bytes(make_tar([("providers.json", b"[]")]))
        with self.assertRaisesRegex(exporter.LegacyExportError, "没有 bili_data.db"):
            exporter._extract_legacy_tar(missing_db, self.root / "stage-missing-db")


if __name__ == "__main__":
    unittest.main()
