#!/usr/bin/env bash
# Local checks — this repository has NO CI. Run this before every push / PR.
#
# Usage: bash scripts/check-local.sh
#
# It reproduces exactly what used to run in GitHub Actions (Python unit tests,
# syntax compiles, JavaScript syntax, dashboard manifest) on this machine.
# Exit code 0 = everything that could run passed.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

fail=0
skipped=0
ran=0

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
ok()   { printf '   OK   %s\n' "$1"; ran=$((ran + 1)); }
ko()   { printf '   FAIL %s\n' "$1"; fail=1; }
warn() { printf '   SKIP %s\n' "$1"; skipped=$((skipped + 1)); }

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "python3 is required" >&2
  exit 2
fi

# The dashboard backend imports fastapi. Prefer uv (ephemeral, nothing installed
# in the repo); fall back to an interpreter that already has fastapi.
RUN=()
if command -v uv >/dev/null 2>&1; then
  RUN=(uv run --quiet --with fastapi python)
elif "$PY" -c 'import fastapi' >/dev/null 2>&1; then
  RUN=("$PY")
else
  RUN=("$PY")
  warn "fastapi is not importable: install it (python3 -m pip install fastapi) or use uv for the backend tests"
fi

step "Python unit tests (unittest discover -s tests)"
if "${RUN[@]}" -m unittest discover -s tests -v; then
  ok "python tests"
else
  ko "python tests"
fi

step "Python syntax (py_compile)"
if "${RUN[@]}" -m py_compile dashboard/plugin_api.py usage_history.py __init__.py scripts/configure.py; then
  ok "py_compile"
else
  ko "py_compile"
fi

step "JavaScript syntax (node --check)"
if command -v node >/dev/null 2>&1; then
  for f in desktop/plugin.js dashboard/dist/index.js; do
    if node --check "$f"; then ok "node --check $f"; else ko "node --check $f"; fi
  done
else
  warn "node is not installed: desktop and dashboard bundles were not syntax-checked"
fi

step "Dashboard manifest (json.tool)"
if "$PY" -m json.tool dashboard/manifest.json >/dev/null; then
  ok "dashboard/manifest.json"
else
  ko "dashboard/manifest.json"
fi

printf '\n------------------------------------------------------------------------\n'
printf '%s check(s) passed, %s skipped, %s failure(s)\n' "$ran" "$skipped" "$fail"
if [ "$fail" -ne 0 ]; then
  printf '\033[1mDO NOT PUSH\033[0m — fix the failures above first.\n'
  exit 1
fi
if [ "$skipped" -ne 0 ]; then
  printf 'Some checks were skipped (missing tool): re-run on a complete machine\n'
  printf 'before claiming the change is verified.\n'
fi
printf 'Local checks passed.\n'
