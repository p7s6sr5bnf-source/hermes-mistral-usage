# Hermes Mistral Usage

A standalone **Hermes Agent + Hermes Desktop** plugin for **Linux and macOS**.
Native sidebar page and status-bar chip display the **included Mistral subscription budgets** for API and Vibe Code, using `billing.budget`. No token estimates, no LLM calls, no changes to configured model providers.

> **Status: V0.2 candidate, not yet tested against a real Mistral account.** The response mapping is supported by a redacted live account example. The exact network Request URL still needs to be supplied; the endpoint is unofficial.

## Install (from repository)

In Hermes Desktop, use **Capabilities → Plugins → Install from Git** and enter
`p7s6sr5bnf-source/hermes-mistral-usage`. The GitHub connection must have
permission to access this **private** repository.

Alternatively on a machine with GitHub access:

```bash
hermes plugins install p7s6sr5bnf-source/hermes-mistral-usage --enable
```

Enable **Desktop** separately in **Capabilities → Plugins**, then open the
**Mistral Usage** sidebar tab. Hermes >= 0.21.2 is required.
For testing the feature branch directly, clone it and install it as a local
plugin directory. Do **not** use the main branch until the PR is merged.

## Configure the Mistral web session (on each backend host)

No API key can fetch these subscriber-level metrics. The plugin uses the
authenticated **web Cookie header** for Mistral Console/Admin. **Never paste
your cookie into chat, GitHub, Hermes agent prompts, a URL or a shell command.**

1. Log in to Mistral Console in your own browser.
2. In browser Developer Tools → Network, inspect an authenticated request to
   `console.mistral.ai` or `admin.mistral.ai`; copy the **Cookie request header**
   using local clipboard only. Be aware some cookies may be host-specific:
   successful access to both endpoints is not guaranteed.
3. On the **machine running the Hermes backend**, execute:
   ```bash
   python3 scripts/configure.py
   ```
   and paste the cookie at the hidden prompt. This creates
   `~/.config/hermes-mistral-usage/session.cookie` with mode 0600. If you
   install on Linux and macOS independently, configure the session **separately**
   on both machines.
4. In DevTools Network → select `billing.budget` → Headers → General,
   copy the exact **Request URL**. Configure it in the **trusted backend process**
   as `MISTRAL_SUBSCRIPTION_BUDGET_URL`. Only HTTPS requests to
   `admin.mistral.ai` with a path ending in `/billing.budget` are accepted.
   The exact URL (including `input`) has not yet been confirmed and is not
   hardcoded. Check that the query string contains no sensitive tokens before
   storing it in an environment variable.
5. Restart/reload the Hermes backend if necessary, and enable the plugin in
   Hermes Desktop. The view refreshes automatically every 5 minutes.

For deployment without the helper script, supply `MISTRAL_USAGE_COOKIE` as an
environment variable **only to the trusted backend process**, or specify the
`MISTRAL_USAGE_COOKIE_FILE` path to an owner-only regular file. Environment
variables can be exposed to local process administrators; prefer the file.

## UI and monitoring

- Vibe Code: included budget, used / remaining percentages and reset time.
- API: included budget, used / remaining percentages and reset time.
- Both derive from the same subscription budget response; an endpoint failure makes both unavailable.
- Pay-as-you-go is deliberately excluded; no per-key consumption is claimed.
- Status bar: Vibe remaining percentage, or a dash if unavailable.
- Automatic refresh every five minutes. Shared cache TTL = 300 s; manual
  refresh observes a minimum 30 s interval.
- Timestamps for last successful poll; distinct error and cached states.

**Scope:** this is an organization/subscription view. Two API keys in one
organization do not necessarily correspond to two separately reported budgets.
The plugin does not claim per-key consumption.

## Privacy / security

- Backend reads a private local cookie; Desktop renderer receives only
  aggregate numeric data and sanitized error text.
- No cookies, API keys, conversations or prompts are stored in GitHub.
- Outbound requests go only to Mistral's fixed HTTPS hosts.
- Redirects are disabled for credential-bearing requests.
- The cookie file must be regular, owned by the current user, and mode 0600.
- Do not enable the backend route on an unauthenticated publicly accessible
  Hermes dashboard. Hermes must enforce authentication for plugin API endpoints.
- This is a **web-session integration**, not an official Mistral API. Expiration,
  revocation, CSRF rules and endpoint schema may change.

## Development / checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile dashboard/plugin_api.py
node --check desktop/plugin.js
hermes plugins validate .
```

The first three checks require Python with `fastapi` (usually supplied by
Hermes) and Node.js; `hermes plugins validate` requires a compatible Hermes
installation. Live authenticated testing must be performed locally; CI must
never have a production web-session cookie.

## Confirmed subscription schema

`billing.budget` returns `result.data.json.api_budget` and `vibe_budget`, each with `usage_percentage`, `initial_budget`, `currency` and `reset_at`. The top-level percentage is **not** a third independent budget. The `billing.usageLimits` response represents Pay-as-you-go and is not used.

## Origins

The endpoint approach was identified in
[UsageBar](https://github.com/lfmundim/UsageBar). See [THIRD_PARTY.md](THIRD_PARTY.md).
