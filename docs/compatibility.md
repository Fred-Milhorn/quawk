# Compatibility Plan

This document is the implementation plan for `T-035`: the differential compatibility runner.

## Goal

Implement a compatibility runner that executes the checked-in compatibility baseline under:

- `quawk`
- `one-true-awk`
- `gawk --posix`

and produces normalized, comparable results for both pytest and CLI use.

## Scope

`T-035` should:

- run the same corpus case under all three engines
- normalize results enough to compare them deterministically
- report agreement and disagreement clearly
- integrate with the existing corpus harness and the `T-047` compatibility baseline

`T-035` should not:

- classify divergences beyond surfacing reference disagreement
- massively expand the corpus beyond the existing supported baseline
- introduce a second metadata system beyond the current corpus manifests

## Design

### 1. Extend the corpus model with differential results

Add small data structures in [corpus.py](/Users/fred/dev/quawk/src/quawk/corpus.py):

- `NormalizedCorpusResult`
  - `engine`
  - `returncode`
  - `stdout`
  - `stderr`
- `DifferentialCaseResult`
  - `case`
  - `results_by_engine`
  - helper methods for agreement checks and display formatting

Keep the existing raw subprocess result type for direct execution.

### 2. Add engine availability detection

Implement helpers such as:

- `is_engine_available("quawk")`
- `is_engine_available("gawk-posix")`
- `is_engine_available("one-true-awk")`

Expected behavior:

- `quawk` is required in-repo
- `gawk` and host `awk` may be absent
- pytest differential tests should `skip` cleanly when an external engine is unavailable
- the CLI should print a useful message and exit nonzero if asked to run differential mode without the required engines

Missing engines should not be reported as compatibility failures.

### 3. Normalize outputs conservatively

Add one normalization function for subprocess results.

Normalize:

- line endings: `\r\n` to `\n`
- `stderr` line endings the same way

Do not normalize aggressively yet:

- do not trim or invent final newlines
- do not strip trailing whitespace
- do not rewrite diagnostics text
- do not bucket errors by category

The first pass should keep mismatches visible.

### 4. Add differential execution helpers

Add functions like:

- `run_case_differential(case: CorpusCase) -> DifferentialCaseResult`
- `run_case_for_engines(case, engines=...)`

This layer should:

- execute each engine once
- normalize each result
- preserve command lines for reporting
- avoid deciding expected behavior beyond the reference-agreement rule

### 5. Define comparison policy

For `T-035`, use the simplest explicit rule:

- if `one-true-awk` and `gawk --posix` agree on exit, `stdout`, and `stderr`, `quawk` must match
- if the two references disagree, report the case as reference disagreement and do not fail it as a `quawk` incompatibility yet

That keeps `T-035` aligned with [testing.md](testing.md) and leaves persistent divergence handling to `T-037`.

### 6. Convert the `T-047` baseline into real differential tests

Update [test_p10_compat_baselines.py](/Users/fred/dev/quawk/tests/test_p10_compat_baselines.py):

- remove the placeholder runner
- parameterize over `compatibility_baseline_cases()`
- run differential execution
- `skip` when required external engines are unavailable
- pass when references agree and `quawk` matches
- pass when references disagree
- fail when references agree and `quawk` differs

This should burn down the current strict `xfail` placeholders added by `T-047`.

### 7. Expose differential mode in the corpus CLI

Extend the `corpus` CLI in [corpus.py](/Users/fred/dev/quawk/src/quawk/corpus.py) with a differential mode.

Recommended flags:

- keep `--engine` for single-engine execution
- add `--differential`

Example:

```sh
uv run corpus --differential
uv run corpus --differential regex_filter
```

CLI output should show one line per case:

- `PASS`
- `FAIL`
- `SKIP`
- `REF-DISAGREE`

No richer formatting is required for `T-035`.

## Test Plan

### Unit coverage

Add focused tests in a file such as [test_corpus_differential.py](/Users/fred/dev/quawk/tests/test_corpus_differential.py) for:

- engine command construction
- engine availability detection
- result normalization
- reference-agreement logic
- mismatch formatting

Use small synthetic results where possible instead of spawning subprocesses for every unit test.

### Integration coverage

Update [test_p10_compat_baselines.py](/Users/fred/dev/quawk/tests/test_p10_compat_baselines.py) to become the acceptance test for the differential runner.

Expected outcomes:

- no placeholder `xfail`s remain for `T-035`
- cases either pass, skip, or fail with concrete diffs
- missing `gawk` or `awk` yields skip, not failure

### Existing corpus coverage

Keep [test_corpus.py](/Users/fred/dev/quawk/tests/test_corpus.py) unchanged as the single-engine `quawk` corpus surface.

## Acceptance Criteria

`T-035` is done when:

- `tests/test_p10_compat_baselines.py` uses the real differential runner
- the `T-047` placeholder `xfail`s are removed
- the runner executes `quawk`, `one-true-awk`, and `gawk --posix`
- normalized results are compared deterministically
- missing external interpreters produce clean skips
- reference disagreement is surfaced distinctly from `quawk` mismatches
- [roadmap.md](roadmap.md) marks `T-035` done

## Recommended Order

1. Add result and normalization types in `corpus.py`
2. Add engine availability detection
3. Add differential runner functions
4. Add unit tests for normalization and agreement logic
5. Replace the `T-047` placeholder baseline with real pytest differential tests
6. Add `corpus --differential`
7. Update roadmap and testing docs

## Key Decisions

These policy choices are assumed by this plan:

- compare `stderr` exactly after newline normalization
- missing external engines should skip, not fail
- reference disagreement should be reported but not treated as a failure until `T-037`
- `T-035` should burn down the `T-047` placeholders rather than creating a second parallel baseline

## Size

This is a medium task:

- one moderate expansion of [corpus.py](/Users/fred/dev/quawk/src/quawk/corpus.py)
- one new unit test file
- one existing baseline test update
- small roadmap and testing-doc updates
