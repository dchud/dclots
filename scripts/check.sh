#!/usr/bin/env bash
# Pre-push check. Runs what CI runs, in the same order.
set -euo pipefail

cd "$(dirname "$0")/.."

step() { printf '\n=== %s ===\n' "$1"; }

# CI installs with --locked, which fails when uv.lock is out of date;
# `uv run` alone would rewrite the lockfile instead.
step "lockfile"
uv sync --locked

step "format"
uv run ruff format --check .

step "lint"
uv run ruff check .

step "types"
uv run mypy

step "process labels"
uv run python scripts/lint_process_labels.py

# Covers the workflows and the Dependabot config.
step "workflow lint"
uv run zizmor --quiet .github/

# The PySpark README example needs Java 17 or 21 and is skipped without
# it; CI runs it.
step "tests"
uv run pytest -q

printf '\nAll checks passed.\n'
