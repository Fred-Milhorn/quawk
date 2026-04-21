# Agent Workflow

This document defines the default local workflow for AI/code agents and maintainers working in this repository.

## Principles

- keep changes scoped and reviewable
- run commands through `uv` for Python entrypoints and tests
- stage intentionally; use `git add -A` only when the worktree scope is verified or agent-owned
- avoid shell-quoting pitfalls in multi-line commit messages

## Environment and Commands

Use the project-local toolchain:

- `uv` for Python and dependency execution
- Python `3.14.x` from the repo-managed `.venv`
- system LLVM tools on `PATH`: `lli`, `clang`, `llvm-as`, `llvm-link`, and `llc`

Bootstrap a fresh checkout with:

```sh
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install -e .[dev]
```

Initialize pinned upstream compatibility sources when working on compatibility:

```sh
git submodule update --init --recursive
uv run quawk-upstream bootstrap
```

Preferred command style:

```sh
uv run quawk --help
uv run pytest -q
uv run pytest -q -m core
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
```

Static validation commands:

```sh
uv run ruff check .
uv run mypy src
uv run yapf --diff --recursive src tests
```

## Marker-Based Suites

Use marker-based suite selection, not long per-file pytest invocations.

Preferred suite commands:

```sh
uv run pytest -q -m core
uv run pytest -q -m conformance
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
```

For debugging a serial test run:

```sh
uv run pytest -n 0 -q
```

## Test Selection

Implementation should stay test-driven:

- add or update tests before behavior changes
- use ordinary failing tests by default
- use `pytest.mark.xfail` only when a temporary expected failure is clearer than a hard fail
- keep roadmap state in `docs/roadmap.md`, not in a parallel test metadata system

Use corpus cases under `tests/corpus/` for user-visible AWK behavior that is
best expressed as a small AWK program with input and expected output.

Prefer ordinary Python tests for:

- lexer tokenization details
- parser shape or AST structure
- diagnostics formatting or source spans
- narrow backend or CLI contracts that are easier to assert directly

Useful corpus commands:

```sh
uv run corpus --list
uv run corpus demo_case
uv run corpus --differential demo_case
```

## Compatibility Workflow

Compatibility references are repo-managed and pinned:

- primary reference: One True Awk built under `build/upstream/bin/`
- secondary reference: `gawk --posix` built under `build/upstream/bin/`
- host `awk` is not a compatibility reference
- `compat_reference` is the primary compatibility authority
- `compat_corpus` is the repo-owned supplemental regression surface

If One True Awk and `gawk --posix` agree, `quawk` should match them. If they
disagree, classify the behavior by POSIX text before deciding the expected
behavior.

Persistent corpus reference disagreements belong in
`tests/corpus/divergences.toml`. Persistent upstream failures or disagreements
belong in `tests/upstream/divergences.toml` and the companion notes in
`docs/compatibility.md`.

Required compatibility pytest suites should fail, not skip, when the pinned
reference engines are missing.

## Implementation Guardrails

`quawk` is an AOT-oriented compiler and runtime. Python should lex, parse,
validate, lower, link, and invoke LLVM tooling; claimed AWK program semantics
should execute through the compiled backend/runtime path.

Do not add Python-side semantic fallback for claimed behavior. For
record-driven programs, keep generated IR reusable across input runs and let the
runtime stream records rather than materializing input in Python or lowering one
module per concrete input stream.

Public feature claims should stay aligned across ordinary execution, `--ir`,
`--asm`, tests, and docs. If a grammar-valid or parser-admitted form is not part
of the current compiled execution contract, document it as unclaimed or
out-of-contract rather than silently falling back.

## Documentation Updates

When a change affects behavior, update the relevant docs in the same change:

- public feature claims: `SPEC.md`
- architecture, execution model, and CLI contract: `docs/design.md`
- concrete grammar: `docs/quawk.ebnf`
- implemented AST shape: `docs/quawk.asdl`
- active backlog and task completion: `docs/roadmap.md`
- user-visible behavior and release notes: `CHANGELOG.md`
- release process changes: `docs/release-checklist.md`
- compatibility policy and upstream decisions: `docs/compatibility.md`

Update `CHANGELOG.md` when the change affects user-visible behavior,
compatibility, CLI behavior, or release notes.

## Git Commit Workflow

When preparing a commit:

1. Review changes:
   - `git status --short`
   - identify unrelated user changes before staging
2. Stage:
   - use targeted `git add <path>` for mixed worktrees
   - use `git add -A` only when all worktree changes are in scope
3. Verify staged scope:
   - `git status --short`
   - `git diff --cached --stat`
   - confirm no unrelated user changes or temporary files are staged

### Commit Message via Temp File

Use a temp file for multi-line messages to avoid shell expansion issues (for example, backticks in Markdown lists).

```sh
tmp_msg="$(mktemp)"
cat > "$tmp_msg" <<'MSG'
tests: speed up default cycle and relax roadmap doc coupling

- run pytest in parallel by default with xdist (`-n auto`)
- add `pytest-xdist` to dev dependencies
- keep default test runs focused on executable behavior
- remove brittle historical roadmap-string assertions from roadmap test files

This keeps default test runs focused on executable behavior and cuts wall-clock
time substantially without adding a separate documentation-test surface.
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
