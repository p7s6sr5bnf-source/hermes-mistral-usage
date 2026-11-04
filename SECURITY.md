# Security policy

This plugin is a read-only Mistral subscription-usage monitor; it uses a
**privileged authenticated browser session cookie**, not a scoped read-only
Mistral API credential. An attacker who steals the cookie may impersonate
the user's Mistral browser session.

## Never share credentials

Never put any of the following in issues, PRs, screenshots, chat transcripts,
Git commits, test fixtures or logs: Cookie request headers, Ory session values,
CSRF tokens, exported browser sessions, API keys, or HAR files.

If credentials leak, sign out/revoke the Mistral session and rotate associated
keys where appropriate. Removing the secret from the latest Git revision is
not sufficient if it was included in earlier commits.

## Threat model and safeguards

- Network calls use a fixed HTTPS Mistral Admin endpoint; no credentialed
  redirects are allowed.
- The backend reads a 0600 owner-only local cookie file; it is **not encrypted**
  at rest. Never run on an untrusted or public multi-tenant host.
- Read-only metrics are returned through Hermes's authenticated plugin API.
  Do not expose Hermes Dashboard or plugin API publicly without access controls.
- The history database contains only numerical usage and timestamp metadata,
  in a local owner-only 0600 SQLite file outside the Git working tree.
- Hermes Agent's tool reads the local database only. It never reads the cookie
  or makes network calls. **If you ask an Agent to use the tool, the resulting
  metrics may be shared with the model provider powering that Agent.**
- Plugin monitoring has no power to change quotas, accounts, billing or
  model routing. Mistral's undocumented browser APIs can change without notice.
- The project does not support automatically renewing browser credentials.

## Report a vulnerability

Please report privately to the repository owner through GitHub's private
vulnerability reporting when enabled. Otherwise open a minimal non-sensitive
issue asking for a private contact channel. Do not include exploit secrets or
live tokens in public issues.
