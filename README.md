# Hermes Mistral Usage

A standalone **Hermes Agent + Hermes Desktop** plugin for **Linux and macOS**.
Native sidebar page and status-bar chip display the **included Mistral subscription budgets** for API and Vibe Code, using `billing.budget`. No token estimates, no LLM calls, no changes to configured model providers.

> **Status: V0.2.1 candidate, not yet tested against a real Mistral account.** The response mapping is supported by a redacted live account example. The exact billing.budget Request URL was confirmed from browser DevTools; this remains an unofficial endpoint.

## Install (from repository)

In Hermes Desktop, use **Capabilities → Plugins → Install from Git** and enter
`p7s6sr5bnf-source/hermes-mistral-usage`. If the repository is private, the Hermes environment must already have
GitHub access. If the owner switches it to public, no GitHub credentials
should be required to clone.

Alternatively on a machine with GitHub access:

```bash
hermes plugins install p7s6sr5bnf-source/hermes-mistral-usage --enable
```

Enable **Desktop** separately in **Capabilities → Plugins**, then open the
**Mistral Usage** sidebar tab. Hermes >= 0.21.2 is required.
For manual/offline installation, follow the official Hermes documentation for
local package discovery (the CLI command `hermes plugins install .` does not
accept local paths).

## Configure the Mistral web session (on each backend host)

No API key can fetch these subscriber-level metrics. The plugin uses the
authenticated **web Cookie header** for Mistral Console/Admin. **Never paste
your cookie into chat, GitHub, Hermes agent prompts, a URL or a shell command.**

1. Log in to **Mistral Admin** in your own browser.
2. In browser Developer Tools → Network, select the authenticated
   `billing.budget` request to `admin.mistral.ai` and copy its **Cookie request header**
   using local clipboard only. Do not send a screenshot showing the header.
3. On the **machine running the Hermes backend**, execute:
   ```bash
   python3 scripts/configure.py
   ```
   and paste the cookie at the hidden prompt. This creates
   `~/.config/hermes-mistral-usage/session.cookie` with mode 0600. If you
   install on Linux and macOS independently, configure the session **separately**
   on each trusted backend machine. The cookie is a privileged browser session
   credential, not a read-only scoped API token.
4. The observed `billing.budget` URL is already embedded in the plugin. No URL environment variable is required.
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

**Making this GitHub repository public does not make your cookie public.**
The repository contains no authentic session data. Before changing visibility,
scan all historical commits and branches for accidentally committed secrets.
Any previously leaked session must be revoked; adding .gitignore does not
remove secrets from Git history.


- Backend reads a private local cookie; Desktop renderer receives only
  aggregate numeric data and sanitized error text.
- No cookies, API keys, conversations or prompts are stored in GitHub.
- Outbound requests go only to Mistral's fixed HTTPS hosts.
- Redirects are disabled for credential-bearing requests.
- The cookie file must be regular, owned by the current user, mode 0600,
  and not a symlink or hard-linked file. It is **not encrypted at rest**.
- An attacker with the backend process's user permissions can read this
  cookie and potentially impersonate the Mistral browser session.
- The plugin cannot renew the cookie automatically; expiration and 302
  redirects require a fresh locally supplied browser session.
- Prefer running this on a dedicated, trusted machine and **not** on a
  multi-tenant or publicly reachable Hermes backend.
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
