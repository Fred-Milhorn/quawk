# Optional Benchmark Notes

This document captures optional performance-benchmark ideas for `quawk`.

It is not part of the active roadmap or required implementation plan.

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

## T-325 NOAA Runtime Gap Benchmark

For `T-325`, the repo now includes a NOAA-style benchmark harness that runs the
checked-in climate-report program against deterministic synthetic fixed-width
inputs:

```sh
uv run python scripts/benchmark_noaa_runtime_gap.py
```

The harness reports two timing families:

- `startup_heavy`
  - `uv run quawk` versus `gawk --posix`
- `steady_state`
  - direct `.venv/bin/quawk` versus `gawk --posix` on repeated input

This split is intentional:

- the startup-heavy family keeps the real user-facing `uv run quawk` path visible
- the steady-state family uses the direct project binary and a repeated-input
  workload so runtime changes are not drowned out by fixed startup cost

Recommended passing smoke command:

```sh
uv run python scripts/benchmark_noaa_runtime_gap.py --dataset-scale smoke --repetitions 1 --warmups 0
```

Use `--json PATH` for machine-readable output and `--keep-workdir` when you want
to inspect the generated station metadata and synthetic `.dly` input. Use
`--family steady_state` when startup-heavy timing is not relevant to the
workload you are validating.

Known failing investigation commands:

```sh
uv run python scripts/benchmark_noaa_runtime_gap.py --family steady_state --dataset-scale medium
uv run python scripts/benchmark_noaa_runtime_gap.py --family steady_state --dataset-scale large
```

Those larger steady-state scales currently expose a reference-output mismatch in
the monthly summary output, so they are useful for diagnosis but should not be
treated as passing validation commands until `T-332` is closed.

## T-326 Elapsed-Time Runtime Profile

The runtime hot-path profiler now reports both call counts and aggregate elapsed
time per helper when `QUAWK_RUNTIME_PROFILE=1` is enabled. Use the checked-in
consumer script to rank helpers by wall-clock cost instead of call count alone:

```sh
uv run python scripts/profile_runtime_hot_paths.py --dataset-scale smoke --repetitions 1 --warmups 0
```

The script aggregates runtime stderr output across the selected workloads and
prints the top helpers by total elapsed time, along with total call counts and
average nanoseconds per call.

## T-234 Slot vs Hash Microbenchmark

For `T-234`, the repo now includes a focused microbenchmark script:

```sh
uv run python scripts/benchmark_slot_vs_hash.py
```

Sample run on April 10, 2026 (`--iterations 2000000 --repetitions 7 --warmups 2`):

- slot median: `12.688 ms`
- hash median: `33.801 ms`
- median speedup (`slot` vs `hash`): `2.66x`

## T-249 Numeric Loop Fast Path Microbenchmark

For `T-249`, the repo now includes a focused benchmark script:

```sh
uv run python scripts/benchmark_numeric_loop_fast_path.py
```

Sample run on April 10, 2026 (`--iterations 120000 --repetitions 7 --warmups 2`):

- fast-path median: `491.637 ms`
- mixed-fallback median: `536.320 ms`
- median speedup (`fast` vs `fallback`): `1.09x`

## T-257 Optimized vs Unoptimized Suite

For `T-257`, the repo now includes a workload-suite benchmark script:

```sh
uv run python scripts/benchmark_optimized_vs_unoptimized.py
```

This suite replaced the earlier single-loop microbenchmark because that probe was
too narrow and was a poor fit for evaluating LLVM optimization value after the
P25-P27 lowering work.

The current suite mixes:

- optimizer kernels:
  - `scalar_fold_loop`
  - `branch_rewrite_loop`
- user-facing runtime workloads:
  - `field_aggregate`
  - `filter_transform`
  - `multi_file_reduce`

For each workload, the script reports both:

- `end_to_end`: real execution through `python -m quawk` / `quawk -O`
- `lli_only`: execution of prebuilt optimized and unoptimized modules

The `lli_only` numbers are diagnostic. The primary comparison is the
`end_to_end` timing family because that is the user-visible path.

Recommended local commands:

```sh
uv run python scripts/benchmark_optimized_vs_unoptimized.py --dataset-scale smoke
uv run python scripts/benchmark_optimized_vs_unoptimized.py --dataset-scale medium
uv run python scripts/benchmark_optimized_vs_unoptimized.py --dataset-scale large
```

When a quick iteration is needed, narrow the suite to one workload:

```sh
uv run python scripts/benchmark_optimized_vs_unoptimized.py --dataset-scale smoke --workload scalar_fold_loop
```

`T-290` historical baseline note before `T-292` (sample run on April 17, 2026 with
`--dataset-scale medium --repetitions 7 --warmups 2`):

- geometric mean speedup (`optimized` vs `unoptimized`, `end_to_end`): `0.93x`
- geometric mean speedup (`optimized` vs `unoptimized`, `lli_only`): `0.99x`

Historical interpretation before `T-292`:

- the flat `lli_only` result means this is not just `opt` process overhead in
  the user-facing `-O` path; representative optimized kernels are already
  failing to get meaningful runtime wins from the current IR shape
- the current scalar-kernel IR still keeps loop-local numeric temporaries in
  `%quawk.state` instead of lowering them as local values that LLVM can more
  easily promote and simplify
- the representative baseline anchors for `P34` are:
  - `scalar_fold_loop`: `n`, `s`, `bias`, `scale`, `i`, `base`, `x`, `y`, `z`,
    and `dead` remain state-backed
  - `branch_rewrite_loop`: `n`, `total`, `limit`, `i`, `left`, `right`, and
    `always` remain state-backed
- `field_aggregate`: runtime field extraction still flows through
  `qk_get_field_inline`, alongside state-backed locals such as `a`, `b`, `c`,
  `derived`, `total`, and `count`

`T-295` post-`T-294` rebaseline note (sample run on April 18, 2026 with
`--dataset-scale medium --repetitions 7 --warmups 2`):

- geometric mean speedup (`optimized` vs `unoptimized`, `end_to_end`): `0.94x`
- geometric mean speedup (`optimized` vs `unoptimized`, `lli_only`): `1.00x`
- per-workload `lli_only` median speedups:
  - `scalar_fold_loop`: `0.99x`
  - `branch_rewrite_loop`: `1.02x`
  - `field_aggregate`: `1.00x`
  - `filter_transform`: `1.01x`
  - `multi_file_reduce`: `0.99x`

Current interpretation after `T-295`:

- the `P34` IR work clearly changed representative code shape, but that cleanup
  still does not translate into a meaningful suite-level `lli_only` win on the
  current benchmark mix
- `branch_rewrite_loop` is the clearest optimizer-kernel improvement, but
  `scalar_fold_loop` remains effectively flat and the overall geometric mean is
  still noise-level
- end-to-end `-O` remains slower because `opt` overhead is still larger than the
  execution win on this workload mix
- the current benchmark evidence supports treating `P34` as an IR-shape cleanup
  and honest rebaseline, not as proof that LLVM optimization is broadly
  worthwhile for this suite yet

## Assumptions

- the benchmark is a local engineering tool, not a release gate
- `gawk --posix` is the primary reference for relative comparisons
- the first version remains self-contained and does not require extra benchmark tooling
- workloads stay within the current LLVM-backed subset of `quawk`
- end-to-end `quawk` timing is the primary apples-to-apples comparison
