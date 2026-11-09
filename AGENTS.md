# AGENTS.md — rules for every AI agent working on this repository

This repository has **no CI**. GitHub Actions was removed on purpose: Actions
minutes cost money and every check here runs locally in seconds. There is
nothing to "wait for" after a push.

## Before every push / pull request

Run the whole check suite on this machine, from the repository root:

```bash
bash scripts/check-local.sh
```

- Exit code 0 is the only acceptable result before a push or a PR.
- If a required tool is missing (no `node`, no `fastapi`), the script reports it
  as **skipped**: say so explicitly in the PR/summary, and run the suite on a
  machine that has the tool. Never present a skipped check as a passing one.
- Never add or re-enable a GitHub Actions workflow, and never add a
  `.github/workflows/` file: the suite above is the single gate.
- There is no remote status to observe, so never write "CI is green" or "waiting
  for CI": report the local command, its output and its limits instead.

## What the suite covers

`scripts/check-local.sh` reproduces the former workflow: Python unit tests
(`unittest discover -s tests`), `py_compile` on the Python entry points,
`node --check` on `desktop/plugin.js` and `dashboard/dist/index.js`, and JSON
validation of `dashboard/manifest.json`.

## Workflow expected from an agent

1. Read `README.md` and the code you are about to touch.
2. Implement on a dedicated branch; commit with conventional messages
   (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
3. Run `bash scripts/check-local.sh` and paste the real result in the summary.
4. Open the pull request. State what was verified, what was skipped and why.

## Other standing rules

- Never commit or print a Mistral session cookie: the cookie lives only in
  `~/.config/hermes-mistral-usage/session.cookie` (mode 0600) or in the
  backend environment, never in the repository, the chat, a log or a test
  fixture.
- Tests use synthetic data only and must not contact Mistral.
- Keep the history type agnostic: the SQLite database stores timestamps,
  metric names, percentages and aggregate amounts — no cookies, no tokens, no
  prompts, no account identifiers.
- Bump `plugin.yaml` version together with behaviour changes and keep the
  README feature table honest about what is and is not verified.

## Première prise en main

Avant toute action sur ce dépôt, lire **`ARCHITECTURE.md`** à la racine : il décrit l'architecture, la liaison des composants et le contexte global de l'écosystème. Ne pas explorer le projet au hasard avant de l'avoir lu.

Ce dépôt n'a plus de CI : la porte locale est bash scripts/check-local.sh. Commits : docs only, identité dominante = p7s6sr5bnf-source <p7s6sr5bnf@privaterelay.appleid.com> (vérifie avec git log). Ne modifie aucun autre fichier, ne touche à aucun autre dépôt. Pour pousser : export GH_TOKEN=$(grep -m1 '^GH_TOKEN=' ~/.hermes/.env | cut -d= -f2- | tr -d '\r\n"') puis git push origin HEAD:main. Jamais de force push. Rapport final : dépôt, lignes d'ARCHITECTURE.md, action sur AGENTS.md, SHA du commit, dernière ligne exacte du push.
