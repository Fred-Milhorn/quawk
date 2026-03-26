# Testing

This document defines how `quawk` validates behavior, tracks incomplete work, and plans future release gates.

## Objectives

- catch parser and runtime regressions early
- make compatibility decisions explicit and reproducible
- prioritize POSIX-conformant behavior over implementation-specific quirks
- keep TDD workflow lightweight and reviewable

## TDD Workflow Policy

Implementation should stay test-driven without adding a second metadata system:

1. before implementation starts for the initial `P1` path or the next capability increment, author the tests first
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

Start with small end-to-end fixtures for the current supported execution path.

For the `P1` phase, CLI-driven end-to-end tests are the primary proof that work is moving in the right direction.
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

The repository keeps these as file-backed cases under `tests/corpus/`.
Each case lives in its own directory and includes:
- `case.toml`
- `program.awk`
- optional stdin fixture such as `input.txt`
- optional file-argv fixtures listed under `inputs`
- optional `expected.stdout`
- optional `expected.stderr`
- optional shared `divergences.toml` entry when references disagree persistently

The manifest records:
- case ID and short description
- expected exit status
- tags such as `supported`, `known-gap`, `compat-baseline`, and `posix-required`
- optional `args` for AWK CLI options such as `-F:`
- optional `inputs` for record files passed on the command line after `-f`
- optional `xfail_reason` for known unsupported behavior

## When To Add A Corpus Case

Use the corpus for user-visible AWK behavior.

Add a corpus case when:
- the behavior is naturally expressed as a small AWK program
- you want to verify end-to-end execution or compatibility behavior
- the case represents a language feature, a compatibility question, or a known unsupported feature worth tracking
- the failure or expected result is easier to understand from program/input/output artifacts than from Python assertions

Prefer ordinary Python tests when:
- you are checking lexer tokenization details
- you are checking parser shape or AST structure directly
- you are checking diagnostics formatting or source spans
- you are checking narrow backend or CLI contracts that are easier to assert directly in Python

Use both when:
- the feature matters end to end and also has tricky internal structure worth pinning with unit tests

Examples of good corpus cases:
- `BEGIN { print 1 + 2 }`
- `{ print $1 }` with input
- `/foo/ { print $0 }`
- `BEGIN { print "start" } { print $2 } END { print "done" }`

## How To Add A Corpus Case

1. Create a new directory under `tests/corpus/`.
2. Add `program.awk`.
3. Add `input.txt` if the case should feed stdin text to the program.
4. Add file fixtures and list them under `inputs` if the case needs real AWK input files.
5. Add `expected.stdout` and, if needed, `expected.stderr`.
6. Add `case.toml` with:
   - `id`
   - `description`
   - `program`
   - optional `input`
   - optional `inputs`
   - optional `args`
   - `tags`
   - optional `xfail_reason`
   - `[expect]` including `exit` and any expected output files
7. If the reference AWKs disagree, add or update the entry in `tests/corpus/divergences.toml`.
8. Run `uv run corpus --list` to confirm the case is discovered.
9. Run `uv run pytest tests/test_corpus.py`.

Minimal example:

```toml
id = "begin_print_literal"
description = "Literal string print from BEGIN."
program = "program.awk"
tags = ["supported", "smoke", "p1"]

[expect]
stdout = "expected.stdout"
exit = 0
```

Use `xfail_reason` when the case documents a known unsupported feature or an intentional temporary gap. Keep these reasons specific so stale expected failures are easy to notice in review.

## Oracle Execution Model

For each compatibility case:

1. run under `one-true-awk`
2. run under `gawk --posix`
3. run under `quawk`
4. compare normalized outputs and exit codes

Normalize before comparison:
- line endings for `stdout` and `stderr` in the current differential runner
- additional normalization policy can expand later if compatibility work needs it

This oracle model becomes a primary workflow in the compatibility phase, not a blocker for the initial `P1` path.

## Divergence Classification

When references disagree, classify once and record it:
- `POSIX-specified`
- `implementation-defined`
- `unspecified/undefined`
- `extension`

Record these in `tests/corpus/divergences.toml`:

```toml
[[divergence]]
case_id = "example_case"
classification = "implementation-defined"
summary = "one-true-awk and gawk --posix disagree on this corner case"
```

Never silently pick one behavior. Every persistent divergence needs an explicit classification.
The differential corpus workflow should fail on:
- unclassified reference disagreements
- stale divergence entries whose case no longer disagrees

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

Differential corpus policy:
- `PASS`: `quawk` matches the agreeing references and has no stale divergence entry
- `REF-DISAGREE`: allowed only when the case is classified in `tests/corpus/divergences.toml`
- `FAIL`: `quawk` differs from agreeing references, the references disagree without a classification, or a divergence entry has gone stale

Release gate recommendation:
- no failing `posix-required` tests
- no stale `xfail` tests whose reason no longer matches reality
- no unclassified or stale divergence-manifest entries
- compatibility gaps are documented in tests, roadmap notes, or issue tracking

## CI Gate Specification

Required jobs:

1. `format-lint`
   - `yapf --diff --recursive src tests`
   - `ruff check .`
2. `type-check`
   - `mypy src`
3. `tests`
   - `pytest`

Optional jobs initially:
- `compat-smoke`
- `release-smoke`

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
corpus --list
pytest
pytest -m smoke
yapf --diff --recursive src tests
ruff check .
mypy src
```

## Operational Notes

- pin reference interpreter versions in CI for reproducibility
- rebaseline intentionally only through a reviewed change to expected results
- keep tests small and focused; prefer one behavior assertion per test case
