# Contributing to quawk

`quawk` is in active implementation, so contributions currently include both documentation/spec changes and incremental runtime/compiler work. This guide explains how to propose changes, make them coherently, and validate them before review.

## Before You Start

Open an issue or short proposal first when a change affects:
- language semantics
- parser ambiguity or grammar shape
- runtime behavior
- compatibility expectations
- CLI contract
- roadmap scope

For behavior changes, include:
- the use case
- expected behavior
- a POSIX reference when applicable
- comparison output from `one-true-awk` or `gawk --posix` when relevant

## Setup

Use the local environment described in [docs/getting-started.md](docs/getting-started.md). The project baseline is:
- `uv`
- Python `3.14.x`
- project-local `.venv` managed by `uv`

## Workflow Expectations

- Keep changes scoped and easy to review.
- Update the relevant docs in the same change when behavior or design intent changes.
- Prefer separate PRs for broad doc reorgs versus implementation work.
- When references disagree, cite POSIX text before locking expected behavior.
- Keep links relative. Do not add absolute local filesystem paths.

## Coding and Documentation Standards

Apply these rules to Python source, tests, and documentation unless a documented exception is approved.

- Prefer explicit, typed data flow over implicit side effects.
- Keep parser, semantic analysis, backend, and runtime boundaries explicit.
- Use descriptive names that communicate intent quickly.
- Prefer short functions with single focused responsibilities.
- Add comments for invariants, parser disambiguation rules, and non-obvious behavior.
- Do not add comments that restate obvious syntax.

### Naming

- Use `snake_case` for functions, variables, and modules.
- Use `PascalCase` for classes, dataclasses, and enums.
- Avoid one-letter names except for short-lived local indices.
- Keep phase-oriented naming consistent: `lexer`, `parser`, `sema`, `backend`, `runtime`.

### Errors and Data Models

- Do not use exception-driven control flow for expected parser, semantic, or runtime paths.
- Represent recoverable failures with structured result or error objects.
- Attach source spans to frontend and semantic errors when available.
- Keep public module boundaries type-annotated.
- Prefer `dataclass` or `TypedDict` for structured records over ad hoc dicts.
- Keep AST and IR models immutable by default where practical.

## Testing Expectations

Implementation follows strict capability-first TDD:

1. Before implementing the initial `P1` path or the next capability increment, add the tests first.
2. Use ordinary failing tests or `pytest.mark.xfail` when a temporary expected failure is clearer.
3. Burn those tests down to `pass` during implementation.
4. Keep roadmap state in the roadmap, not in separate test metadata files.

For behavior and compatibility work, prefer adding or updating AWK cases under `tests/corpus/` in the same change.

Reference behavior:
- primary: `one-true-awk`
- secondary: `gawk --posix`

Current local checks are defined in [docs/testing.md](docs/testing.md). When the project scaffold is in place, contributors should expect to run:

```sh
quawk --help
corpus --list
pytest
uv run pytest -m compat
yapf --diff --recursive src tests
ruff check .
mypy src
```

## Pull Request Checklist

Before opening or updating a PR, verify that:
- the change is scoped and clearly explained
- [CHANGELOG.md](CHANGELOG.md) was updated when the change affects user-visible behavior or release notes
- affected docs or specs were updated
- tests were added or updated when behavior changed
- compatibility impact is called out explicitly
- local links are relative and not broken
- required local checks pass when the relevant tooling exists

For release-process changes, update [docs/release-checklist.md](docs/release-checklist.md) in the same change.

## Review Notes

Review should focus on:
- semantic correctness
- compatibility implications
- stability of diagnostics and test coverage
- clarity of public behavior and design intent

When a change affects grammar, execution, CLI behavior, or CI/test gates, update the matching section in the docs instead of leaving the design split across multiple files.
