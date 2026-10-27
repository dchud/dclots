# CLAUDE.md

Instructions for agents working in this repository.

## Project

`dclots` parses and labels District of Columbia SSL (square, suffix, lot)
identifiers. It is one module, `src/dclots/__init__.py`, with no dependencies
outside the standard library, supporting Python 3.11 through 3.15. Every public
function takes one value and returns one value, or `None` when the value
doesn't parse, so each works as a scalar UDF in pandas, polars, DuckDB, ibis
and PySpark.

Users install it from git, or copy `src/dclots/__init__.py` into their
project as `dclots.py`. Keep it a single code file with no runtime
dependencies. `src/dclots/py.typed` marks the installed package as typed.

`README.md` is the user documentation: the SSL format, every function, the
lot-type ranges and their exceptions, repairs, options, and dataframe
examples.

## Key files

| Path | Contents |
|---|---|
| `src/dclots/__init__.py` | The library: patterns, the `SSL` record, `Parser`, module-level functions |
| `src/dclots/py.typed` | Marks the installed package as typed for mypy and other checkers |
| `tests/test_dclots.py` | Behavior tests, using SSL values from DC's VPM layers |
| `tests/test_readme.py` | Runs every README example and checks its printed output |
| `README.md` | User documentation |
| `scripts/check.sh` | Pre-push check; runs what CI runs |
| `scripts/lint_process_labels.py` | Fails on ticket IDs, PR numbers and version-tagged claims |
| `.github/workflows/ci.yml` | `lint`; `test` on each supported Python version; `test-results`, one result for the test matrix |
| `.beads/` | Issue tracker (`br`) |

## Commands

```sh
uv sync               # install dev dependencies
./scripts/check.sh    # ruff format and check, mypy, label lint, zizmor, tests
uv run pytest -q      # tests only
```

Use `uv` for every Python invocation. Line length is 79.

The PySpark README example needs Java 17 or 21. `check.sh` skips it when the
Java found through `JAVA_HOME` or the path is another version, and skips any
README example whose library isn't installed. CI sets Java 21 and
`DCLOTS_REQUIRE_ALL_EXAMPLES=1`, which turns those skips into failures.

## How the library works

- `Parser` is a frozen dataclass holding the options. The module-level
  functions are bound methods of a default `Parser()`. A new accessor goes on
  `Parser` as a method, gets a module-level binding at the end of the file,
  and goes in `__all__`.
- `parse()` strips and uppercases the value, then tries a square SSL, then a
  prefixed SSL (`PAR`, `RES`, `APPR`), then, with
  `unreadable_lot="square_only"`, a square with no readable lot.
- `SSL` is a frozen record. Square SSLs set `square` and `suffix`; prefixed
  SSLs set `number` instead. `lot` never includes the of-lot marker.
- Every accessor returns `None` for a value that doesn't parse, whatever its
  type; `is_valid` returns `False`.
- Each judgment call is a named option with a default and named alternatives:
  `dash_marker`, `unreadable_lot`, `extra_zeros`, and `normalize(of_lot=...)`.
  Values are `Literal` strings, checked when the `Parser` is created. A new
  judgment call gets the same treatment, with README examples and tests.

## Tests

- Take test values from DC's data where possible, and name the source layer
  in a comment. Mark made-up values "constructed".
- Every README example is a test. `pycon` blocks run as doctests in one
  shared namespace. A `python` block followed by a `text` block must print
  exactly that text; produce the text by running the code.

## DC reference data

The VPM layers are served from
`https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land_WebMercator/FeatureServer/<layer>`.
Query `<layer>/query` with `returnGeometry=false` and only the SSL-related
`outFields`; pages hold 2,000 rows. Downloads go in `./tmp/`, never in the
repository.

| Layer | Name |
|---|---|
| 40 | Common Ownership Lots |
| 52 | Condo Relate Table |
| 44 | Condo Approval Lots |
| 34 | Record Lots (Historical) |
| 39, 38 | Tax Lots, Tax Lots (Historical) |
| 33, 32 | Parcel Lots, Parcel Lots (Historical) |
| 37, 36 | Reservations, Reservations (Historical) |
| 3, 2 | Air Rights Lots, Air Rights Lots (Historical) |
| 5 | Appropriations |
| 78 | Land Boundary Change |

What the data shows:

- Parcel Lots and Reservations use `SQUARE` for the square(s) a parcel or
  reservation lies in, not for the SSL's first field.
- DC's `LOT` column includes the of-lot marker, as in `0076-of2`.
- The `LOT_TYPE` domain in a layer's metadata (`<layer>?f=json`) defines
  codes 1 through 7; 7 is condo.
- The SSL string and DC's `SQUARE`/`SUFFIX` columns sometimes disagree. The
  parser reads the string.

DC describes the format at <https://opendata.dc.gov/pages/changes-in-lots>.
The page renders with JavaScript and its answers sit in collapsed accordions,
so a plain fetch returns only the title; read it in a browser.

## Working with Daniel

Daniel is a solo developer who reviews pull requests in the GitHub PR view
and merges them. Treat a correction as a standing rule.

1. Branch from `main` for each ticket and mark the ticket `in_progress`.
2. Work until `./scripts/check.sh` passes.
3. Commit, push and `gh pr create` without asking; say so in one sentence.
4. Report the PR link and the CI result, then stop.

- Never merge. Approving an approach is not approval to merge. Don't ask
  whether to merge or say you're waiting on one.
- A ruleset protects `main`: changes land only through a PR, the `lint`
  and `test-results` checks must pass, and force pushes and deleting the
  branch are blocked. Nobody bypasses it. Renaming either job means
  updating the ruleset in the repository settings; changing the Python
  versions in the matrix does not.
- Cut every branch from `main` and target `main`; don't stack PRs.
- Never delete remote branches. Never run a package registry upload.
- After a merge: switch to `main`, pull, `git remote prune origin`, then
  delete each merged local branch with `git branch -d` once
  `git merge-base --is-ancestor <branch> origin/main` succeeds. Never `-D`
  without asking.
- Prefer one coherent PR to several small ones; two to four commits in a
  medium PR. When Daniel says "ticket it", write the ticket and stop.

### Tone

Flat, matter-of-fact and direct, in chat and in everything committed. No
enthusiasm, affirmations, idioms, euphemisms or marketing language. State the
literal claim, and claim no more than a change delivers. Documentation
instructs: no rebuttals, no defending a design. Explaining why something
behaves as it does is fine.

Keep command output to result lines. End every turn with a short summary that
restates any open question. Use AskUserQuestion for decisions that block
work.

### Documentation and persistent artifacts

- Don't create or edit documentation a task doesn't reference. When a
  complete fix needs a doc edit, ask. Don't write spec or design files unless
  asked. Revise a document in place.
- Keep process out of code, tests and docs: no ticket IDs, PR numbers, phase
  labels, version-tagged claims, or project-state wording such as
  "currently", "not yet" or "planned". Those belong in commit messages, PR
  bodies and tickets. `scripts/lint_process_labels.py` checks the common
  shapes.
- Write PR bodies, tickets and commit messages as if they were right the
  first time; no revision narration.

### Tickets

`br` keeps tickets in SQLite with a JSONL export in `.beads/issues.jsonl`.

- `br show <id> --json` before any update. `br update --description`
  replaces the description; it does not append.
- Create with `br create "Title" -t task -p 2 --silent --description-file -`
  and a heredoc. Never pass `--slug`. Never run `br edit`.
- Titles are descriptive, with no priority, phase or version prefixes.
  Descriptions are unwrapped Markdown.
- Close a ticket in the PR that resolves it: `br close`,
  `br sync --flush-only`, then commit `.beads/issues.jsonl`. Check that
  `git diff .beads/issues.jsonl` touches only this branch's tickets.
- If a flush refuses because the JSONL changed, run
  `br sync --flush-only --force`.
- A short token Daniel mentions, such as `5x5`, is probably a ticket ID;
  check `br` first.

### Git and GitHub

- Stage by path. Never `git add -A`, `git add .` or `git commit -a`. Check
  `git status --short` and `git diff --cached --stat` before committing.
- Conventional-commit subjects; bodies wrapped at 72 columns.
- No Claude attribution: no `Co-Authored-By` or session trailers, no
  "Generated with" footers.
- PR titles carry no ticket suffix. Start PR bodies from
  `.github/PULL_REQUEST_TEMPLATE.md`, mark every checklist item (use
  "N/A: reason"), and end with the `Bead:` line. Keep the body current with
  `gh pr edit` as commits land.
- Text sent to GitHub or `br` is not hard-wrapped. Markdown files in the
  repository are wrapped at 79 columns. Never break code blocks, tables or
  URLs.

### Scratch and tools

- All scratch, including a subagent's, goes in `./tmp/` (gitignored). Never
  use `/tmp`, `/private/tmp`, `/var/folders` or a harness scratchpad, and
  never write to `/`.
- Use `rg` rather than grep, `fd` rather than find, and `dust` rather than
  du. Use `git dft` for structural diffs.

### Model and effort

- Original work, meaning code, tests, docs, ticket text, review and debugging:
  Opus at `/effort xhigh`.
- Housekeeping, meaning git operations, cleanup, status questions and
  bookkeeping that is already decided: Sonnet at medium effort.

Haiku is not used. When the active setting doesn't match the task, suggest
the switch in one line and proceed. Subagents that write repository content
run on Opus. Ask before dispatching a subagent on Fable.

### Verification and design

- Run `./scripts/check.sh` and read its output before saying anything
  passes. Report failures and skips as they are. Check a subagent's claims
  by running them.
- With no installed base, don't count "changes existing behavior" as a cost.
  Prefer the result that treats analogous cases the same way and whose rule
  fits in one sentence.
