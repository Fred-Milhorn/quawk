# Testing

This document defines how `quawk` validates behavior, tracks incomplete work, and blocks regressions in CI.

## Objectives

- catch parser and runtime regressions early
- make compatibility decisions explicit and reproducible
- prioritize POSIX-conformant behavior over implementation-specific quirks
- keep TDD workflow lightweight and reviewable

## TDD Workflow Policy

Implementation should stay test-driven without adding a second metadata system:

1. before implementation starts for the MVP path or the next MVP increment, author the tests first
2. use ordinary failing tests by default
3. use `pytest.mark.xfail` only when an expected temporary failure is clearer than a hard fail
4. implement the smallest coherent runtime change that burns those tests down to `pass`

Roadmap state should be tracked in [docs/roadmap.md](roadmap.md), not in separate manifest files or a custom validator.

## Framework Baseline

Default framework stack:
- `pytest` for unit and integration execution

Framework policy:
- use `pytest` for parser, semantic, backend, and runtime tests
- use property-based testing only when a stable behavior area clearly benefits from it
- keep compatibility and differential orchestration in dedicated harness code invoked by pytest
- use deterministic fixture-driven tests when property testing is not ergonomic

## Reference Implementations

Primary reference:
- `one-true-awk`

Secondary reference:
- `gawk --posix`

Decision rule:
- if `one-true-awk` and `gawk --posix` agree, `quawk` should match
- if they differ, classify behavior by POSIX text before deciding expected behavior

## Test Corpus Structure

Start with small end-to-end fixtures for the current MVP path.

For the MVP phase, CLI-driven end-to-end tests are the primary proof that work is moving in the right direction.
Lexer, parser, and lowering unit tests are supporting tests, not substitutes for CLI-level execution coverage.

Expand into behavior-focused suites only as the supported subset grows, for example:
- `parser/`
- `runtime/records_fields/`
- `runtime/types_coercions/`
- `runtime/control_flow/`
- `runtime/functions/`
- `runtime/regex/`
- `io/`
- `errors/`

Each compatibility test should include:
- AWK program text
- input fixture
- expected stdout
- expected stderr class
- expected exit status
- tags such as `posix-required`, `unspecified`, `extension`, `known-gap`

## Oracle Execution Model

For each compatibility case:

1. run under `one-true-awk`
2. run under `gawk --posix`
3. run under `quawk`
4. compare normalized outputs and exit codes

Normalize before comparison:
- line endings
- trailing whitespace policy
- locale and timezone-sensitive values via a fixed environment

This oracle model becomes a primary workflow in the compatibility phase, not a blocker for the initial MVP path.

## Divergence Classification

When references disagree, classify once and record it:
- `POSIX-specified`
- `implementation-defined`
- `unspecified/undefined`
- `extension`

Never silently pick one behavior. Every persistent divergence needs an explicit classification.

## Expected Failures

Use `pytest.mark.xfail` when:
- a test documents behavior you intend to implement shortly
- a known platform or dependency issue makes the failure expected for now
- the temporary failure is still worth keeping visible in the suite

Do not create a parallel manifest or checklist entry for the same behavior.
The test itself should remain the source of truth.

## Pass/Fail Policy

Test statuses:
- `pass`: `quawk` matches expected result
- `xfail`: expected failure with reason metadata
- `fail`: regression or unresolved incompatibility

Release gate recommendation:
- no failing `posix-required` tests
- no stale `xfail` tests whose reason no longer matches reality
- compatibility gaps are documented in tests, roadmap notes, or issue tracking

## CI Gate Specification

Required jobs:

1. `format-lint`
   - `yapf --diff --recursive src tests scripts`
   - `ruff check .`
2. `type-check`
   - `mypy src`
3. `tests`
   - `pytest`

Optional jobs initially:
- `compat-smoke`

Minimum CI matrix:
- Python 3.14 on Linux x86_64

Planned CI expansion:
- Python 3.14 on macOS
- compatibility matrix by reference awk version

Promotion rule:
- a change cannot merge unless all required jobs pass
- optional jobs may remain informative until promoted to required

## Local Commands

Common local commands once the scaffold exists:

```sh
quawk --help
pytest
yapf --diff --recursive src tests scripts
ruff check .
mypy src
```

## Operational Notes

- pin reference interpreter versions in CI for reproducibility
- rebaseline intentionally only through a reviewed change to expected results
- keep tests small and focused; prefer one behavior assertion per test case
