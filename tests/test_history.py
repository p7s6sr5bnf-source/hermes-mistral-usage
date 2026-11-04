"""Offline local-history tests. No Mistral credentials or real account data."""
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

path = pathlib.Path(__file__).resolve().parents[1] / "usage_history.py"
spec = importlib.util.spec_from_file_location("test_usage_history_module", path)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)


def snapshot(time, used_api=4, used_vibe=2, cycle=None):
    cycle = cycle or (time + timedelta(days=25)).isoformat()
    return {
        "fetched_at": time.isoformat(),
        "api": {"ok": True, "used_percent": used_api, "initial_budget": 100.0,
                "spent": 100.0*used_api/100, "currency": "EUR", "reset_at": cycle},
        "vibe": {"ok": True, "used_percent": used_vibe, "initial_budget": 200.0,
                 "spent": 200*used_vibe/100, "currency": "EUR", "reset_at": cycle},
    }


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"HERMES_MISTRAL_DATA_DIR": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_empty(self):
        info = history.overview()
        self.assertEqual(info["status"], "no_history")

    def test_no_cookies_written(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(history.record(snapshot(now)))
        path = pathlib.Path(self.temp.name) / "usage.sqlite3"
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_mode & 0o077, 0)
        blob = path.read_bytes()
        self.assertNotIn(b"cookie", blob.lower())
        self.assertNotIn(b"token", blob.lower())

    def test_invalid_data_not_recorded(self):
        now = datetime.now(timezone.utc)
        sample = snapshot(now)
        sample["api"]["used_percent"] = 120
        self.assertFalse(history.record(sample))
        self.assertEqual(history.overview()["status"], "no_history")

    def test_forecast_after_multiple_days(self):
        now = datetime.now(timezone.utc)
        reset = (now + timedelta(days=30)).isoformat()
        for i in range(5):
            self.assertTrue(history.record(snapshot(now-timedelta(days=4-i),
                              used_api=10+i*4, used_vibe=2+i, cycle=reset)))
        result = history.overview()
        self.assertEqual(result["status"], "ok")
        api = result["api"]
        self.assertGreater(api["daily_remaining_budget"], 0)
        self.assertAlmostEqual(api["daily_usage_rate_pct"], 4, places=1)
        self.assertIsNotNone(api["projected_exhaustion"])
        self.assertEqual(len(api["chart"]), 5)

    def test_cycle_reset_not_joined(self):
        now = datetime.now(timezone.utc)
        old_cycle = (now-timedelta(days=1)).isoformat()
        new_cycle = (now+timedelta(days=30)).isoformat()
        history.record(snapshot(now-timedelta(days=2), 90, 85, old_cycle))
        history.record(snapshot(now, 1, 1, new_cycle))
        self.assertEqual(history.overview()["api"]["samples"], 1)
        self.assertIsNone(history.overview()["api"]["daily_usage_rate_pct"])

    def test_anomaly_requires_history(self):
        now = datetime.now(timezone.utc)
        reset = (now+timedelta(days=15)).isoformat()
        for i, pct in enumerate([1, 1.1, 1.2, 1.3, 1.4, 1.5, 10]):
            history.record(snapshot(now-timedelta(hours=6*(6-i)),
                                    pct, pct, reset))
        anomaly = history.overview()["api"]["anomaly"]
        self.assertIsNotNone(anomaly)
        self.assertGreater(anomaly["delta_percent_points"], 8)


if __name__ == "__main__":
    unittest.main()
