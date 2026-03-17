# Contributing to quawk

`quawk` is still in design/prototyping, so contributions currently include both documentation/spec changes and early implementation bootstrap work. This guide explains how to propose changes, make them coherently, and validate them before review.

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

Apply these rules to Python source, tests, scripts, and documentation unless a documented exception is approved.

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

Implementation follows strict phase-based TDD:

1. Before a phase starts, author that phase's planned tests.
2. Mark unimplemented behavior as `xfail` with reason `phase_bootstrap`.
3. Burn those tests down to `pass` during implementation.
4. Do not close a phase with remaining `phase_bootstrap` tests.

Allowed exception:
- a remaining `xfail` must be reclassified as `known_gap` with explicit tracking

Reference behavior:
- primary: `one-true-awk`
- secondary: `gawk --posix`

Current local checks are defined in [docs/testing.md](docs/testing.md). When the project scaffold is in place, contributors should expect to run:

```sh
quawk --help
pytest
ruff format --check .
ruff check .
mypy src scripts
python scripts/check_phase_gate.py
```

## Pull Request Checklist

Before opening or updating a PR, verify that:
- the change is scoped and clearly explained
- affected docs or specs were updated
- tests were added or updated when behavior changed
- compatibility impact is called out explicitly
- local links are relative and not broken
- no undocumented `known_gap` was introduced
- required local checks pass when the relevant tooling exists

## Review Notes

Review should focus on:
- semantic correctness
- compatibility implications
- stability of diagnostics and test metadata
- clarity of public behavior and design intent

When a change affects grammar, execution, CLI behavior, or CI/test gates, update the matching section in the docs instead of leaving the design split across multiple files.
