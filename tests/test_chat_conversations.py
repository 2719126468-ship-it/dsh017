import unittest

from flask import Flask

from app.chat_routes import chat_bp


class ChatConversationApiTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(chat_bp)
        self.client = app.test_client()
        self.created_ids = []

    def tearDown(self):
        for conversation_id in self.created_ids:
            self.client.delete("/api/conversations/" + conversation_id)

    def test_create_list_restore_update_and_delete_conversation(self):
        messages = [
            {"role": "user", "content": "帮我整理一份项目计划"},
            {"role": "assistant", "content": "可以，先确定目标。"},
        ]
        created = self.client.post("/api/conversations", json={"messages": messages})
        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        conversation_id = item["id"]
        self.created_ids.append(conversation_id)
        self.assertEqual(len(conversation_id), 32)
        self.assertEqual(item["title"], "帮我整理一份项目计划")
        self.assertEqual(item["messages"], messages)

        listed = self.client.get("/api/conversations?limit=20")
        self.assertEqual(listed.status_code, 200)
        summary = next(row for row in listed.get_json()["items"] if row["id"] == conversation_id)
        self.assertEqual(summary["message_count"], 2)

        restored = self.client.get("/api/conversations/" + conversation_id)
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.get_json()["item"]["messages"], messages)

        updated_messages = messages + [{"role": "user", "content": "再补充风险分析"}]
        updated = self.client.put(
            "/api/conversations/" + conversation_id,
            json={"title": "项目计划与风险分析", "messages": updated_messages},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["item"]["title"], "项目计划与风险分析")
        self.assertEqual(len(updated.get_json()["item"]["messages"]), 3)

        deleted = self.client.delete("/api/conversations/" + conversation_id)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/conversations/" + conversation_id).status_code, 404)
        self.created_ids.remove(conversation_id)

    def test_conversation_api_rejects_invalid_ids_and_message_payloads(self):
        self.assertEqual(self.client.get("/api/conversations/not-a-valid-id").status_code, 400)
        self.assertEqual(self.client.get("/api/conversations/" + "0" * 32).status_code, 404)

        bad_role = self.client.post("/api/conversations", json={
            "messages": [{"role": "system", "content": "do not accept arbitrary roles"}]
        })
        self.assertEqual(bad_role.status_code, 400)

        bad_content = self.client.post("/api/conversations", json={
            "messages": [{"role": "user", "content": 123}]
        })
        self.assertEqual(bad_content.status_code, 400)

        too_many_chars = self.client.post("/api/conversations", json={
            "messages": [{"role": "user", "content": "x" * 200001}]
        })
        self.assertEqual(too_many_chars.status_code, 400)

        too_many_messages = self.client.post("/api/conversations", json={
            "messages": [{"role": "user", "content": "x"} for _ in range(101)]
        })
        self.assertEqual(too_many_messages.status_code, 400)

    def test_conversation_list_limit_is_bounded(self):
        self.assertEqual(self.client.get("/api/conversations?limit=0").status_code, 400)
        self.assertEqual(self.client.get("/api/conversations?limit=201").status_code, 400)
        self.assertEqual(self.client.get("/api/conversations?limit=abc").status_code, 400)


if __name__ == "__main__":
    unittest.main()
