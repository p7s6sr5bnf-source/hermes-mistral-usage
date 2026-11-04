import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"
spec = importlib.util.spec_from_file_location("mistral_backend", MODULE)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class BackendTests(unittest.TestCase):
    def test_csrf(self):
        self.assertEqual(backend._csrf("a=1; csrftoken=hello; b=2"), "hello")
        self.assertIsNone(backend._csrf("a=1"))

    def test_no_cookie(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"MISTRAL_USAGE_COOKIE": "", "MISTRAL_USAGE_COOKIE_FILE": folder + "/absent"}):
                result = backend._collect()
                self.assertFalse(result["configured"])

    def test_private_cookie_file(self):
        with tempfile.TemporaryDirectory() as folder:
            p = pathlib.Path(folder) / "cookie"
            p.write_text("a=1")
            p.chmod(0o600)
            with patch.dict(os.environ, {"MISTRAL_USAGE_COOKIE": "", "MISTRAL_USAGE_COOKIE_FILE": str(p)}):
                self.assertEqual(backend._read_cookie(), "a=1")
                p.chmod(0o644)
                with self.assertRaises(backend.FetchError):
                    backend._read_cookie()

    def test_reject_symlink_cookie(self):
        with tempfile.TemporaryDirectory() as folder:
            real = pathlib.Path(folder) / "real"
            link = pathlib.Path(folder) / "link"
            real.write_text("session=123")
            real.chmod(0o600)
            link.symlink_to(real)
            with patch.dict(os.environ, {"MISTRAL_USAGE_COOKIE": "", "MISTRAL_USAGE_COOKIE_FILE": str(link)}):
                with self.assertRaises(backend.FetchError):
                    backend._read_cookie()

    def test_redirect_does_not_follow_credential_bearing_request(self):
        from urllib.request import Request
        self.assertIsNone(backend.NoRedirects().redirect_request(
            Request("https://admin.mistral.ai/"), None, 302, "moved", {}, "https://example.org/"))

    def test_subscription_budget_schema(self):
        item = backend._budget_item({
            "usage_percentage": 1.86366963, "initial_budget": 100.0,
            "currency": "EUR", "reset_at": "2026-12-01T00:00:00Z"
        })
        self.assertTrue(item["ok"])
        self.assertAlmostEqual(item["spent"], 1.86367, places=5)
        self.assertAlmostEqual(item["remaining_percent"], 98.13633037, places=5)

    def test_subscription_budgets(self):
        payload = {"result": {"data": {"json": {
            "api_budget": {"usage_percentage": 1, "initial_budget": 100.0, "currency": "EUR"},
            "vibe_budget": {"usage_percentage": 0.5, "initial_budget": 200, "currency": "EUR"}
        }}}}
        with patch.object(backend, "_get_json", return_value=payload):
            api, vibe = backend._subscription_budgets("x=1")
            self.assertEqual(api["initial_budget"], 100.0)
            self.assertEqual(vibe["initial_budget"], 200)

    def test_budget_url_is_fixed_and_uses_https(self):
        url = backend._budget_url()
        self.assertTrue(url.startswith("https://admin.mistral.ai/api/local-trpc/billing.budget?input="))
        with patch.dict(os.environ, {"MISTRAL_SUBSCRIPTION_BUDGET_URL": "https://evil.example/"}):
            self.assertEqual(backend._budget_url(), url)


if __name__ == "__main__":
    unittest.main()
