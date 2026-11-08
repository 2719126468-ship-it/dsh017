import json
import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

import app.providers as providers
from app.providers import provider_bp


class ProviderApiLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-provider-api-")
        self.config_patch = patch.object(
            providers, "_CONFIG_PATH", os.path.join(self.temp.name, "providers.json")
        )
        self.secrets_patch = patch.object(
            providers, "_SECRETS_PATH", os.path.join(self.temp.name, "provider_secrets.json")
        )
        self.url_patch = patch.object(
            providers, "validate_provider_url_syntax", return_value=True
        )
        self.config_patch.start()
        self.secrets_patch.start()
        self.url_patch.start()
        self.runtime_before = dict(providers._RUNTIME_SECRETS)
        providers._RUNTIME_SECRETS.clear()

        app = Flask(__name__)
        app.register_blueprint(provider_bp)
        self.client = app.test_client()

    def tearDown(self):
        providers._RUNTIME_SECRETS.clear()
        providers._RUNTIME_SECRETS.update(self.runtime_before)
        self.url_patch.stop()
        self.secrets_patch.stop()
        self.config_patch.stop()
        self.temp.cleanup()

    def test_create_list_update_secret_disable_and_delete_lifecycle(self):
        original_key = "synthetic-provider-key-original"
        replacement_key = "synthetic-provider-key-replaced"

        created = self.client.post("/api/providers", json={
            "id": "lifecycle-provider",
            "name": "Lifecycle Provider",
            "base_url": "https://api.example.test/v1",
            "models": ["model-a"],
            "default_model": "model-a",
            "api_key": original_key,
        })
        self.assertEqual(created.status_code, 201)
        created_payload = created.get_json()["item"]
        self.assertTrue(created_payload["secret_configured"])
        self.assertNotIn("api_key", created_payload)
        self.assertNotIn(original_key, created.get_data(as_text=True))

        listed = self.client.get("/api/providers")
        self.assertEqual(listed.status_code, 200)
        item = next(
            value for value in listed.get_json()["items"]
            if value["id"] == "lifecycle-provider"
        )
        self.assertTrue(item["secret_configured"])
        self.assertNotIn("api_key", item)
        self.assertNotIn(original_key, listed.get_data(as_text=True))

        updated = self.client.put("/api/providers/lifecycle-provider", json={
            "name": "Lifecycle Provider Updated",
            "enabled": False,
            "api_key": replacement_key,
        })
        self.assertEqual(updated.status_code, 200)
        updated_item = updated.get_json()["item"]
        self.assertFalse(updated_item["enabled"])
        self.assertTrue(updated_item["secret_configured"])
        self.assertNotIn(replacement_key, updated.get_data(as_text=True))
        self.assertEqual(
            providers.get_provider_secret("lifecycle-provider"), replacement_key
        )

        deleted = self.client.delete("/api/providers/lifecycle-provider")
        self.assertEqual(deleted.status_code, 200)
        self.assertIsNone(providers.get_provider("lifecycle-provider"))
        self.assertEqual(providers.get_provider_secret("lifecycle-provider"), "")

        with open(providers._CONFIG_PATH, encoding="utf-8") as stream:
            remaining = json.load(stream)
        self.assertFalse(any(
            row.get("id") == "lifecycle-provider" for row in remaining
        ))
        if os.path.exists(providers._SECRETS_PATH):
            with open(providers._SECRETS_PATH, encoding="utf-8") as stream:
                secrets = json.load(stream)
            self.assertNotIn("lifecycle-provider", secrets)


if __name__ == "__main__":
    unittest.main()
