import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("DSH017_DATA_DIR", tempfile.mkdtemp(prefix="dsh017-workspace-tests-"))

from flask import Flask
import app.db as db
import app.workspace_routes as workspace_routes
from app.workspace_routes import workspace_bp


class WorkspaceProjectApiTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(workspace_bp)
        self.client = app.test_client()
        self.project_id = None
        self.file_ids = []
        self.rule_ids = []

        # Use a fresh SQLite database per test. The default test data directory
        # is shared across the unittest process, so rules created by other
        # modules must not affect the Workspace permission tests.
        self.db_temp = tempfile.TemporaryDirectory(prefix="dsh017-workspace-case-")
        self.db_path_patch = patch.object(
            db, "_DB_PATH", os.path.join(self.db_temp.name, "bili_data.db")
        )
        self.db_path_patch.start()
        db._db_init()
        db._db_init_workspace()
        db._db_init_rules()
        db._db_init_chat_conversations()

        with workspace_routes._AUTO_GUARD_LOCK:
            self._auto_state_before = (
                workspace_routes._AUTO_BLOCK_STREAK,
                workspace_routes._AUTO_DOWNGRADED,
            )
            workspace_routes._AUTO_BLOCK_STREAK = 0
            workspace_routes._AUTO_DOWNGRADED = False

    def tearDown(self):
        for rule_id in self.rule_ids:
            self.client.delete("/api/workspace/rules?id=%d" % rule_id)
        for file_id in self.file_ids:
            self.client.delete("/api/workspace/files/%d" % file_id)
        if self.project_id:
            self.client.delete("/api/workspace/projects/" + self.project_id)
        with workspace_routes._AUTO_GUARD_LOCK:
            workspace_routes._AUTO_BLOCK_STREAK, workspace_routes._AUTO_DOWNGRADED = self._auto_state_before
        self.db_path_patch.stop()
        self.db_temp.cleanup()

    def test_project_file_tree_versions_and_restore(self):
        created = self.client.post("/api/workspace/projects", json={
            "name": "测试项目 " + uuid.uuid4().hex[:8],
            "description": "workspace API test",
        })
        self.assertEqual(created.status_code, 201)
        project = created.get_json()["item"]
        self.project_id = project["id"]

        folder = self.client.post("/api/workspace/files", json={
            "name": "src", "project_id": self.project_id, "kind": "directory",
        })
        self.assertEqual(folder.status_code, 201)
        folder_id = folder.get_json()["id"]
        self.file_ids.append(folder_id)

        file_response = self.client.post("/api/workspace/files", json={
            "name": "README.md", "project_id": self.project_id,
            "parent_id": folder_id, "kind": "file",
        })
        self.assertEqual(file_response.status_code, 201)
        file_id = file_response.get_json()["id"]
        self.file_ids.append(file_id)

        listing = self.client.get("/api/workspace/files?project_id=" + self.project_id)
        self.assertEqual(listing.status_code, 200)
        nodes = listing.get_json()["items"]
        self.assertEqual({node["id"] for node in nodes}, {folder_id, file_id})
        self.assertEqual(next(node for node in nodes if node["id"] == folder_id)["kind"], "directory")
        self.assertEqual(next(node for node in nodes if node["id"] == file_id)["parent_id"], folder_id)

        saved = self.client.put("/api/workspace/files/%d" % file_id, json={
            "content": "# First version\n", "base_version": 1,
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["version"], 2)

        saved2 = self.client.put("/api/workspace/files/%d" % file_id, json={
            "content": "# Second version\n", "base_version": 2,
        })
        self.assertEqual(saved2.status_code, 200)
        versions = self.client.get("/api/workspace/files/%d/versions" % file_id).get_json()["items"]
        original = next(item for item in versions if item["source"] == "manual" and item["base_version"] == 0)

        restored = self.client.post("/api/workspace/files/%d/restore" % file_id, json={
            "version_id": original["id"], "base_version": 3,
        })
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.get_json()["content"], "")

        renamed = self.client.patch("/api/workspace/files/%d" % file_id, json={"name": "START.md"})
        self.assertEqual(renamed.status_code, 200)
        opened = self.client.get("/api/workspace/files/%d" % file_id).get_json()
        self.assertEqual(opened["name"], "START.md")
        self.assertEqual(opened["workspace_id"], self.project_id)

    def test_manual_ai_confirmation_is_one_shot_and_version_checked(self):
        project = self.client.post("/api/workspace/projects", json={
            "name": "AI confirmation " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = project["id"]
        file_id = self.client.post("/api/workspace/files", json={
            "name": "plan.md", "project_id": self.project_id,
        }).get_json()["id"]
        self.file_ids.append(file_id)

        saved = self.client.put("/api/workspace/files/%d" % file_id, json={
            "content": "alpha\nbeta\n", "base_version": 1,
        })
        self.assertEqual(saved.status_code, 200)
        confirmed = self.client.post("/api/workspace/confirm_edit", json={
            "file_id": file_id, "base_version": 2,
            "old_str": "beta", "new_str": "gamma",
        })
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(confirmed.get_json()["confirmed_by_user"])
        self.assertEqual(confirmed.get_json()["content"], "alpha\ngamma\n")
        self.assertEqual(confirmed.get_json()["version"], 3)

        stale = self.client.post("/api/workspace/confirm_edit", json={
            "file_id": file_id, "base_version": 2,
            "old_str": "gamma", "new_str": "delta",
        })
        self.assertEqual(stale.status_code, 409)

    def test_ai_apply_edit_rejects_directories_and_oversized_patches(self):
        project = self.client.post("/api/workspace/projects", json={
            "name": "AI edit guards " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = project["id"]

        folder = self.client.post("/api/workspace/files", json={
            "name": "src", "project_id": self.project_id, "kind": "directory",
        })
        self.assertEqual(folder.status_code, 201)
        folder_id = folder.get_json()["id"]
        self.file_ids.append(folder_id)

        directory_edit = self.client.post("/api/workspace/apply_edit", json={
            "file_id": folder_id, "base_version": 1,
            "old_str": "", "new_str": "must not be stored", "mode": "auto",
        })
        self.assertEqual(directory_edit.status_code, 400)
        self.assertEqual(directory_edit.get_json()["reason"], "not_a_file")

        file_response = self.client.post("/api/workspace/files", json={
            "name": "large.txt", "project_id": self.project_id,
        })
        self.assertEqual(file_response.status_code, 201)
        file_id = file_response.get_json()["id"]
        self.file_ids.append(file_id)
        oversized_edit = self.client.post("/api/workspace/apply_edit", json={
            "file_id": file_id, "base_version": 1,
            "old_str": "", "new_str": "x" * 1_000_001, "mode": "auto",
        })
        self.assertEqual(oversized_edit.status_code, 400)

        oversized_old_edit = self.client.post("/api/workspace/apply_edit", json={
            "file_id": file_id, "base_version": 1,
            "old_str": "x" * 1_000_001, "new_str": "", "mode": "auto",
        })
        self.assertEqual(oversized_old_edit.status_code, 400)

    def test_auto_edit_uses_default_ask_and_deny_overrides_allow(self):
        project = self.client.post("/api/workspace/projects", json={
            "name": "Rule precedence " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = project["id"]
        file_id = self.client.post("/api/workspace/files", json={
            "name": "plan.md", "project_id": self.project_id,
        }).get_json()["id"]
        self.file_ids.append(file_id)
        self.client.put("/api/workspace/files/%d" % file_id, json={
            "content": "alpha beta", "base_version": 1,
        })

        # No matching rule must ask; it must never silently grant auto-write.
        default_ask = self.client.post("/api/workspace/apply_edit", json={
            "file_id": file_id, "base_version": 2,
            "old_str": "alpha", "new_str": "changed", "mode": "auto",
        })
        self.assertEqual(default_ask.status_code, 409)
        self.assertEqual(default_ask.get_json()["reason"], "rule_ask")

        # A matching deny rule takes precedence over a more specific allow.
        for rule in (
            {"file_pattern": "plan*", "operation": "edit", "action": "deny"},
            {"file_pattern": "plan.md", "operation": "edit", "action": "allow"},
        ):
            response = self.client.post("/api/workspace/rules", json=rule)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["code"], 0)
        items = self.client.get("/api/workspace/rules").get_json()["items"]
        self.rule_ids.extend(
            item["id"] for item in items
            if item["file_pattern"] in ("plan*", "plan.md")
        )
        denied = self.client.post("/api/workspace/apply_edit", json={
            "file_id": file_id, "base_version": 2,
            "old_str": "alpha", "new_str": "must stay blocked", "mode": "auto",
        })
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get("/api/workspace/files/%d" % file_id).get_json()["content"], "alpha beta")

        # Explicit user confirmation must not bypass a deny rule either.
        manual_denied = self.client.post("/api/workspace/confirm_edit", json={
            "file_id": file_id, "base_version": 2,
            "old_str": "alpha", "new_str": "also blocked",
        })
        self.assertEqual(manual_denied.status_code, 403)

        deny_id = next(
            item["id"] for item in items if item["file_pattern"] == "plan*"
        )
        removed = self.client.delete("/api/workspace/rules?id=%d" % deny_id)
        self.assertEqual(removed.status_code, 200)
        self.rule_ids.remove(deny_id)

        applied = self.client.post("/api/workspace/apply_edit", json={
            "file_id": file_id, "base_version": 2,
            "old_str": "alpha", "new_str": "gamma", "mode": "auto",
        })
        self.assertEqual(applied.status_code, 200)
        self.assertTrue(applied.get_json()["auto_applied"])
        self.assertEqual(applied.get_json()["version"], 3)
        self.assertEqual(applied.get_json()["content"], "gamma beta")

    def test_auto_edit_breaker_downgrades_to_ask_after_repeated_blocks(self):
        project = self.client.post("/api/workspace/projects", json={
            "name": "Auto breaker " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = project["id"]
        file_id = self.client.post("/api/workspace/files", json={
            "name": "breaker.txt", "project_id": self.project_id,
        }).get_json()["id"]
        self.file_ids.append(file_id)

        for _ in range(workspace_routes._AUTO_BLOCK_THRESHOLD):
            blocked = self.client.post("/api/workspace/apply_edit", json={
                "file_id": file_id, "base_version": 1,
                "old_str": "", "new_str": "blocked", "mode": "auto",
            })
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(blocked.get_json()["reason"], "rule_ask")

        status = self.client.get("/api/workspace/auto_status").get_json()
        self.assertTrue(status["downgraded"])
        self.assertEqual(status["streak"], workspace_routes._AUTO_BLOCK_THRESHOLD)

        response = self.client.post("/api/workspace/rules", json={
            "file_pattern": "breaker.txt", "operation": "edit", "action": "allow",
        })
        self.assertEqual(response.status_code, 200)
        items = self.client.get("/api/workspace/rules").get_json()["items"]
        rule_id = next(item["id"] for item in items if item["file_pattern"] == "breaker.txt")
        self.rule_ids.append(rule_id)

        downgraded = self.client.post("/api/workspace/apply_edit", json={
            "file_id": file_id, "base_version": 1,
            "old_str": "", "new_str": "must remain unchanged", "mode": "auto",
        })
        self.assertEqual(downgraded.status_code, 409)
        self.assertEqual(downgraded.get_json()["reason"], "auto_downgraded")
        stored = self.client.get("/api/workspace/files/%d" % file_id).get_json()
        self.assertEqual(stored["content"], "")
        self.assertEqual(stored["version"], 1)

    def test_confirm_edit_rejects_oversized_old_and_new_patch_strings(self):
        project = self.client.post("/api/workspace/projects", json={
            "name": "Confirm size " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = project["id"]
        file_id = self.client.post("/api/workspace/files", json={
            "name": "bounded.md", "project_id": self.project_id,
        }).get_json()["id"]
        self.file_ids.append(file_id)

        oversized_old = self.client.post("/api/workspace/confirm_edit", json={
            "file_id": file_id, "base_version": 1,
            "old_str": "x" * 1_000_001, "new_str": "",
        })
        self.assertEqual(oversized_old.status_code, 400)

        oversized_new = self.client.post("/api/workspace/confirm_edit", json={
            "file_id": file_id, "base_version": 1,
            "old_str": "", "new_str": "x" * 1_000_001,
        })
        self.assertEqual(oversized_new.status_code, 400)

        stored = self.client.get("/api/workspace/files/%d" % file_id).get_json()
        self.assertEqual(stored["content"], "")
        self.assertEqual(stored["version"], 1)

    def test_stale_file_save_returns_conflict_without_overwriting_latest_content(self):
        project = self.client.post("/api/workspace/projects", json={
            "name": "Optimistic lock " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = project["id"]
        file_id = self.client.post("/api/workspace/files", json={
            "name": "state.md", "project_id": self.project_id,
        }).get_json()["id"]
        self.file_ids.append(file_id)
        first = self.client.put("/api/workspace/files/%d" % file_id, json={
            "content": "newer committed content", "base_version": 1,
        })
        self.assertEqual(first.status_code, 200)
        stale = self.client.put("/api/workspace/files/%d" % file_id, json={
            "content": "stale content must not win", "base_version": 1,
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["current_version"], 2)
        latest = self.client.get("/api/workspace/files/%d" % file_id)
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.get_json()["content"], "newer committed content")
        self.assertEqual(latest.get_json()["version"], 2)

    def test_file_creation_rejects_unsafe_names_duplicate_siblings_and_foreign_parent(self):
        first = self.client.post("/api/workspace/projects", json={
            "name": "Boundary project " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        self.project_id = first["id"]
        for invalid_name in ("", "../escape", "folder/file", "folder\\\\file", "..", "."):
            with self.subTest(name=invalid_name):
                response = self.client.post("/api/workspace/files", json={
                    "name": invalid_name, "project_id": self.project_id,
                })
                self.assertEqual(response.status_code, 400)
        folder = self.client.post("/api/workspace/files", json={
            "name": "src", "project_id": self.project_id, "kind": "directory",
        })
        self.assertEqual(folder.status_code, 201)
        folder_id = folder.get_json()["id"]
        self.file_ids.append(folder_id)
        bad_parent = self.client.post("/api/workspace/files", json={
            "name": "bad-parent.md", "project_id": self.project_id, "parent_id": True,
        })
        self.assertEqual(bad_parent.status_code, 400)
        other = self.client.post("/api/workspace/projects", json={
            "name": "Other project " + uuid.uuid4().hex[:8],
        }).get_json()["item"]
        foreign_parent = self.client.post("/api/workspace/files", json={
            "name": "foreign.md", "project_id": other["id"], "parent_id": folder_id,
        })
        self.assertEqual(foreign_parent.status_code, 400)
        self.client.delete("/api/workspace/projects/" + other["id"])
        created = self.client.post("/api/workspace/files", json={
            "name": "duplicate.md", "project_id": self.project_id,
        })
        self.assertEqual(created.status_code, 201)
        file_id = created.get_json()["id"]
        self.file_ids.append(file_id)
        duplicate = self.client.post("/api/workspace/files", json={
            "name": "duplicate.md", "project_id": self.project_id,
        })
        self.assertEqual(duplicate.status_code, 409)
    def test_default_workspace_cannot_be_deleted(self):
        response = self.client.delete("/api/workspace/projects/default")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
