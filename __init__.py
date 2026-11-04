"""Hermes Mistral Usage - read-only local monitoring tool for Hermes Agent.

The Agent tool NEVER reads the web-session cookie or makes network requests.
It returns sanitized historical totals saved by the trusted backend.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCHEMA = {
    "description": "Read locally recorded Mistral API and Vibe Code subscription usage, reset countdown, and conservative depletion forecast. No live network requests or secrets.",
    "parameters": {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "minimum": 1, "maximum": 90,
                     "description": "Historical analysis window in days (default 30)."}
        },
        "additionalProperties": False,
    },
}


def _history():
    path = Path(__file__).resolve().parent / "usage_history.py"
    spec = importlib.util.spec_from_file_location("hermes_mistral_agent_history", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _handle(args, **kwargs):
    del kwargs
    from tools.registry import tool_result, tool_error
    days = args.get("days", 30)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 90:
        return tool_error("days must be an integer between 1 and 90")
    try:
        data = _history().overview(days)
    except (OSError, RuntimeError, ValueError):
        return tool_error("Local Mistral usage history is unavailable")
    # Avoid unrestricted serialisation and never return local paths or cookies.
    for metric in ("api", "vibe"):
        item = data.get(metric, {})
        item.pop("chart", None)
    return tool_result(data)


def register(ctx):
    ctx.register_tool(
        name="mistral_usage_status",
        toolset="mistral_usage",
        schema=SCHEMA,
        handler=_handle,
        description="Get the local Mistral Vibe/API budget history, anomaly and forecast without reading credentials.",
    )
