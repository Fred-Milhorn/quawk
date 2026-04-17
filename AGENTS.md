# Agent Workflow

This document defines the default local workflow for AI/code agents and maintainers working in this repository.

## Principles

- keep changes scoped and reviewable
- run commands through `uv` for Python entrypoints and tests
- stage intentionally, but `git add -A` is acceptable when the worktree is agent-owned
- avoid shell-quoting pitfalls in multi-line commit messages

## Environment and Commands

Use the project-local toolchain:

- `uv` for Python and dependency execution
- Python `3.14.x` from the repo-managed `.venv`

Preferred command style:

```sh
uv run quawk --help
uv run pytest -q
uv run pytest -q -m core
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
```

## Marker-Based Suites

Use marker-based suite selection, not long per-file pytest invocations.

Preferred suite commands:

```sh
uv run pytest -q -m core
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
uv run pytest -m docs_contract
```

Roadmap-contract checks are opt-in:

```sh
QUAWK_RUN_ROADMAP_TESTS=1 uv run pytest -m roadmap_contract
```

For debugging a serial test run:

```sh
uv run pytest -n 0 -q
```

## Git Commit Workflow

When preparing a commit:

1. Review changes:
   - `git status --short`
2. Stage:
   - `git add -A`
3. Verify staged scope:
   - `git status --short`
   - `git diff --cached --stat`

### Commit Message via Temp File

Use a temp file for multi-line messages to avoid shell expansion issues (for example, backticks in Markdown lists).

```sh
tmp_msg="$(mktemp)"
cat > "$tmp_msg" <<'MSG'
tests: speed up default cycle and relax roadmap doc coupling

- run pytest in parallel by default with xdist (`-n auto`)
- add `pytest-xdist` to dev dependencies
- mark roadmap-only contract tests as `roadmap_contract`
- skip roadmap contract checks by default unless `QUAWK_RUN_ROADMAP_TESTS=1`
- remove brittle historical roadmap-string assertions from roadmap test files

This keeps default test runs focused on executable behavior and cuts wall-clock
time substantially, while preserving an explicit opt-in path for roadmap checks.
MSG
git commit -F "$tmp_msg"
rm -f "$tmp_msg"
```

Notes:
- prefer `git commit -F` over inline repeated `-m` for long messages
- never rely on backticks inside double-quoted shell strings

## Final Validation Before Push

- run relevant tests with `uv run ...` before commit/push
- confirm no temporary files are staged
- check final commit message:
  - `git log -1 --pretty=format:%B`

## Task Close-Out Rule

After finishing any roadmap task:

- update `docs/roadmap.md` to reflect completion in the backlog status
- update the `Immediate next tasks:` list so completed items are removed and the next pending items are current
