"""Tests for the /api/health and /api/admin/health endpoints."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthEndpoint(unittest.TestCase):
    def setUp(self):
        # Minimal Flask app setup — import app only after path is set
        os.environ.setdefault('SECRET_KEY', 'test-secret')

        from routes.health import health_bp
        from flask import Flask
        self.app = Flask(__name__)
        self.app.register_blueprint(health_bp)
        self.app.secret_key = 'test-secret'
        self.client = self.app.test_client()

    # ---- Public /api/health tests ----

    def test_health_returns_200(self):
        resp = self.client.get('/api/health')
        self.assertEqual(resp.status_code, 200)

    def test_health_returns_json(self):
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertIsNotNone(data)

    def test_health_status_is_ok(self):
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertEqual(data.get('status'), 'ok')

    def test_health_has_uptime(self):
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertIn('uptime', data)
        self.assertIsInstance(data['uptime'], (int, float))
        self.assertGreaterEqual(data['uptime'], 0)

    def test_health_does_not_leak_version(self):
        """Public endpoint must NOT expose version info."""
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertNotIn('version', data)

    def test_health_does_not_leak_checks(self):
        """Public endpoint must NOT expose checks (docker, disk, db detail)."""
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertNotIn('checks', data)

    def test_health_does_not_leak_docker(self):
        """Public endpoint must NOT expose docker_version."""
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertNotIn('docker_version', data)
        self.assertNotIn('docker', data)

    def test_health_does_not_leak_disk(self):
        """Public endpoint must NOT expose disk_usage."""
        resp = self.client.get('/api/health')
        data = resp.get_json()
        self.assertNotIn('disk_usage', data)
        self.assertNotIn('disk', data)

    # ---- Admin /api/admin/health tests ----

    def test_admin_health_requires_auth(self):
        """Admin health endpoint must return 401 without auth."""
        resp = self.client.get('/api/admin/health')
        self.assertEqual(resp.status_code, 401)

    def test_admin_health_returns_details_when_authenticated(self):
        """Admin health endpoint must return full details when authenticated."""
        with self.client.session_transaction() as sess:
            sess['authenticated'] = True
        resp = self.client.get('/api/admin/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('version', data)
        self.assertIn('checks', data)
        self.assertIn('disk', data['checks'])
        self.assertIn('docker', data['checks'])
        self.assertIn('database', data['checks'])

    def test_admin_health_version_from_file(self):
        """Admin health must read version from VERSION file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='VERSION',
                                         delete=False, dir='/tmp') as f:
            f.write('v1.2.3')
            fname = f.name

        import routes.health as health_mod
        orig_fn = health_mod._get_version

        def _patched():
            with open(fname) as f:
                return f.read().strip()

        health_mod._get_version = _patched
        try:
            with self.client.session_transaction() as sess:
                sess['authenticated'] = True
            resp = self.client.get('/api/admin/health')
            data = resp.get_json()
            self.assertEqual(data['version'], 'v1.2.3')
        finally:
            health_mod._get_version = orig_fn
            os.unlink(fname)

    def test_admin_health_still_has_status_and_uptime(self):
        """Admin health must also include status and uptime."""
        with self.client.session_transaction() as sess:
            sess['authenticated'] = True
        resp = self.client.get('/api/admin/health')
        data = resp.get_json()
        self.assertIn('status', data)
        self.assertIn('uptime', data)


if __name__ == '__main__':
    unittest.main()
