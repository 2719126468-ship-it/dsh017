import os
import tempfile
import unittest

# Keep hub auth tokens out of the checkout while importing the production app.
_TEST_DATA_DIR = tempfile.TemporaryDirectory(prefix="dsh017-hub-tests-")
os.environ["DSH017_DATA_DIR"] = _TEST_DATA_DIR.name

from hub_server import app as hub_app, SERVICES


class StatisticsConsoleTests(unittest.TestCase):
    def setUp(self):
        self.client = hub_app.test_client()

    def test_stats_route_serves_a_dedicated_dashboard(self):
        response = self.client.get("/stats")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>统计控制台 · DSH-017</title>", body)
        self.assertIn('id="counterRows"', body)
        self.assertIn('id="services"', body)
        self.assertIn('fetch("/api/status"', body)
        self.assertNotIn('id="grid"', body)

    def test_hub_has_a_separate_entry_for_the_stats_dashboard(self):
        stats = next((service for service in SERVICES if service["name"] == "统计控制台"), None)
        self.assertIsNotNone(stats)
        self.assertEqual(stats["url"], "http://{host}:8080/stats")

        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertIn("live metrics dashboard", body)
        self.assertIn("/stats", body)


if __name__ == "__main__":
    unittest.main()
