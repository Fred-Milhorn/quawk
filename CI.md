# CI Gate Specification

This document defines the minimum CI gates required for `quawk`.

## Required Jobs (Blocking)

1. `format`
- command: `nix --extra-experimental-features 'nix-command flakes' fmt -- --check`
- fails on formatting drift

2. `build`
- command: `nix --extra-experimental-features 'nix-command flakes' build`
- fails on build/package errors

3. `flake-check`
- command: `nix --extra-experimental-features 'nix-command flakes' flake check`
- fails on check derivation failures

4. `phase-gate`
- command: `scripts/check-phase-gate`
- validates:
  - test manifests match `TEST_SPEC.md`
  - `xfail_reason=known_gap` has `tracking`
  - completed phases contain no `xfail_reason=phase_bootstrap`

Implementation note:
- `phase-gate` validator is implemented in SML.
- test metadata parsing uses `huml-sml`.

## Optional Jobs (Non-Blocking Initially)

1. `compat-smoke`
- runs small differential subset with `one-true-awk`, `gawk --posix`, and `quawk`

2. `perf-smoke`
- records startup and cache-hit timing trend

## CI Matrix

Minimum required:
- default developer platform

Planned expansion:
- Linux x86_64
- macOS x86_64/aarch64 (as available in CI provider)

## Promotion Rule

- A change cannot merge unless all required jobs pass.
- Optional jobs may be informative until promoted to required status.
