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
- required pytest differential tests should fail clearly when `gawk` or host `awk` is unavailable
- the CLI should print a useful message and exit nonzero if asked to run differential mode without the required engines

Missing engines are environment failures for the required compatibility gate.

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
- fail clearly when required external engines are unavailable
- pass when references agree and `quawk` matches
- pass when references disagree only if the case is classified in `tests/corpus/divergences.toml`
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
- cases either pass or fail with concrete diffs
- missing `gawk` or `awk` yields an environment failure, not a skip

### Existing corpus coverage

Keep [test_corpus.py](/Users/fred/dev/quawk/tests/test_corpus.py) unchanged as the single-engine `quawk` corpus surface.

## Acceptance Criteria

`T-035` is done when:

- `tests/test_p10_compat_baselines.py` uses the real differential runner
- the `T-047` placeholder `xfail`s are removed
- the runner executes `quawk`, `one-true-awk`, and `gawk --posix`
- normalized results are compared deterministically
- missing external interpreters produce clear environment failures in required pytest gates
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
- missing external engines should fail in required pytest suites
- reference disagreement should be reported but not treated as a failure until `T-037`
- `T-035` should burn down the `T-047` placeholders rather than creating a second parallel baseline

## Size

This is a medium task:

- one moderate expansion of [corpus.py](/Users/fred/dev/quawk/src/quawk/corpus.py)
- one new unit test file
- one existing baseline test update
- small roadmap and testing-doc updates

## Coverage Checklist

Use this rubric to decide whether the compatibility corpus is comprehensive
enough for the shipped public surface.

Coverage levels:
- `none`: no differential corpus case exists for the feature family
- `smoke`: one basic happy-path case exists
- `happy + edge`: one normal case and at least one boundary/default/interaction case exist
- `happy + edge + divergence`: normal and edge coverage exist, plus any known
  extension or reference-split case is tagged and classified

For each implemented public feature in [SPEC.md](/Users/fred/dev/quawk/SPEC.md),
the compatibility corpus should answer all of these:
- is there at least one happy-path case?
- is there at least one edge/default/interaction case?
- if `quawk` intentionally differs from the reference awks here, is that case
  tagged and classified in `tests/corpus/divergences.toml`?
- can a reviewer point from the case back to a SPEC row, roadmap claim, or
  known divergence?

The compatibility corpus is only close to comprehensive when every implemented
feature family reaches at least `happy + edge`, and every known extension or
reference split reaches `happy + edge + divergence`.

## Current Coverage Matrix

Current corpus size:
- 38 checked-in corpus cases under `tests/corpus/`

Current matrix against the shipped surface:

| Feature family | Current level | Target level | Current evidence | Main gaps |
|---|---|---|---|---|
| `BEGIN` scalar and expression basics | `happy + edge + divergence` | `happy + edge + divergence` | `begin_print_literal`, `begin_assignment`, `begin_if_less`, `begin_logical_and`, `begin_equality` | Add more arithmetic, ternary, and match-op cases only if they become compatibility-sensitive. |
| Record actions and mixed programs | `happy + edge` | `happy + edge` | `record_first_field`, `mixed_begin_record_end`, `mixed_begin_record_end_first_field`, `mixed_begin_record_end_custom_fs` | Add more multi-file and empty-input mixed-program cases as depth work, not as the immediate minimum. |
| Regex and range patterns | `happy + edge` | `happy + edge` | `regex_filter`, `range_default_print` | Add regex edge cases and more range boundary cases to deepen beyond the minimum. |
| Arrays and iteration | `happy + edge + divergence` | `happy + edge + divergence` | `array_missing_read`, `array_delete_index`, `length_string_and_array`, `split_builtin`, `for_in_plain_array`, `for_expr_list_loop`, `for_in_parenthesized_array` | Add more array key/value interaction cases and more delete/iteration combinations as depth work. |
| Fields and record mutation | `happy + edge` | `happy + edge` | `record_first_field`, `dynamic_field_assignment` | Add more `$0`, higher-index field, and field-rebuild interaction cases as depth work. |
| Control flow and record control | `happy + edge` | `happy + edge` | `begin_if_less`, `while_loop_print`, `for_standard_loop`, `break_in_loop`, `continue_in_loop`, `do_while_print`, `next_skip_record`, `nextfile_two_files`, `exit_status_after_output` | Add more nested and multi-file control-flow interactions as depth work. |
| Builtins | `smoke` | `happy + edge` | `printf_formatting`, `length_string_and_array`, `split_builtin`, `substr_builtin` | Add more arity/boundary behavior for the currently claimed builtin tranche. |
| Builtin variables | `happy + edge` | `happy + edge` | `nr_nf_builtin_vars`, `filename_two_files`, `builtin_vars_multi_file_reset` | Add more builtin-variable combinations only if compatibility work exposes gaps. |
| String/number coercions | `smoke` | `happy + edge` | `string_coercion_concat` | Add more numeric-string conversion and truthiness cases. |
| CLI/runtime option interactions in corpus | `happy + edge` | `happy + edge` | `mixed_begin_record_end_custom_fs`, `v_numeric_begin`, `stdin_dash_operand`, `dash_dash_input_operand` | Add more file-argv permutations only if compatibility work exposes gaps. |
| User-defined functions | `happy + edge` | `happy + edge` | `function_basic_call`, `function_local_scope` | Add more function-argument and return-shape cases only if compatibility work exposes gaps. |
| Diagnostics and error-shape compatibility | `none` | `none` | none | Keep most diagnostics in direct pytest coverage; add corpus negatives only where end-to-end compatibility behavior matters more than direct assertions. |

## Current Gap List

The biggest current compatibility gaps are:
- builtin coverage is still a small tranche and has little boundary testing
- coercion coverage relies on one concatenation-oriented case
- regex/range coverage exists but is still only one or two cases deep

## Recommended Next Additions

If coverage expansion resumes, prioritize these next:
1. one additional coercion/truthiness case
2. one regex boundary case and one range boundary case
3. one builtin boundary case for each of `length`, `split`, and `substr`
4. one deeper array iteration interaction case
5. one additional mixed-program multi-file boundary case

This keeps corpus growth tied to the real compatibility-risk surface instead of
adding cases just to increase the raw count.

## Planned Case Inventory

This section is the concrete planning surface for the next `P11` expansion wave
tracked in [roadmap.md](roadmap.md) as `T-127` through `T-131`.

`T-127` is complete when:
- every implemented feature family above has an explicit target coverage level
- every area still at `none` or `smoke` has named next corpus cases below
- the immediate implementation work is partitioned into `T-128`, `T-129`, and `T-130`

### T-128: Functions and standard loop families

Committed corpus cases:
- `function_basic_call`
  - `function f(x) { return x + 1 } BEGIN { print f(2) }`
- `function_local_scope`
  - `function f(x) { x = x + 1; return x } BEGIN { x = 10; print f(2); print x }`
- `while_loop_print`
  - `BEGIN { x = 0; while (x < 3) { print x; x = x + 1 } }`
- `for_standard_loop`
  - `BEGIN { for (i = 0; i < 3; i = i + 1) print i }`
- `for_in_plain_array`
  - `BEGIN { a["x"] = 1; for (k in a) print k }`
- `break_in_loop`
  - one loop case with early exit through `break`
- `continue_in_loop`
  - one loop case that skips exactly one iteration through `continue`

Expected result:
- functions and standard loop families reach at least `happy + edge`

### T-129: CLI/runtime options and builtin variables

Committed corpus cases:
- `v_numeric_begin`
  - `-v x=7` is visible before `BEGIN`
- `stdin_dash_operand`
  - `-` stdin operand is processed in file order
- `dash_dash_input_operand`
  - `--` preserves an input file operand beginning with `-`
- `filename_two_files`
  - explicit `FILENAME` coverage across two file operands
- `builtin_vars_multi_file_reset`
  - `NR`, `FNR`, and `NF` behavior across multiple files

Expected result:
- CLI/runtime option interactions and builtin variables reach at least `happy + edge`

### T-130: Coercions, regex/range boundaries, and builtin edges

Add these corpus cases:
- `numeric_string_truthiness`
  - one case that forces both numeric and string truthiness/coercion behavior
- `unset_scalar_coercion`
  - one case that reads the same unset scalar in numeric and string contexts
- `regex_no_match`
  - regex selection produces no output
- `range_single_record`
  - range starts and ends on the same record
- `substr_two_arg`
  - two-argument `substr`
- `split_explicit_separator`
  - `split` with an explicit separator argument
- `length_empty_string`
  - empty-string length boundary case

Expected result:
- coercions, regex/range boundaries, and the currently claimed builtin tranche move beyond `smoke`

### T-131: Rebaseline

After the new cases land:
- rerun the required differential suites
- classify/document any new intentional extensions or reference splits
- update the coverage matrix above to reflect the new case inventory and the remaining gaps

Implementation rule:
- if the references agree and `quawk` differs, treat the case as a bug or unsupported gap
- if `quawk` intentionally differs and that behavior is acceptable, tag the case appropriately and add a checked-in divergence entry
