# Hermes Mistral Usage

[![Version](https://img.shields.io/badge/version-0.4.0-blue)](plugin.yaml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A **read-only Mistral subscription quota monitor** for Hermes Desktop and Hermes Agent on Linux and macOS. It tracks the included **Vibe Code** and **API** budgets using Mistral's authenticated browser endpoint.

The plugin does **not** use a model, change billing settings, switch providers, or spend API credits.

> **Compatibility:** Hermes >= 0.21.2. Mistral's `billing.budget` endpoint is undocumented and can change without notice. Real-world compatibility depends on the installed Hermes version and an active Mistral web session. Linux CI has passed; Desktop/Agent integration and macOS should be verified on the target installation.

## Features

| Feature | Hermes Desktop | Hermes Agent |
| --- | --- | --- |
| Vibe Code / API subscription usage | Live budget readout | Latest saved observation |
| Used or remaining balance, percent or currency | Configurable | Numeric values |
| Status bar, green / amber / red thresholds | Yes | — |
| Local historical observations and daily charts | 7 / 30 / 90-day selection | Local history summary |
| Renewal date and daily budget allowance | Yes | Yes |
| Conservative exhaustion projection | Yes | Yes |
| Unusual consumption detection | Native alert when enabled | Read-only anomaly result |
| Account changes or automatic model switching | **No** | **No** |

The included API and Vibe budgets are separate from **pay-as-you-go** usage. No per-key consumption is available.

## Installation

### Hermes Desktop

1. Open **Capabilities → Plugins → Install from Git**.
2. Enter `p7s6sr5bnf-source/hermes-mistral-usage`.
3. Enable the plugin's Desktop component.
4. Open **Mistral Usage** from the sidebar. Its preferences are under **Settings → Plugins → Mistral Usage**.

The Desktop view requests usage from the Hermes plugin API. A backend with a valid Mistral session must be configured for live readings.

### Hermes Agent (CLI)

Install in the **same Hermes environment and user profile that runs the Agent**:

```bash
hermes plugins install p7s6sr5bnf-source/hermes-mistral-usage --enable
```

To update an existing installation:

```bash
hermes plugins update hermes-mistral-usage
hermes plugins enable hermes-mistral-usage
```

Check registration:

```bash
hermes plugins list
hermes plugins doctor hermes-mistral-usage
```

Restart the Hermes Agent/Gateway process after enabling the Python component. A new CLI session can then call **`mistral_usage_status`** (optional `days` argument: integer from 1 to 90, default 30).

Example prompt:

> Use the mistral_usage_status tool to summarize my latest saved Mistral API and Vibe Code usage, renewal date, daily allowance, and any available forecast.

**Important:** The Agent tool does **not** log in to Mistral, read cookies, or fetch live balances. It reads only the local history written by a configured backend. Installing only the CLI tool does not create or populate this history. The tool may report no data until a successful fresh backend collection occurs.

If separate Hermes processes must access the same history, they must point to the same **trusted local data directory**; otherwise, histories remain independent. No shared storage or additional infrastructure is required for a single Hermes installation.

## Configure the Mistral session

No documented scoped API credential exposes the subscription's `billing.budget` values. The current implementation uses an authenticated **browser session cookie**, which can grant account-level access and must be treated as a secret.

1. Sign in to [Mistral Admin](https://admin.mistral.ai/).
2. In your browser's developer tools, open **Network**, filter for `billing.budget`, and select a successful request to `admin.mistral.ai`.
3. Under **Request Headers**, copy the **complete value of the `Cookie` header**. Do **not** copy the `Set-Cookie` response header or send a HAR/cURL capture to anyone.
4. Run the helper **locally on the trusted backend host** from the cloned repository or installed plugin directory:

   ```bash
   python3 scripts/configure.py
   ```

5. Paste the cookie at the hidden prompt. Restart the backend if necessary, then refresh Mistral Usage.

The helper saves `~/.config/hermes-mistral-usage/session.cookie` with owner-only permissions (`0600`). The cookie stays local; it is neither committed to Git nor passed to the Desktop renderer or Agent tool. It is **not encrypted at rest**.

Alternative settings for the backend process:

| Variable | Purpose |
| --- | --- |
| `MISTRAL_USAGE_COOKIE_FILE` | Path to a trusted owner-only cookie file |
| `MISTRAL_USAGE_COOKIE` | Cookie supplied as an environment variable (less desirable: may be visible to process administrators) |
| `HERMES_HOME` | Hermes home directory used for the default history path |
| `HERMES_MISTRAL_DATA_DIR` | Optional directory containing the history database |

These variables do not belong in the public repository. Do not put credentials in issues, pull requests, agent prompts, logs, screenshots, or shell arguments.

**Session expiration:** the plugin does not auto-renew sessions. A redirect or unauthorized response can mean the browser session expired or was revoked. Retrieve a fresh cookie locally if needed.

## Monitoring and preferences

Under **Settings → Plugins → Mistral Usage**, configure:

- Display **used** (default) or **remaining** balance.
- Display a **percentage** (default) or the subscription currency amount.
- Show or hide the Vibe and API indicators.
- Enable/disable status colors. Green = normal; amber = at least 80% of the alert threshold; red = at or above the threshold.
- Set independent Vibe/API thresholds (1–100% **used**, default 80%).
- Enable/disable native OS notifications and anomalous-use alerts.
- Select a 7-, 30-, or 90-day history window, and a 5-, 10-, 15-, or 30-minute Desktop polling interval.

The backend caches normal reads for 5 minutes and applies a 30-second minimum interval to manual refreshes. Notifications are deduplicated per event and are generated only while the Desktop plugin is running and notifications are allowed by the OS. Preferences are stored locally by Hermes Desktop.

## History, forecasts, and data retention

Successful **fresh** authenticated backend reads append numeric observations to:

```text
$HERMES_HOME/plugin-data/hermes-mistral-usage/usage.sqlite3
```

The default Hermes home is `~/.hermes`. Alternatively, set `HERMES_MISTRAL_DATA_DIR` to a dedicated local directory. History is stored outside the plugin's installation tree, so plugin updates do not delete it. Database permissions are restricted to the owning user; records older than 400 days are pruned on subsequent writes.

The database contains **only** observation timestamps, metric names, renewal timestamps, percentages, currency, and aggregate monetary amounts. It contains **no** cookies, tokens, prompts, conversations, or account identifiers.

**How the 7/30/90-day selector works:** it selects the *maximum lookback window for recorded observations*, **not** a request for historical data from Mistral. The current implementation plots the latest subscription cycle only; previous renewal cycles are not stitched into the current chart. The plugin cannot reconstruct earlier readings that were never recorded.

**Forecasts:** the remaining daily allowance is the current unspent budget divided by the time left until renewal. A seven-day linear extrapolation requires at least three distinct days of observations spanning 24 hours. A forecast is only shown when the extrapolated exhaustion precedes renewal; it is an estimate, not a promise.

**Anomalies:** detection needs at least six consecutive valid increases within 12-hour sample gaps. The most recent increase must be at least 0.5 percentage points and at least three times the median of the previous increments. Low-frequency sampling can miss short spikes. Notifications are not a server-side background monitor.

**Agent privacy:** when an Agent invokes `mistral_usage_status`, the resulting aggregate figures can be sent to the model provider serving the conversation. The cookie itself is never read by that tool.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `302` / redirect or unauthorized | The session cookie may have expired, been revoked, or be for a different scope. Repeat the local configuration using the exact `billing.budget` request. |
| Desktop says backend unavailable | Verify the Hermes backend/profile is reachable and the plugin backend is enabled; restart/reload it. |
| Agent cannot find `mistral_usage_status` | Verify the plugin is enabled in the Agent's own environment and restart the process. |
| Agent returns `no_history` | It reads saved data only. Check that a fresh authenticated backend collection occurred and both processes can access the same history directory. |
| Graph shows no line | Initial readings may be missing or only one day is recorded. The selector does not backfill previous months. |
| No native notification | Check the threshold, notification preference, Desktop runtime, and OS notification permissions. |
| History unavailable | Check the history directory's existence, owner, `0700` directory permissions, and `0600` SQLite file permissions. |

## Development

Run from the repository root:

```bash
python3 -m pip install fastapi
python3 -m unittest discover -s tests -v
python3 -m py_compile dashboard/plugin_api.py usage_history.py __init__.py scripts/configure.py
node --check desktop/plugin.js
hermes plugins validate .
```

The tests use synthetic account data and do not contact Mistral or require credentials. GitHub Actions checks are **manual-only** (`workflow_dispatch`) while integration is being validated; this does not constitute macOS certification.

## Security, contributions and licensing

Read [SECURITY.md](SECURITY.md) before reporting an issue. Use synthetic or redacted diagnostic information, and **never disclose a live browser session**.

This is an independent, MIT-licensed project; see [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md) for attribution. It is **unofficial** and is not endorsed by Mistral or Hermes.
