"""Local, credential-free history and conservative projections for Mistral budgets.

Stores only usage percentages, monetary totals, currency, reset timestamps and
observation times. NEVER stores a cookie, headers, prompts, account IDs or tokens.
Shared by the Hermes Dashboard backend and read-only Hermes Agent tool.
"""
from __future__ import annotations

import os
import sqlite3
import statistics
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY,
  observed_at TEXT NOT NULL,
  metric TEXT NOT NULL CHECK(metric IN ('api', 'vibe')),
  cycle TEXT NOT NULL,
  used_pct REAL NOT NULL CHECK(used_pct >= 0 AND used_pct <= 100),
  budget REAL NOT NULL CHECK(budget > 0),
  spent REAL NOT NULL CHECK(spent >= 0),
  currency TEXT NOT NULL,
  UNIQUE(observed_at,metric)
);
CREATE INDEX IF NOT EXISTS idx_observations_metric_cycle_time
  ON observations(metric,cycle,observed_at);
"""
MAX_AGE_DAYS = 400


def _utc(text):
    if not isinstance(text, str):
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _path():
    custom = os.environ.get("HERMES_MISTRAL_DATA_DIR")
    root = Path(custom).expanduser() if custom else (
        Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
        / "plugin-data" / "hermes-mistral-usage"
    )
    return root / "usage.sqlite3"


def _connect(create=False):
    path = _path()
    if not create and not path.exists():
        return None
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Refusing symlink for usage history")
    if create:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
    if path.exists():
        st = path.stat()
        if st.st_nlink != 1 or st.st_mode & 0o077:
            raise ValueError("History database needs owner-only permissions")
        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            raise ValueError("History database owner mismatch")
    if create:
        con = sqlite3.connect(str(path), timeout=5)
    else:
        # The Agent-side reader is strictly read-only at SQLite level.
        con = sqlite3.connect("file:" + quote(str(path)) + "?mode=ro", uri=True, timeout=5)
    try:
        if create:
            os.chmod(path, 0o600)
            con.executescript(SCHEMA)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        con.close()
        raise


def record(snapshot):
    """Insert only fresh, successful, validated samples (no credentials)."""
    dt = _utc(snapshot.get("fetched_at"))
    if not dt:
        return False
    rows = []
    for name in ("api", "vibe"):
        metric = snapshot.get(name, {})
        if not isinstance(metric, dict) or not metric.get("ok"):
            return False
        try:
            used, budget, spent = (float(metric[k]) for k in
                                    ("used_percent", "initial_budget", "spent"))
            currency = metric["currency"]
            cycle = metric["reset_at"]
        except (KeyError, TypeError, ValueError):
            return False
        if (not all(map(math.isfinite, [used, budget, spent])) or
                not 0 <= used <= 100 or budget <= 0 or spent < 0 or
                currency not in ("EUR", "USD", "CHF", "GBP") or
                not _utc(cycle)):
            return False
        rows.append((dt.isoformat(), name, cycle, used, budget, spent, currency))
    con = _connect(create=True)
    try:
        with con:
            con.executemany(
                """INSERT OR IGNORE INTO observations
                   (observed_at, metric, cycle, used_pct, budget, spent, currency)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""", rows
            )
            cutoff = (dt - timedelta(days=MAX_AGE_DAYS)).isoformat()
            con.execute("DELETE FROM observations WHERE observed_at < ?", (cutoff,))
    finally:
        con.close()
    return True


def _rows(con, name, cycle, days=30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return list(reversed([dict(x) for x in con.execute(
        """SELECT observed_at, metric, cycle, used_pct, budget, spent, currency
           FROM observations
           WHERE metric=? AND cycle=? AND observed_at>=?
           ORDER BY observed_at DESC LIMIT 12000""",
        (name, cycle, cutoff)
    )]))


def _insight(rows, now=None):
    """Conservative seven-day trend; never treat two observations as a forecast."""
    now = now or datetime.now(timezone.utc)
    if not rows:
        return {"status": "insufficient_history", "samples": 0, "chart": [],
                "anomaly": None}
    latest = rows[-1]
    reset = _utc(latest["cycle"])
    current = latest["used_pct"]
    remaining = max(0.0, latest["budget"] - latest["spent"])
    days_left = max(0.0, (reset - now).total_seconds() / 86400) if reset else None
    daily_allowance = (remaining / days_left if days_left and days_left > 0 else None)

    # Compact chart: one maximal observed value per UTC day, monotone per cycle.
    daily = {}
    for r in rows:
        key = r["observed_at"][:10]
        if key not in daily or r["used_pct"] > daily[key]["used_pct"]:
            daily[key] = r
    chart = [{"day": day, "used_percent": round(r["used_pct"], 4),
              "spent": round(r["spent"], 4)} for day, r in sorted(daily.items())]

    seven = [r for r in rows if _utc(r["observed_at"]) >= now - timedelta(days=7)]
    distinct_days = len({_utc(r["observed_at"]).date() for r in seven})
    first = seven[0] if seven else None
    span_days = (( _utc(seven[-1]["observed_at"]) - _utc(first["observed_at"]) ).total_seconds() / 86400) if first else 0
    rate = ((seven[-1]["used_pct"] - first["used_pct"]) / span_days
            if span_days >= 1 and distinct_days >= 3 and len(seven) >= 3 else None)
    if rate is not None and rate <= 0:
        rate = None
    exhaustion = None
    if rate and current < 100:
        candidate = now + timedelta(days=(100-current)/rate)
        exhaustion = candidate.isoformat() if reset and candidate < reset else None

    # Robust spike test only with enough same-cycle historical increments.
    deltas = []
    for prev, nxt in zip(rows, rows[1:]):
        gap = (_utc(nxt["observed_at"]) - _utc(prev["observed_at"])).total_seconds()/3600
        delta = nxt["used_pct"] - prev["used_pct"]
        if 0 < gap <= 12 and delta >= 0:
            deltas.append((nxt["observed_at"], delta))
    anomaly = None
    if len(deltas) >= 6 and deltas[-1][0] == rows[-1]['observed_at']:
        baseline = [d for _, d in deltas[:-1]]
        current_delta = deltas[-1][1]
        typical = statistics.median(baseline)
        if current_delta >= 0.5 and current_delta >= max(3 * typical, 0.5):
            anomaly = {"at": deltas[-1][0], "delta_percent_points": round(current_delta, 3),
                       "median_delta_percent_points": round(typical, 3)}
    return {
        "status": "ok" if rate is not None else "insufficient_history",
        "samples": len(rows), "latest": {
            "at": latest["observed_at"], "used_percent": current,
            "spent": latest["spent"], "initial_budget": latest["budget"],
            "currency": latest["currency"], "reset_at": latest["cycle"],
        },
        "days_until_reset": round(days_left, 2) if days_left is not None else None,
        "daily_remaining_budget": round(daily_allowance, 3) if daily_allowance is not None else None,
        "daily_usage_rate_pct": round(rate, 4) if rate is not None else None,
        "projected_exhaustion": exhaustion,
        "forecast_note": "Observed seven-day linear rate; not a guarantee." if rate else "Need three distinct days over at least 24 hours.",
        "chart": chart[-90:], "anomaly": anomaly,
    }


def overview(days=30):
    days = max(1, min(90, int(days)))
    con = _connect(create=False)
    if con is None:
        return {"status": "no_history", "api": _insight([]), "vibe": _insight([])}
    try:
        result = {}
        for metric in ("api", "vibe"):
            last = con.execute(
                "SELECT cycle FROM observations WHERE metric=? ORDER BY observed_at DESC LIMIT 1",
                (metric,)
            ).fetchone()
            result[metric] = _insight(_rows(con, metric, last["cycle"], days) if last else [])
        return {"status": "ok", **result}
    finally:
        con.close()
