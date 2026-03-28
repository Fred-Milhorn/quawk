# Benchmarking Plan

This document defines the first performance-benchmarking pass for `quawk`.

## Goal

Build an engineering benchmark that compares:

- `quawk`
- `awk` (`one-true-awk` in this repo's terminology)
- `gawk --posix`

The benchmark should measure:

- wall-clock execution time
- peak memory usage

The benchmark is for local engineering use and regression tracking. It is not a publishable benchmark suite and should optimize for low setup friction over maximum methodological sophistication.

## Scope

The first version should:

- use a repo-owned Python harness
- avoid optional external benchmarking tools such as `hyperfine`
- generate large synthetic datasets on demand
- run a small fixed suite of representative workloads
- report repeated-run summaries rather than single-run timings
- report both user-visible end-to-end `quawk` time and a `quawk`-only compile-versus-run breakdown

The first version should not:

- gate CI on absolute timing thresholds
- require checked-in large fixture datasets
- depend on profiler tooling
- attempt publication-grade benchmarking methodology

## Measurement Method

The harness should be the source of truth for all measurements.

Implementation choices:

- use Python `subprocess` to launch each engine
- use `time.perf_counter()` for wall time
- use `os.wait4()` and child `rusage` for peak resident set size on Unix platforms
- use warmup runs before measured runs
- summarize measured runs with median and p95 wall time plus median peak RSS

The benchmark should report two timing families for `quawk`:

1. `end_to_end`
   - the real user-facing invocation path, including frontend work, lowering, runtime linking, and `lli` execution
2. `split_breakdown`
   - engineering-only timing that separates:
     - frontend and lowering work
     - `lli` execution of an already-built IR module

The `split_breakdown` numbers are explanatory only. They should not be presented as directly comparable to `awk` or `gawk --posix`.

## Workload Suite

Use a small fixed suite of three workloads. Keep them inside the currently LLVM-backed `quawk` subset so the `quawk` split metric is meaningful.

### Workload 1: Delimited Aggregation

Behavior:

- parse multi-column delimited records
- aggregate numeric values by key
- print one final summary

Purpose:

- stress field splitting, keyed aggregation, and full-input traversal

### Workload 2: Filter and Transform

Behavior:

- filter records by mixed predicates
- derive numeric output values from selected records
- print transformed output

Purpose:

- stress predicate evaluation, string handling, and per-record compute cost

### Workload 3: Multi-file Reduction

Behavior:

- process multiple input files in one invocation
- use `NR`, `FNR`, and `FILENAME`
- aggregate values across files and print a final summary

Purpose:

- stress runtime bookkeeping and file-transition behavior

## Dataset Generation

Datasets should be generated on demand, not checked into the repo.

Requirements:

- deterministic generation from a fixed seed
- text-heavy inputs that exercise AWK field splitting and record traversal
- multiple dataset scales:
  - `smoke` for fast harness verification
  - `medium` for local iteration
  - `large` for the default comparison run

The default `large` scale should be chosen so a single run takes long enough to drown out startup noise. Target multi-second runtimes in the reference engines rather than sub-second runs.

## Benchmark Interface

The first version should expose a checked-in command such as:

```sh
uv run python scripts/benchmark.py
```

Recommended command-line surface:

- `--repetitions N` with default `15`
- `--warmups N` with default `3`
- `--dataset-scale {smoke,medium,large}` with default `large`
- `--json PATH` for optional machine-readable output
- `--keep-workdir` for debugging generated inputs and intermediate artifacts

Default behavior should print a readable terminal summary.

## Reporting

For each workload, report:

- median wall time
- p95 wall time
- median peak RSS
- relative comparison versus `gawk --posix`

For `quawk`, also report:

- end-to-end median wall time
- split frontend and lowering median wall time
- split `lli` execution median wall time

The report should make the distinction between end-to-end `quawk` numbers and split `quawk` breakdown numbers explicit.

## Validation and Tests

Tests for the benchmark harness should focus on correctness of orchestration, not on absolute performance.

Required coverage:

- deterministic dataset generation for a fixed seed
- correct engine command construction for `quawk`, `awk`, and `gawk --posix`
- correct summary math for median, p95, and memory aggregation
- successful `smoke` runs against all required engines
- clear failures when required tools are missing
- correct `quawk` split behavior: build IR once, then run `lli` against the saved module

Do not add tests that assert specific timing or memory thresholds.

## Assumptions

- the benchmark is a local engineering tool, not a release gate
- `gawk --posix` is the primary reference for relative comparisons
- the first version remains self-contained and does not require extra benchmark tooling
- workloads stay within the current LLVM-backed subset of `quawk`
- end-to-end `quawk` timing is the primary apples-to-apples comparison
