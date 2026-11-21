"""Verify a restored backup is the database opened by a fresh application process.

All source, backup, and restore paths live under TemporaryDirectory. The
subprocess imports the production app.db module with the restored environment
to model a service restart without touching a user's live data.
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "data_backup.py"


def create_source_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE search_history(q TEXT PRIMARY KEY, ts INTEGER NOT NULL);
            CREATE TABLE favorites(
                bvid TEXT PRIMARY KEY, title TEXT, cover TEXT, author TEXT,
                ts INTEGER NOT NULL
            );
            CREATE TABLE watch_progress(
                bvid TEXT NOT NULL, cid INTEGER NOT NULL, position REAL,
                duration REAL, ts INTEGER NOT NULL
            );
            CREATE TABLE workspace_projects(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE workspace_files(
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_id INTEGER,
                workspace_id TEXT, content TEXT NOT NULL, version INTEGER NOT NULL,
                deleted_at INTEGER, updated_at INTEGER, kind TEXT NOT NULL
            );
            CREATE TABLE workspace_file_versions(
                id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, content TEXT NOT NULL,
                source TEXT NOT NULL, base_version INTEGER, created_at INTEGER
            );
            CREATE TABLE workspace_rules(
                id INTEGER PRIMARY KEY, file_pattern TEXT NOT NULL,
                operation TEXT NOT NULL, action TEXT NOT NULL, created_at INTEGER
            );
            CREATE TABLE chat_conversations(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, messages TEXT NOT NULL,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            );

            INSERT INTO search_history VALUES('restore startup query', 100);
            INSERT INTO favorites VALUES('BVrestore001', 'restored favorite', '', 'test', 100);
            INSERT INTO watch_progress VALUES('BVrestore001', 11, 42.5, 120, 100);
            INSERT INTO workspace_projects VALUES(
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'Restored project', '', 100, 100
            );
            INSERT INTO workspace_files VALUES(
                7, 'plan.md', NULL, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'restored workspace content',
                3, NULL, 100, 'file'
            );
            INSERT INTO workspace_file_versions VALUES(
                9, 7, 'restored previous revision', 'manual', 2, 90
            );
            INSERT INTO workspace_rules VALUES(1, '*.md', 'write', 'ask', 100);
            INSERT INTO chat_conversations VALUES(
                'chat-restore', 'restored chat',
                '[{"role":"user","content":"restored conversation"}]', 100, 100
            );
        """)


def database_snapshot(path):
    """Return reproducible integrity and row-count evidence for key tables."""
    tables = (
        "chat_conversations",
        "search_history",
        "favorites",
        "watch_progress",
        "workspace_projects",
        "workspace_files",
        "workspace_file_versions",
        "workspace_rules",
    )
    with sqlite3.connect(path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        row_counts = {
            table: connection.execute(
                'SELECT COUNT(*) FROM "' + table + '"'
            ).fetchone()[0]
            for table in tables
        }
    return {"integrity": integrity, "row_counts": row_counts}


class BackupRestoreApplicationStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-backup-app-start-")
        self.root = Path(self.temp.name)
        self.source_data = self.root / "source-data"
        self.source_presets = self.root / "source-presets"
        self.backup_dir = self.root / "backups"
        self.source_data.mkdir()
        self.source_presets.mkdir()
        create_source_database(self.source_data / "bili_data.db")
        (self.source_data / "providers.json").write_text(
            json.dumps([{
                "id": "restore-provider",
                "base_url": "https://api.example.test/v1",
                "models": ["restore-chat"],
            }]),
            encoding="utf-8",
        )
        (self.source_presets / "Restored.txt").write_text(
            "restored user preset", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, str(TOOL), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )

    def test_restored_database_is_selected_by_app_db_on_fresh_process_start(self):
        backup = self.run_tool(
            "backup",
            "--data-dir", self.source_data,
            "--db-path", self.source_data / "bili_data.db",
            "--preset-dir", self.source_presets,
            "--backup-dir", self.backup_dir,
        )
        self.assertEqual(backup.returncode, 0, backup.stdout + backup.stderr)
        archive_path = Path(backup.stdout.strip())
        self.assertTrue(archive_path.is_file())

        restored_data = self.root / "restored-data"
        restored_presets = self.root / "restored-presets"
        restore = self.run_tool(
            "restore",
            "--archive", archive_path,
            "--data-dir", restored_data,
            "--preset-dir", restored_presets,
        )
        self.assertEqual(restore.returncode, 0, restore.stdout + restore.stderr)

        restored_db = restored_data / "bili_data.db"
        self.assertTrue(restored_db.is_file())

        # Compare the source and recovered copies explicitly. The restore
        # command also validates integrity internally; these assertions keep
        # the before/after evidence visible in this end-to-end drill.
        source_snapshot = database_snapshot(self.source_data / "bili_data.db")
        restored_snapshot = database_snapshot(restored_db)
        self.assertEqual(source_snapshot["integrity"], "ok")
        self.assertEqual(restored_snapshot["integrity"], "ok")
        self.assertEqual(
            restored_snapshot["row_counts"],
            source_snapshot["row_counts"],
        )
        self.assertEqual(
            (restored_data / "providers.json").read_text(encoding="utf-8"),
            (self.source_data / "providers.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (restored_presets / "Restored.txt").read_text(encoding="utf-8"),
            "restored user preset",
        )

        # A fresh interpreter models the next service start. It must open the
        # restored database selected by the same data and DB path environment.
        env = os.environ.copy()
        env.update({
            "DSH017_DATA_DIR": str(restored_data),
            "DSH017_DB_PATH": str(restored_db),
            "DSH017_PRESET_DIR": str(restored_presets),
            "DSH017_BACKUP_DIR": str(self.root / "restored-backups"),
            "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
        })

        # The production database initializer idempotently seeds the built-in
        # "default" Workspace project on first service startup. Account for
        # that expected application-owned row while still checking that all
        # restored user records remain present and no extra rows appear on a
        # subsequent restart.
        expected_service_counts = dict(source_snapshot["row_counts"])
        expected_service_counts["workspace_projects"] += 1
        probe = """
import json
import app.db as db
from bili_console import app as service_app

connection = db._db_conn()
try:
    workspace_file = connection.execute(
        "SELECT content FROM workspace_files WHERE id=7"
    ).fetchone()
    workspace_version = connection.execute(
        "SELECT content FROM workspace_file_versions WHERE id=9"
    ).fetchone()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    tables = (
        "chat_conversations", "search_history", "favorites", "watch_progress",
        "workspace_projects", "workspace_files", "workspace_file_versions",
        "workspace_rules",
    )
    row_counts = {
        table: connection.execute(
            'SELECT COUNT(*) FROM "' + table + '"'
        ).fetchone()[0]
        for table in tables
    }
finally:
    connection.close()

# Importing the production Flask entrypoint models a fresh service start,
# rather than only proving that the database helper can open the restored file.
client = service_app.test_client()
history_response = client.get("/api/history")
favorites_response = client.get("/api/fav")
progress_response = client.get("/api/progress?bvid=BVrestore001&cid=11")
projects_response = client.get("/api/workspace/projects")
files_response = client.get("/api/workspace/files?project_id=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
versions_response = client.get("/api/workspace/files/7/versions")

print(json.dumps({
    "data_dir": db._DATA_DIR,
    "db_path": db._DB_PATH,
    "integrity": integrity,
    "row_counts": row_counts,
    "history": db.db_history_list(),
    "favorites": db.db_fav_list(),
    "progress": db.db_progress_get("BVrestore001", 11),
    "conversation": db.db_chat_conversation_get("chat-restore"),
    "workspace_file": workspace_file["content"] if workspace_file else None,
    "workspace_version": workspace_version["content"] if workspace_version else None,
    "service_routes": {
        "history_status": history_response.status_code,
        "history": history_response.get_json(),
        "favorites_status": favorites_response.status_code,
        "favorites": favorites_response.get_json(),
        "progress_status": progress_response.status_code,
        "progress": progress_response.get_json(),
        "projects_status": projects_response.status_code,
        "projects": projects_response.get_json(),
        "files_status": files_response.status_code,
        "files": files_response.get_json(),
        "versions_status": versions_response.status_code,
        "versions": versions_response.get_json(),
    },
}))
"""
        def start_service_process():
            return subprocess.run(
                [sys.executable, "-c", probe],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )

        started = start_service_process()
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        state = json.loads(started.stdout.strip())

        self.assertEqual(state["data_dir"], str(restored_data))
        self.assertEqual(state["db_path"], str(restored_db))
        self.assertEqual(state["integrity"], "ok")
        self.assertEqual(state["row_counts"], expected_service_counts)
        self.assertEqual(state["history"], ["restore startup query"])
        self.assertEqual(state["favorites"][0]["title"], "restored favorite")
        self.assertEqual(state["progress"]["position"], 42.5)
        self.assertEqual(
            state["conversation"]["messages"][0]["content"],
            "restored conversation",
        )
        self.assertEqual(state["workspace_file"], "restored workspace content")
        self.assertEqual(state["workspace_version"], "restored previous revision")

        # Exercise the production Flask entrypoint after the restored paths
        # have been selected, including the user-facing history and Workspace
        # APIs that a restarted service exposes.
        routes = state["service_routes"]
        self.assertEqual(routes["history_status"], 200)
        self.assertEqual(routes["history"]["items"][0]["q"], "restore startup query")
        self.assertEqual(routes["favorites_status"], 200)
        self.assertEqual(routes["favorites"]["items"][0]["title"], "restored favorite")
        self.assertEqual(routes["progress_status"], 200)
        self.assertEqual(routes["progress"]["position"], 42.5)
        self.assertEqual(routes["projects_status"], 200)
        self.assertIn(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            [item["id"] for item in routes["projects"]["items"]],
        )
        self.assertEqual(routes["files_status"], 200)
        self.assertIn(7, [item["id"] for item in routes["files"]["items"]])
        self.assertEqual(routes["versions_status"], 200)
        self.assertEqual(
            routes["versions"]["items"][0]["source"],
            "manual",
        )

        # A second clean process with the exact same environment models the
        # next supervisor-managed service start. It must reopen the same
        # recovered database without losing or silently recreating records.
        restarted = start_service_process()
        self.assertEqual(
            restarted.returncode, 0, restarted.stdout + restarted.stderr
        )
        restarted_state = json.loads(restarted.stdout.strip())
        self.assertEqual(restarted_state["data_dir"], str(restored_data))
        self.assertEqual(restarted_state["db_path"], str(restored_db))
        self.assertEqual(restarted_state["integrity"], "ok")
        self.assertEqual(
            restarted_state["row_counts"],
            expected_service_counts,
        )
        self.assertEqual(
            restarted_state["service_routes"]["history"]["items"][0]["q"],
            "restore startup query",
        )
        self.assertEqual(
            restarted_state["service_routes"]["files"]["items"][0]["id"],
            7,
        )


if __name__ == "__main__":
    unittest.main()
