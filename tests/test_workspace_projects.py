import os
import tempfile
import unittest
import uuid

os.environ.setdefault("DSH017_DATA_DIR", tempfile.mkdtemp(prefix="dsh017-workspace-tests-"))

from flask import Flask
from app.workspace_routes import workspace_bp


class WorkspaceProjectApiTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(workspace_bp)
        self.client = app.test_client()
        self.project_id = None
        self.file_ids = []

    def tearDown(self):
        for file_id in self.file_ids:
            self.client.delete("/api/workspace/files/%d" % file_id)
        if self.project_id:
            self.client.delete("/api/workspace/projects/" + self.project_id)

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

    def test_default_workspace_cannot_be_deleted(self):
        response = self.client.delete("/api/workspace/projects/default")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
