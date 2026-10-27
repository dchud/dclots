#!/usr/bin/env bash
# Pre-push check. Runs what CI runs, in the same order.
set -euo pipefail

cd "$(dirname "$0")/.."

step() { printf '\n=== %s ===\n' "$1"; }

step "format"
uv run ruff format --check .

step "lint"
uv run ruff check .

step "types"
uv run mypy

step "process labels"
uv run python scripts/lint_process_labels.py

step "workflow lint"
uv run zizmor --quiet .github/workflows/

# The PySpark README example needs Java 17 or 21 and is skipped without
# it; CI runs it.
step "tests"
uv run pytest -q

printf '\nAll checks passed.\n'
