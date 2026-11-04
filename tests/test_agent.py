"""Read-only Hermes Agent tool integration contract, with fake data only."""
import importlib.util
import os
import pathlib
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mistral_agent_entry", ROOT / "__init__.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
hspec = importlib.util.spec_from_file_location("test_agent_history", ROOT / "usage_history.py")
history = importlib.util.module_from_spec(hspec)
hspec.loader.exec_module(history)


class FakeCtx:
    def __init__(self):
        self.tool = None

    def register_tool(self, **kwargs):
        self.tool = kwargs


class AgentToolTests(unittest.TestCase):
    def test_registers_single_read_only_tool(self):
        ctx = FakeCtx()
        agent.register(ctx)
        self.assertEqual(ctx.tool["name"], "mistral_usage_status")
        self.assertNotIn("cookie", ctx.tool["schema"]["parameters"]["properties"])
        self.assertNotIn("refresh", ctx.tool["schema"]["parameters"]["properties"])

    def test_reads_local_metrics_without_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"HERMES_MISTRAL_DATA_DIR": folder}):
                now = datetime.now(timezone.utc)
                reset = (now + timedelta(days=20)).isoformat()
                sample = {
                    "fetched_at": now.isoformat(),
                    "api": {"ok": True, "used_percent": 5, "initial_budget": 100.0,
                            "spent": 5.0, "currency": "EUR", "reset_at": reset},
                    "vibe": {"ok": True, "used_percent": 10, "initial_budget": 200,
                             "spent": 20.0, "currency": "EUR", "reset_at": reset},
                }
                history.record(sample)
                # Do not require a real Hermes installation for the contract test.
                pkg = types.ModuleType("tools")
                registry = types.ModuleType("tools.registry")
                registry.tool_result = lambda data: data
                registry.tool_error = lambda message: {"error": message}
                with patch.dict(sys.modules, {"tools": pkg, "tools.registry": registry}):
                    output = agent._handle({"days": 7})
                self.assertEqual(output["api"]["latest"]["used_percent"], 5)
                self.assertEqual(output["vibe"]["latest"]["used_percent"], 10)
                self.assertNotIn("chart", output["api"])
                self.assertNotIn("cookie", repr(output).lower())


if __name__ == "__main__":
    unittest.main()
