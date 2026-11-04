"""Hermes plugin backend: read-only Mistral billing and Vibe quota.

Browser-session endpoints are unofficial and may change. Cookies are read only
from the backend process environment or a private host-local file. Never send
credentials to the Desktop renderer or persist them in the plugin repository.
"""
from __future__ import annotations

import json
import os
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import APIRouter

router = APIRouter()
CACHE_SECONDS = 300
MIN_REFRESH_SECONDS = 30
MAX_RESPONSE_BYTES = 2_000_000
BILLING_URL = "https://admin.mistral.ai/api/billing/v2/usage"
VIBE_URL = (
    "https://console.mistral.ai/api-ui/trpc/billing.vibeUsage?"
    "batch=1&input=%7B%220%22%3A%7B%22json%22%3Anull%7D%7D"
)
_lock = threading.Lock()
_cache = None
_cache_time = 0.0


class FetchError(Exception):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Prevent authentication cookies leaking to a redirect target.
        return None


def _cookie_path():
    override = os.environ.get("MISTRAL_USAGE_COOKIE_FILE")
    return Path(override).expanduser() if override else (
        Path.home() / ".config" / "hermes-mistral-usage" / "session.cookie"
    )


def _read_cookie():
    env = os.environ.get("MISTRAL_USAGE_COOKIE", "").strip()
    if env:
        return _validate_cookie(env)
    path = _cookie_path()
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise FetchError("Cookie file must be regular and mode 0600.")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise FetchError("Cookie file must be owned by the current user.")
    return _validate_cookie(path.read_text(encoding="utf-8").strip())


def _validate_cookie(cookie):
    if not cookie or "\r" in cookie or "\n" in cookie or len(cookie) > 16000:
        raise FetchError("Cookie is missing or invalid.")
    if not any("=" in part for part in cookie.split(";")):
        raise FetchError("Expected a Cookie header (name=value pairs).")
    return cookie


def _csrf(cookie):
    for item in cookie.split(";"):
        key, sep, value = item.strip().partition("=")
        if sep and key.lower() == "csrftoken":
            return value
    return None


def _get_json(url, cookie, referer, timeout):
    headers = {
        "Accept": "application/json",
        "Cookie": cookie,
        "Referer": referer,
        "User-Agent": "hermes-mistral-usage/0.1",
    }
    csrf = _csrf(cookie)
    if csrf:
        headers["X-CSRFToken"] = csrf
    request = Request(url, headers=headers, method="GET")
    try:
        response = build_opener(NoRedirects).open(request, timeout=timeout)
        with response:
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise FetchError("Mistral returned non-JSON content.")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise FetchError("Mistral response too large.")
            return json.loads(raw)
    except HTTPError as exc:
        # Never include response bodies, URLs or request headers in errors.
        if exc.code in (401, 403):
            raise FetchError("Mistral session expired or unauthorized.") from None
        if exc.code == 429:
            raise FetchError("Mistral rate limit; retry later.") from None
        raise FetchError("Mistral HTTP error " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        raise FetchError("Mistral request or JSON response failed.") from None


def _billing(cookie):
    now = datetime.now().astimezone()
    url = BILLING_URL + "?" + urlencode({"month": now.month, "year": now.year})
    result = _get_json(url, cookie, "https://admin.mistral.ai/organization/usage", 15)
    billing = result.get("billing") if isinstance(result, dict) else None
    if not isinstance(billing, dict):
        raise FetchError("Mistral billing schema changed or missing.")
    total = 0.0
    model_count = 0
    for category in billing.values():
        if not isinstance(category, dict):
            continue
        models = category.get("models", {})
        if not isinstance(models, dict):
            continue
        for model in models.values():
            if not isinstance(model, dict):
                continue
            cost = model.get("total_cost")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                total += float(cost)
                model_count += 1
    if model_count == 0:
        # Empty billing may be legitimate; report zero only for empty category sets.
        if any(isinstance(c, dict) and c.get("models") for c in billing.values()):
            raise FetchError("Mistral billing cost fields unavailable.")
    return {
        "ok": True, "spent": round(total, 6),
        "currency": "unspecified", "month": now.month, "year": now.year,
        "scope": "organization", "source": "mistral-web-session",
    }


def _vibe(cookie):
    result = _get_json(
        VIBE_URL, cookie, "https://console.mistral.ai/codestral/cli", 10
    )
    try:
        data = result[0]["result"]["data"]["json"]
        used = data["usage_percentage"]
    except (KeyError, IndexError, TypeError):
        raise FetchError("Mistral Vibe response schema changed.") from None
    if not isinstance(used, (int, float)) or isinstance(used, bool) or not 0 <= used <= 100:
        raise FetchError("Mistral Vibe percentage invalid.")
    return {
        "ok": True, "used_percent": float(used),
        "remaining_percent": round(100.0 - float(used), 2),
        "reset_at": data.get("reset_at"), "scope": "subscription",
        "source": "mistral-web-session",
    }


def _result(fn, cookie):
    try:
        return fn(cookie)
    except FetchError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        # Do not expose untrusted API response or exception details to UI/logs.
        return {"ok": False, "error": "Unexpected Mistral response error."}


def _budget_item(value):
    if not isinstance(value, dict):
        raise FetchError("Mistral subscription budget section missing.")
    pct = value.get("usage_percentage")
    amount = value.get("initial_budget")
    currency = value.get("currency")
    if (not isinstance(pct, (float, int)) or isinstance(pct, bool)
            or not 0 <= pct <= 100 or not isinstance(amount, (int, float))
            or isinstance(amount, bool) or amount <= 0
            or currency not in ("EUR", "USD", "GBP", "CHF")):
        raise FetchError("Mistral subscription budget fields invalid.")
    return {
        "ok": True, "used_percent": float(pct),
        "remaining_percent": round(100 - float(pct), 6),
        "initial_budget": float(amount),
        "spent": round(float(amount) * float(pct) / 100, 6),
        "remaining": round(float(amount) * (100 - float(pct)) / 100, 6),
        "currency": currency, "reset_at": value.get("reset_at"),
        "scope": "subscription", "source": "mistral-web-session",
    }


def _budget_url():
    # Observed in Mistral Admin DevTools, November 2026.
    # Unofficial endpoint; no user-controlled host or query parameters.
    return "https://admin.mistral.ai/api/local-trpc/billing.budget?input=%7B%22json%22%3Anull%2C%22meta%22%3A%7B%22values%22%3A%5B%22undefined%22%5D%2C%22v%22%3A1%7D%7D"


def _subscription_budgets(cookie):
    url = _budget_url()
    response = _get_json(url, cookie, "https://admin.mistral.ai/", 15)
    try:
        data = response["result"]["data"]["json"]
    except (KeyError, TypeError):
        raise FetchError("Mistral subscription budget response schema changed.") from None
    if not isinstance(data, dict):
        raise FetchError("Mistral subscription budget response invalid.")
    return _budget_item(data.get("api_budget")), _budget_item(data.get("vibe_budget"))


def _collect():
    try:
        cookie = _read_cookie()
    except FetchError as exc:
        return {"configured": False, "vibe": {"ok": False, "error": str(exc)},
                "api": {"ok": False, "error": str(exc)}, "fetched_at": None}
    if not cookie:
        return {"configured": False, "vibe": {"ok": False, "error": "Configure a Mistral session cookie."},
                "api": {"ok": False, "error": "Configure a Mistral session cookie."}, "fetched_at": None}
    try:
        api, vibe = _subscription_budgets(cookie)
    except FetchError as exc:
        return {"configured": True, "vibe": {"ok": False, "error": str(exc)},
                "api": {"ok": False, "error": str(exc)}, "fetched_at": None}
    except Exception:
        return {"configured": True, "vibe": {"ok": False, "error": "Unexpected subscription budget response."},
                "api": {"ok": False, "error": "Unexpected subscription budget response."}, "fetched_at": None}
    return {
        "configured": True, "vibe": vibe, "api": api,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_usage(force=False):
    global _cache, _cache_time
    now = time.monotonic()
    if _cache is not None and now - _cache_time < (MIN_REFRESH_SECONDS if force else CACHE_SECONDS):
        return dict(_cache, cached=True)
    with _lock:
        now = time.monotonic()
        if _cache is not None and now - _cache_time < (MIN_REFRESH_SECONDS if force else CACHE_SECONDS):
            return dict(_cache, cached=True)
        data = _collect()
        _cache, _cache_time = data, time.monotonic()
        return dict(data, cached=False)


@router.get("/usage")
def usage(refresh: bool = False):
    return get_usage(force=refresh)


@router.get("/health")
def health():
    # Never include the cookie, headers, account IDs or billing amounts here.
    return {"ok": True, "version": "0.1.0", "configured": bool(os.environ.get("MISTRAL_USAGE_COOKIE")) or _cookie_path().exists()}
