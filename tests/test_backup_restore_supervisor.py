"""Exercise a restored DSH-017 data directory through the real supervisors."""
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PORTS = {
    "hub": 8080,
    "tarot": 8084,
    "novel": 8091,
    "bili": 8092,
}
HISTORY_MARKER = "restored-supervisor-restart-marker"


class BackupRestoreSupervisorIntegrationTests(unittest.TestCase):
    def setUp(self):
        missing = [name for name in ("bash", "flock", "ps") if shutil.which(name) is None]
        if missing:
            self.skipTest("supervisor integration requires: " + ", ".join(missing))

        occupied = self._occupied_ports()
        if occupied:
            self.skipTest(
                "refusing to interfere with existing listeners on ports "
                + ", ".join(map(str, occupied))
            )

        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-restore-supervisor-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sandbox = self.root / "repo"
        self.sandbox.mkdir()
        self.supervisors = []
        self.log_handles = []
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.addCleanup(self._cleanup_supervisors)

        # The stop script intentionally checks the deployed script names in
        # the supervisor command line. Copy the real scripts under those names
        # and link only the application sources needed by the four services.
        for name in (
            "app",
            "presets",
            "bili_console.py",
            "hub_server.py",
            "novel_server.py",
            "tarot_server.py",
        ):
            source = ROOT / name
            if source.exists():
                (self.sandbox / name).symlink_to(
                    source, target_is_directory=source.is_dir()
                )

        for source_name, target_name in (
            ("run_bili.sh.example", "run_bili.sh"),
            ("run_sidecars.sh.example", "run_sidecars.sh"),
            ("stop_services.sh.example", "stop_services.sh"),
        ):
            shutil.copy2(ROOT / source_name, self.sandbox / target_name)

        self._create_and_restore_fixture()

        self.service_env = os.environ.copy()
        self.service_env.update({
            "DSH017_DATA_DIR": str(self.restored_data),
            "DSH017_DB_PATH": str(self.restored_data / "bili_data.db"),
            "DSH017_PRESET_DIR": str(self.restored_presets),
            "DSH017_BACKUP_DIR": str(self.restored_data / "backup"),
            "DSH017_AUTH_TOKEN": "normal-test-token-" + "n" * 40,
            "DSH017_ADMIN_TOKEN": "admin-test-token-" + "a" * 40,
            "DSH017_AUTH_EXEMPT_IPS": "",
            "ZHIPU_API_KEY": "test-only-not-a-real-provider-key",
            "PYTHON_BIN": sys.executable,
            "PYTHONPATH": str(self.sandbox) + os.pathsep + str(ROOT),
            "PYTHONUNBUFFERED": "1",
        })

    @staticmethod
    def _occupied_ports():
        occupied = []
        for port in SERVICE_PORTS.values():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("0.0.0.0", port))
                except OSError:
                    occupied.append(port)
        return occupied

    def _run(self, command, *, cwd=None, env=None, timeout=30):
        return subprocess.run(
            command,
            cwd=str(cwd or ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _create_and_restore_fixture(self):
        source_data = self.root / "source-data"
        source_presets = self.root / "source-presets"
        source_backups = self.root / "source-backups"
        source_data.mkdir()
        source_presets.mkdir()
        (source_data / "providers.json").write_text(
            json.dumps([{
                "id": "supervisor-test",
                "base_url": "https://api.example.test/v1",
                "models": ["supervisor-test-model"],
            }]),
            encoding="utf-8",
        )
        (source_presets / "Supervisor.txt").write_text(
            "synthetic restored preset", encoding="utf-8"
        )

        seed_env = os.environ.copy()
        seed_env.update({
            "DSH017_DATA_DIR": str(source_data),
            "DSH017_DB_PATH": str(source_data / "bili_data.db"),
            "DSH017_PRESET_DIR": str(source_presets),
            "DSH017_BACKUP_DIR": str(source_backups),
            "PYTHONPATH": str(ROOT) + os.pathsep + seed_env.get("PYTHONPATH", ""),
        })
        seed = self._run(
            [
                sys.executable,
                "-c",
                (
                    "import app.db as db; "
                    "db.db_history_add(" + repr(HISTORY_MARKER) + "); "
                    "db.db_fav_toggle('BVsupervisor001', 'restored supervisor favorite', '', 'test'); "
                    "db.db_progress_save('BVsupervisor001', 11, 37.5, 120)"
                ),
            ],
            env=seed_env,
        )
        self.assertEqual(seed.returncode, 0, seed.stdout + seed.stderr)

        backup = self._run([
            sys.executable,
            str(ROOT / "scripts" / "data_backup.py"),
            "backup",
            "--data-dir", str(source_data),
            "--db-path", str(source_data / "bili_data.db"),
            "--preset-dir", str(source_presets),
            "--backup-dir", str(source_backups),
        ], env=seed_env)
        self.assertEqual(backup.returncode, 0, backup.stdout + backup.stderr)
        archive = Path(backup.stdout.strip())
        self.assertTrue(archive.is_file(), backup.stdout)

        self.restored_data = self.root / "restored-data"
        self.restored_presets = self.root / "restored-presets"
        restore = self._run([
            sys.executable,
            str(ROOT / "scripts" / "data_backup.py"),
            "restore",
            "--archive", str(archive),
            "--data-dir", str(self.restored_data),
            "--preset-dir", str(self.restored_presets),
            "--db-name", "bili_data.db",
        ])
        self.assertEqual(restore.returncode, 0, restore.stdout + restore.stderr)
        self.assertTrue((self.restored_data / "bili_data.db").is_file())
        self.assertEqual(
            (self.restored_presets / "Supervisor.txt").read_text(encoding="utf-8"),
            "synthetic restored preset",
        )

    def _start_supervisors(self):
        self.supervisors = []
        self.log_handles = []
        for name in ("run_bili.sh", "run_sidecars.sh"):
            log_handle = open(self.root / (name + ".out"), "w", encoding="utf-8")
            process = subprocess.Popen(
                ["bash", str(self.sandbox / name)],
                cwd=str(self.sandbox),
                env=self.service_env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self.log_handles.append(log_handle)
            self.supervisors.append(process)

    def _supervisor_logs(self):
        for handle in self.log_handles:
            handle.flush()
        chunks = []
        for name in ("run_bili.sh", "run_sidecars.sh"):
            path = self.root / (name + ".out")
            if path.exists():
                chunks.append("===== " + name + " =====\n" + path.read_text(encoding="utf-8"))
        for name in ("bili", "hub", "novel", "tarot"):
            path = self.restored_data / "logs" / (name + ".log")
            if path.exists():
                chunks.append("===== " + path.name + " =====\n" + path.read_text(encoding="utf-8"))
        return "\n".join(chunks)

    def _wait_for_services(self):
        deadline = time.monotonic() + 45
        ready = set()
        last_errors = {}
        while time.monotonic() < deadline:
            exited = [process.returncode for process in self.supervisors if process.poll() is not None]
            if exited:
                self.fail(
                    "a supervisor exited before all services became healthy; "
                    + self._supervisor_logs()
                )

            for name, port in SERVICE_PORTS.items():
                if name in ready:
                    continue
                try:
                    with self.opener.open(
                        "http://127.0.0.1:%d/health" % port, timeout=1
                    ) as response:
                        if response.status == 200:
                            ready.add(name)
                except Exception as error:
                    last_errors[name] = repr(error)

            if ready == set(SERVICE_PORTS):
                return
            time.sleep(0.25)

        self.fail(
            "services did not all become healthy; ready=%r errors=%r\n%s"
            % (sorted(ready), last_errors, self._supervisor_logs())
        )

    def _assert_restored_database(self):
        database = self.restored_data / "bili_data.db"
        with sqlite3.connect(database, timeout=5) as connection:
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
            self.assertEqual(
                connection.execute(
                    "SELECT q FROM search_history WHERE q=?", (HISTORY_MARKER,)
                ).fetchone()[0],
                HISTORY_MARKER,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT title FROM favorites WHERE bvid='BVsupervisor001'"
                ).fetchone()[0],
                "restored supervisor favorite",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT position FROM watch_progress "
                    "WHERE bvid='BVsupervisor001' AND cid=11"
                ).fetchone()[0],
                37.5,
            )

    def _assert_bili_service_reads_restored_database(self):
        with self.opener.open("http://127.0.0.1:8092/metrics", timeout=3) as response:
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
        daily = payload["daily"]
        self.assertGreaterEqual(daily["history_total"], 1)
        self.assertGreaterEqual(daily["fav_total"], 1)
        self.assertGreaterEqual(daily["progress_total"], 1)

    def _stop_supervisors(self):
        if not self.supervisors:
            return
        stop = self._run(
            ["bash", str(self.sandbox / "stop_services.sh")],
            cwd=self.sandbox,
            env=self.service_env,
            timeout=45,
        )
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)
        for process in self.supervisors:
            process.wait(timeout=10)
        run_dir = self.restored_data / "run"
        self.assertFalse((run_dir / "bili-supervisor.pid").exists())
        self.assertFalse((run_dir / "sidecars-supervisor.pid").exists())
        for handle in self.log_handles:
            handle.close()
        self.supervisors = []
        self.log_handles = []

    def _assert_services_stopped(self):
        deadline = time.monotonic() + 5
        listening = []
        while time.monotonic() < deadline:
            listening = []
            for port in SERVICE_PORTS.values():
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.2)
                    if sock.connect_ex(("127.0.0.1", port)) == 0:
                        listening.append(port)
            if not listening:
                return
            time.sleep(0.1)
        self.fail(
            "service ports remained open after supervisor stop: "
            + ", ".join(map(str, listening))
            + "\n"
            + self._supervisor_logs()
        )

    def _cleanup_supervisors(self):
        if any(process.poll() is None for process in self.supervisors):
            try:
                subprocess.run(
                    ["bash", str(self.sandbox / "stop_services.sh")],
                    cwd=str(self.sandbox),
                    env=self.service_env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except Exception:
                pass
        for process in self.supervisors:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except Exception:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
                    except Exception:
                        pass
        for handle in self.log_handles:
            try:
                handle.close()
            except Exception:
                pass
        self.supervisors = []
        self.log_handles = []

    def test_restored_database_survives_real_service_stop_and_restart(self):
        self._assert_restored_database()

        self._start_supervisors()
        self._wait_for_services()
        self._assert_bili_service_reads_restored_database()
        self._assert_restored_database()

        # Stop only the supervisors recorded under this isolated restored data
        # directory, then verify the database remains intact before restart.
        self._stop_supervisors()
        self._assert_services_stopped()
        self._assert_restored_database()

        # Reuse the exact same data, DB, preset, and backup paths.
        self._start_supervisors()
        self._wait_for_services()
        self._assert_bili_service_reads_restored_database()
        self._assert_restored_database()
        self._stop_supervisors()
        self._assert_services_stopped()


if __name__ == "__main__":
    unittest.main()
