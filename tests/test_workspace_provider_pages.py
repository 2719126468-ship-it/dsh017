import unittest

from flask import Flask

from app.providers import provider_bp
from app.workspace_ui import workspace_ui_bp


class WorkspaceAndProviderPageTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(workspace_ui_bp)
        app.register_blueprint(provider_bp)
        self.client = app.test_client()

    def test_workspace_is_a_real_four_pane_project_ui(self):
        response = self.client.get("/workspace")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Workspaces · DSH-017", body)
        self.assertIn('id="projectList"', body)
        self.assertIn('id="fileTree"', body)
        self.assertIn('id="editor"', body)
        self.assertIn('id="preview"', body)
        self.assertIn('id="aiMessages"', body)
        self.assertIn("/api/workspace/confirm_edit", body)
        self.assertIn("prefers-reduced-motion", body)

    def test_workspace_mobile_layout_exposes_navigation_and_safe_viewport(self):
        response = self.client.get("/workspace")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("100dvh", body)
        self.assertIn("@media(max-width:760px)", body)
        self.assertIn('id="mobileProjects"', body)
        self.assertIn('id="mobileFiles"', body)
        self.assertIn('id="mobileAI"', body)
        self.assertIn(".ws-main.ai-open", body)
        self.assertIn(".ws-main.files-open", body)
        self.assertIn("visualViewport", body)
        self.assertIn("prefers-reduced-motion:reduce", body)
    def test_provider_page_lists_openai_compatible_presets_and_magpie(self):
        response = self.client.get("/providers")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("OpenAI", body)
        self.assertIn("DeepSeek", body)
        self.assertIn("OpenRouter", body)
        self.assertIn("Magpie Gateway", body)
        self.assertIn("@magpie-community/opencode-qoder-auth", body)
        self.assertIn('id="detectMagpie"', body)
        self.assertIn("/api/providers/detect-magpie", body)
        self.assertIn("DSHProviderKeys", body)
        self.assertIn("secret_configured", body)


if __name__ == "__main__":
    unittest.main()
