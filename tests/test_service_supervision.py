import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


class ServiceSupervisorTests(unittest.TestCase):
    def test_all_four_services_restart_and_stop_cleanly(self):
        repo = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory(prefix="dsh017-supervisor-") as temp:
            root = Path(temp)
            for source, target in (
                ("run_bili.sh.example", "run_bili.sh"),
                ("run_sidecars.sh.example", "run_sidecars.sh"),
                ("stop_services.sh.example", "stop_services.sh"),
            ):
                shutil.copy2(repo / source, root / target)

            fake_python = root / "fake-python"
            fake_python.write_text(
                "#!/bin/bash\n"
                "name=$(basename -- \"$2\")\n"
                "printf '%s\\n' \"$name\" >> \"$FAKE_RUN_LOG\"\n"
                "marker=\"$FAKE_RUN_DIR/$name.started\"\n"
                "if [ ! -f \"$marker\" ]; then touch \"$marker\"; exit 17; fi\n"
                "exec sleep 60\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            data_dir = root / "data"
            fake_run_dir = root / "fake-runs"
            fake_run_dir.mkdir()
            run_log = fake_run_dir / "runs.log"
            env = os.environ.copy()
            env.update({
                "DSH017_DATA_DIR": str(data_dir),
                "PYTHON_BIN": str(fake_python),
                "FAKE_RUN_DIR": str(fake_run_dir),
                "FAKE_RUN_LOG": str(run_log),
            })

            bili = subprocess.Popen(
                ["bash", str(root / "run_bili.sh")],
                cwd=str(root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            sidecars = subprocess.Popen(
                ["bash", str(root / "run_sidecars.sh")],
                cwd=str(root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            expected = {
                "bili_console.py",
                "tarot_server.py",
                "novel_server.py",
                "hub_server.py",
            }
            deadline = time.monotonic() + 12
            try:
                while time.monotonic() < deadline:
                    seen = set(run_log.read_text(encoding="utf-8").splitlines()) if run_log.exists() else set()
                    if expected.issubset(seen) and all(
                        (fake_run_dir / (name + ".started")).is_file() for name in expected
                    ):
                        # Each marker is created during the first (deliberately
                        # failing) run; wait until each supervisor starts run two.
                        counts = {name: seen_list.count(name)
                                  for name in expected
                                  for seen_list in [run_log.read_text(encoding="utf-8").splitlines()]}
                        if all(counts[name] >= 2 for name in expected):
                            break
                    time.sleep(0.1)
                else:
                    self.fail("Not all services were restarted by their supervisors")

                stop = subprocess.run(
                    ["bash", str(root / "stop_services.sh")],
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)
                self.assertIsNotNone(bili.poll(), "Bili supervisor is still running")
                self.assertIsNotNone(sidecars.poll(), "Sidecar supervisor is still running")
                self.assertFalse((data_dir / "run" / "bili-supervisor.pid").exists())
                self.assertFalse((data_dir / "run" / "sidecars-supervisor.pid").exists())

                for name in expected:
                    log_name = name.replace("_server.py", "").replace("_console.py", "") + ".log"
                    self.assertTrue((data_dir / "logs" / log_name).exists())
            finally:
                for process in (bili, sidecars):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
