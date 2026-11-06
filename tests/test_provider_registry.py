import os
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("DSH017_DATA_DIR", tempfile.mkdtemp(prefix="dsh017-provider-tests-"))

import app.providers as providers


class ProviderRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dsh017-provider-config-")
        self.config_path = os.path.join(self.temp.name, "providers.json")
        self.secrets_path = os.path.join(self.temp.name, "provider_secrets.json")
        self.config_patch = patch.object(providers, "_CONFIG_PATH", self.config_path)
        self.secrets_patch = patch.object(providers, "_SECRETS_PATH", self.secrets_path)
        self.config_patch.start()
        self.secrets_patch.start()
        self.url_validation_patch = patch.object(providers, "validate_provider_url", return_value=True)
        self.url_validation_patch.start()
        self.runtime_before = dict(providers._RUNTIME_SECRETS)
        providers._RUNTIME_SECRETS.clear()

    def tearDown(self):
        providers._RUNTIME_SECRETS.clear()
        providers._RUNTIME_SECRETS.update(self.runtime_before)
        self.config_patch.stop()
        self.secrets_patch.stop()
        self.url_validation_patch.stop()
        self.temp.cleanup()

    def test_provider_key_is_not_exposed_and_is_stored_in_private_file(self):
        item = providers.add_provider({
            "id": "sample-provider",
            "name": "Sample Provider",
            "base_url": "https://api.example.test/v1",
            "models": ["sample-chat"],
            "api_key": "secret-value",
        })
        self.assertEqual(item["id"], "sample-provider")
        self.assertEqual(providers.get_provider_secret("sample-provider"), "secret-value")
        listed = next(
            row for row in providers.list_providers()
            if row["id"] == "sample-provider"
        )
        self.assertTrue(listed["secret_configured"])
        self.assertNotIn("api_key", listed)
        self.assertNotIn("secret-value", str(listed))
        self.assertEqual(os.stat(self.secrets_path).st_mode & 0o777, 0o600)
        with open(self.secrets_path, encoding="utf-8") as stream:
            self.assertEqual(__import__("json").load(stream)["sample-provider"], "secret-value")

    def test_provider_updates_models_and_removes_metadata_and_secret(self):
        providers.add_provider({
            "id": "sample-provider",
            "name": "Sample Provider",
            "base_url": "https://api.example.test/v1",
            "models": ["model-a"],
            "api_key": "secret-value",
        })
        updated = providers.update_provider("sample-provider", {
            "models": ["model-a", "model-b"],
            "default_model": "model-b",
        })
        self.assertEqual(updated["default_model"], "model-b")
        providers.delete_provider("sample-provider")
        self.assertIsNone(providers.get_provider("sample-provider"))
        self.assertEqual(providers.get_provider_secret("sample-provider"), "")

    def test_rejects_unsafe_base_urls_and_invalid_model_ids(self):
        bad_urls = [
            "file:///etc/passwd",
            "https://user:pass@example.com/v1",
            "https://example.com/v1?token=x",
            "https://example.com/v1#fragment",
        ]
        for base_url in bad_urls:
            with self.assertRaises(ValueError):
                providers.add_provider({
                    "id": "unsafe",
                    "name": "Unsafe",
                    "base_url": base_url,
                    "models": ["model-a"],
                })
        with self.assertRaises(ValueError):
            providers.add_provider({
                "id": "invalid-model",
                "name": "Invalid",
                "base_url": "https://api.example.test/v1",
                "models": ["bad model id"],
            })

    def test_resolve_provider_builds_openai_chat_completions_endpoint(self):
        providers.add_provider({
            "id": "sample-provider",
            "name": "Sample Provider",
            "base_url": "https://api.example.test/v1",
            "models": ["sample-chat"],
            "api_key": "secret-value",
        })
        item, key, endpoint = providers.resolve_provider("sample-provider", "sample-chat")
        self.assertEqual(item["id"], "sample-provider")
        self.assertEqual(key, "secret-value")
        self.assertEqual(endpoint, "https://api.example.test/v1/chat/completions")
        with self.assertRaises(ValueError):
            providers.resolve_provider("sample-provider", "unlisted-model")

    def test_models_endpoint_reads_openai_compatible_model_list(self):
        providers.add_provider({
            "id": "sample-provider",
            "name": "Sample Provider",
            "base_url": "https://api.example.test/v1",
            "models": ["sample-chat"],
            "api_key": "secret-value",
        })
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [{"id": "model-z"}, {"id": "model-a"}, {"id": "../bad"}]
        }
        with patch.object(providers, "provider_request", return_value=response) as get:
            models = providers.fetch_provider_models("sample-provider")
        self.assertEqual(models, ["model-a", "model-z"])
        self.assertEqual(get.call_args.args[0], "GET")
        self.assertEqual(
            get.call_args.args[1],
            "https://api.example.test/v1/models",
        )
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"],
            "Bearer secret-value",
        )
        self.assertEqual(get.call_args.args[0], "GET")
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 15))


if __name__ == "__main__":
    unittest.main()
