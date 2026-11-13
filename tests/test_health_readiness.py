import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.misc_routes import misc_bp


class HealthReadinessTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(misc_bp)
        self.client = app.test_client()

    def test_health_is_liveness_and_does_not_require_database(self):
        with patch("app.misc_routes._database_probe", return_value=False):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_ready_returns_503_when_database_is_unavailable(self):
        with patch("app.misc_routes._database_probe", return_value=False):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "not_ready")
        self.assertEqual(response.get_json()["database"], "unavailable")

    def test_ready_returns_200_when_database_is_available(self):
        with patch("app.misc_routes._database_probe", return_value=True):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ready")

    def test_metrics_closes_connection_and_reports_failed_counts_as_unavailable(self):
        connection = MagicMock()
        connection.execute.side_effect = RuntimeError("database locked")
        with patch("app.misc_routes._db_conn", return_value=connection):
            response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["database"], "unavailable")
        self.assertIsNone(response.get_json()["daily"])
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
