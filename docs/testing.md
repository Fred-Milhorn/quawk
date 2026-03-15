# Testing

This document defines how `quawk` validates behavior, tracks incomplete work, and blocks regressions in CI.

## Objectives

- catch parser and runtime regressions early
- make compatibility decisions explicit and reproducible
- prioritize POSIX-conformant behavior over implementation-specific quirks
- keep phase-based TDD machine-checkable

## TDD Workflow Policy

Implementation follows strict phase-based TDD:

1. before a phase starts, author that phase's full planned test set
2. mark the new tests as `xfail` while functionality is unimplemented
3. implement features by burning down phase `xfail` tests to `pass`
4. do not close a phase with unresolved phase-bootstrap `xfail` tests

Allowed exception:
- a test may remain `xfail` only if reclassified as `known_gap` with explicit documentation and linked tracking

Phase gate rule:
- before implementation for phase `Px`, tests for `Px` are added as `xfail` with `phase_bootstrap`
- at phase close, no `phase_bootstrap` entries may remain for `Px`

## Framework Baseline

Default framework stack:
- `pytest` for unit and integration execution
- `hypothesis` for property-based testing

Framework policy:
- use `pytest` for parser, semantic, backend, and runtime tests
- use `hypothesis` for parser, semantic, and runtime invariants where property testing is useful
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

Organize tests into behavior-focused suites:
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

## Divergence Classification

When references disagree, classify once and record it:
- `POSIX-specified`
- `implementation-defined`
- `unspecified/undefined`
- `extension`

Never silently pick one behavior. Every persistent divergence needs an explicit classification.

## Test Manifest Specification

Use one manifest file per test case in HUML.

Recommended location:
- `tests/**/case.huml`

Required fields:

```text
id: parser.regex.division.001
phase: P1
suite: parser
status: xfail
xfail_reason: phase_bootstrap
tracking: null
program: tests/parser/regex_division_001.awk
stdin: tests/fixtures/empty.txt
expect:
  stdout: ""
  stderr_class: syntax_error
  exit: 2
tags:
  - posix-required
```

Field rules:
- `id`: stable identifier, lowercase dotted path preferred
- `phase`: one of `P0`..`P6`
- `suite`: logical suite name such as `parser`, `runtime`, or `compat`
- `status`: `pass` or `xfail`
- `xfail_reason`: required when `status=xfail`; allowed values are `phase_bootstrap` and `known_gap`
- `tracking`: required when `xfail_reason=known_gap`
- `program`: path to the AWK program under repo
- `stdin`: path to input fixture or `null`
- `expect`: expected output and exit behavior
- `tags`: must include at least one of `posix-required`, `unspecified`, `extension`, `known-gap`

Runner contract:

1. validate manifest schema before execution
2. execute test and compare against `expect`
3. emit per-test result: `pass`, `xfail`, or `fail`
4. fail if the manifest is invalid, `known_gap` has no `tracking`, or a completed phase still has `phase_bootstrap`

Implementation language and tooling:
- phase-gate validator is implemented in Python
- metadata parsing may use a Python HUML parser or a repository-defined equivalent parser

## Pass/Fail Policy

Test statuses:
- `pass`: `quawk` matches expected result
- `xfail`: expected failure with reason metadata
- `fail`: regression or unresolved incompatibility

Release gate recommendation:
- no failing `posix-required` tests
- no remaining `xfail` tests with reason `phase_bootstrap` in completed phases
- `known_gap` is allowed only when explicitly tagged and documented

## CI Gate Specification

Required jobs:

1. `format-lint`
   - `ruff format --check .`
   - `ruff check .`
2. `type-check`
   - `mypy src`
3. `tests`
   - `pytest`
4. `phase-gate`
   - `python scripts/check_phase_gate.py`

`phase-gate` validates:
- test manifests match the schema above
- `xfail_reason=known_gap` has `tracking`
- completed phases contain no `xfail_reason=phase_bootstrap`

Optional jobs initially:
- `compat-smoke`
- `perf-smoke`

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
pytest
pytest -m property
pytest tests/compat -m smoke
ruff format --check .
ruff check .
mypy src
python scripts/check_phase_gate.py
```

## Operational Notes

- pin reference interpreter versions in CI for reproducibility
- rebaseline intentionally only through a reviewed change to expected results
- keep tests small and focused; prefer one behavior assertion per test case
