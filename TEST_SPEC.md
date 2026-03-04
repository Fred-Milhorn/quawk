# Test Specification (Simple)

This document defines a minimal manifest format for test cases and phase-based `xfail` tracking.

Goals:
- keep test metadata simple
- make TDD phase gates machine-checkable

## Format

One manifest file per test case in HUML.

Recommended location:
- `tests/**/case.huml`

## Required Fields

```text
id: parser.regex.division.001
phase: P1
suite: parser
status: xfail                      # pass | xfail
xfail_reason: phase_bootstrap      # required when status=xfail
tracking: null                     # required when xfail_reason=known_gap
program: tests/parser/regex_division_001.awk
stdin: tests/fixtures/empty.txt    # nullable
expect:
  stdout: ""
  stderr_class: syntax_error        # nullable
  exit: 2
tags:
  - posix-required
```

## Field Rules

- `id`: stable identifier, lowercase dotted path preferred
- `phase`: one of `P0`..`P6`
- `suite`: logical suite name (`parser`, `runtime`, `compat`, etc)
- `status`:
  - `pass`: expected to pass
  - `xfail`: expected failure
- `xfail_reason`:
  - required when `status=xfail`
  - allowed values:
    - `phase_bootstrap` (temporary, pre-implementation)
    - `known_gap` (intentional gap, tracked)
- `tracking`:
  - required when `xfail_reason=known_gap`
  - must reference task/issue ID
- `program`: path to AWK program under repo
- `stdin`: path to input fixture or `null`
- `expect`: expected output/exit behavior
- `tags`: includes at least one of `posix-required`, `unspecified`, `extension`, `known-gap`

## Runner Contract

The test runner must:

1. validate manifest schema before execution
2. execute test and compare against `expect`
3. emit per-test result (`pass`, `xfail`, `fail`)
4. fail if:
  - manifest is invalid
  - `known_gap` has no `tracking`
  - completed phase still has `xfail_reason=phase_bootstrap`

Implementation language/tooling:
- phase-gate validator is implemented in Python
- metadata parsing may use a Python HUML parser or a repository-defined equivalent parser

## Phase Gate Rule

- Before implementation for phase `Px`: tests for `Px` are added as `xfail` with `phase_bootstrap`.
- At phase close: no `phase_bootstrap` entries may remain for `Px`.
