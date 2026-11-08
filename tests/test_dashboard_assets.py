"""Contract checks for Dashboard assets; synthetic, no network or credentials."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


class DashboardAssetsTests(unittest.TestCase):
    def test_page_manifest_references_shipped_bundle(self):
        manifest = json.loads((DASHBOARD / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "hermes-mistral-usage")
        self.assertEqual(manifest["tab"]["path"], "/mistral-usage")
        self.assertEqual(manifest["api"], "plugin_api.py")
        entry = (DASHBOARD / manifest["entry"]).resolve()
        self.assertTrue(entry.is_relative_to(DASHBOARD.resolve()))
        self.assertTrue(entry.is_file())
        self.assertTrue(entry.read_text(encoding="utf-8").strip())

    def test_bundle_registers_page_and_does_not_handle_browser_secrets(self):
        source = (DASHBOARD / "dist/index.js").read_text(encoding="utf-8")
        self.assertIn('registry.register("hermes-mistral-usage", Page)', source)
        self.assertIn('SDK.fetchJSON(API_ROOT + "/usage"', source)
        self.assertIn('SDK.fetchJSON(API_ROOT + "/insights', source)
        self.assertNotIn("admin.mistral.ai", source)
        self.assertNotIn("MISTRAL_USAGE_COOKIE", source)
        self.assertNotIn("document.cookie", source)
        self.assertNotIn("window.localStorage", source)


if __name__ == "__main__":
    unittest.main()
