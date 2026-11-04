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

    def test_billing(self):
        with patch.object(backend, "_get_json", return_value={
            "billing": {
                "completion": {"models": {"a": {"total_cost": 1.25}, "b": {"total_cost": 2}}},
                "ocr": {"models": {"x": {"total_cost": 0.5}}},
            }
        }):
            self.assertEqual(backend._billing("x=1")["spent"], 3.75)

    def test_vibe(self):
        with patch.object(backend, "_get_json", return_value=[
            {"result": {"data": {"json": {"usage_percentage": 23.5, "reset_at": "2026-12-01"}}}}
        ]):
            result = backend._vibe("x=1")
            self.assertEqual(result["remaining_percent"], 76.5)
            self.assertEqual(result["reset_at"], "2026-12-01")

    def test_invalid_vibe(self):
        with patch.object(backend, "_get_json", return_value=[{"result": {"data": {"json": {}}}}]):
            self.assertFalse(backend._result(backend._vibe, "x=1")["ok"])

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

    def test_independent_failures(self):
        with patch.object(backend, "_read_cookie", return_value="a=1"):
            with patch.object(backend, "_vibe", side_effect=backend.FetchError("vibe down")):
                with patch.object(backend, "_billing", return_value={"ok": True, "spent": 1}):
                    result = backend._collect()
                    self.assertFalse(result["vibe"]["ok"])
                    self.assertTrue(result["api"]["ok"])


if __name__ == "__main__":
    unittest.main()
