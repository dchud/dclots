#!/usr/bin/env python3
"""Fail on process labels in artifacts that outlive the work.

Code, tests and user-facing docs get read long after the branch that
produced them is gone. A ticket ID or a PR number in them points at
context that git history already carries and keeps more accurately,
and it goes stale the moment a ticket is renumbered or a commit is
squashed.

Only high-confidence shapes are checked. Bare version numbers and the
word "phase" are not, because they have too many legitimate uses.

Put `process-label-ok` in a comment on the line to exempt it.
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Generated, vendored and scratch trees are not ours to lint.
EXCLUDED_DIRS = {
    ".beads",
    ".claude",
    ".git",
    ".mypy_cache",
    ".playwright-mcp",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "metastore_db",
    "spark-warehouse",
    "tmp",
}
EXCLUDED_PATHS = {
    Path("CHANGELOG.md"),
    # The instruction files define these conventions, so they have to
    # quote the shapes they forbid.
    Path("CLAUDE.md"),
    Path("AGENTS.md"),
}
SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".sh"}

EXEMPTION = "process-label-ok"

CHECKS = [
    (
        re.compile(r"\bbd-[a-z0-9]{3,}\b", re.IGNORECASE),
        "ticket ID",
    ),
    (
        re.compile(r"\bPR\s*#\s*\d+|\bPR\d+\b|\bthis PR\b", re.IGNORECASE),
        "PR reference",
    ),
    (
        re.compile(r"(?<![\w&])#\d+\b"),
        "issue reference",
    ),
    (
        re.compile(
            r"\b(?:since|as of|flipped in|changed in|default since)\s+"
            r"v?\d+\.\d+",
            re.IGNORECASE,
        ),
        "version-tagged claim",
    ),
    (
        re.compile(
            r"\b(?:pre|post)-(?:PR|release|merge|migration)\b", re.IGNORECASE
        ),
        "stage-relative wording",
    ),
]


def candidate_files() -> Iterator[tuple[Path, Path]]:
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if EXCLUDED_DIRS & set(rel.parts):
            continue
        if rel in EXCLUDED_PATHS:
            continue
        yield path, rel


def main() -> int:
    failures = []
    for path, rel in candidate_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, start=1):
            if EXEMPTION in line:
                continue
            for pattern, label in CHECKS:
                match = pattern.search(line)
                if match:
                    failures.append(
                        f"{rel}:{number}: {label} {match.group(0).strip()!r}"
                    )

    if failures:
        print("Process labels found in persistent artifacts:\n")
        for failure in failures:
            print(f"  {failure}")
        print(
            f"\n{len(failures)} finding(s). These belong in commit "
            "messages, PR bodies or ticket descriptions, not in code, "
            "tests or user-facing docs."
        )
        print(f"Add a '{EXEMPTION}' comment on the line to exempt it.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
