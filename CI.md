# CI Gate Specification

This document defines the minimum CI gates required for `quawk`.

## Required Jobs (Blocking)

1. `format-lint`
- setup: install project dev dependencies in Python 3.14 venv
- commands:
  - `ruff format --check .`
  - `ruff check .`
- fails on formatting drift or lint errors

2. `type-check`
- setup: install project dev dependencies
- command: `mypy src`
- fails on type-check regressions

3. `tests`
- setup: install project dev dependencies
- command: `pytest`
- fails on unit/integration/property test failures

4. `phase-gate`
- setup: install project dev dependencies
- command: `python scripts/check_phase_gate.py`
- validates:
  - test manifests match `TEST_SPEC.md`
  - `xfail_reason=known_gap` has `tracking`
  - completed phases contain no `xfail_reason=phase_bootstrap`

## Optional Jobs (Non-Blocking Initially)

1. `compat-smoke`
- runs small differential subset with `one-true-awk`, `gawk --posix`, and `quawk`

2. `perf-smoke`
- records startup and cache-hit timing trend

## CI Matrix

Minimum required:
- Python 3.14 on Linux x86_64

Planned expansion:
- Python 3.14 on macOS (x86_64/aarch64 as available)
- compatibility job matrix by reference awk versions

## Promotion Rule

- A change cannot merge unless all required jobs pass.
- Optional jobs may be informative until promoted to required status.
