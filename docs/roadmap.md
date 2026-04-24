# Roadmap

This document is the live roadmap and active backlog for `quawk`.

Historical phase detail, completed task history, and the prior full roadmap
ledger now live in [docs/roadmap-archive.md](roadmap-archive.md).

## Current Status

- `P0` through `P38` are complete.
- `P39` is now active.
- The current claimed `quawk` surface is documented as a best-effort
  POSIX-complete implementation of AWK.
- The NOAA climate-report example now has a reference-awk baseline under
  `one-true-awk` and `gawk --posix`.
- The active backlog is now the measured steady-state runtime performance gap
  closure work for long-running workloads.

## Working Rules

- keep claimed AWK behavior on the compiled backend/runtime path rather than a
  Python semantic fallback
- keep `docs/quawk.ebnf` aligned with the parser contract actually covered by
  tests
- do test-first work for new capability increments
- treat `one-true-awk` and `gawk --posix` as the primary reference engines
- update the live roadmap and relevant contract docs together when scope or
  status changes

## Immediate Next Tasks

The current implementation phase is `P39`.

| ID | Phase | Priority | Task | Depends On | Acceptance | Status |
|---|---|---|---|---|---|---|
| T-325 | P39 | P0 | Build a stable performance benchmark harness | - | A documented NOAA-style benchmark workflow reports both startup-heavy `uv run quawk` timings and steady-state direct-binary timings against `gawk --posix` | done |
| T-326 | P39 | P0 | Add elapsed-time runtime profiling | T-325 | `QUAWK_RUNTIME_PROFILE` or its replacement reports per-helper elapsed time in addition to counts so hot wall-clock costs can be ranked on the benchmark workload | done |
| T-327 | P39 | P0 | Reduce hot-path string capture copies | T-326 | Hot lowering/runtime paths avoid unnecessary `qk_capture_string_arg()` copies without changing observed AWK behavior on focused regressions and the NOAA workload | done |
| T-328 | P39 | P1 | Cache dual string/numeric views on hot values | T-326 | Repeated string/number coercions are reduced for hot scalar or slot-backed values, with focused tests covering cache correctness and benchmark evidence of fewer conversion hot spots | done |
| T-329 | P39 | P1 | Expand slot/local specialization for hot scalar access | T-326 | More hot scalar access sites lower into slots or locals instead of generic name-based runtime lookup, while preserving current semantics and inspection modes | done |
| T-330 | P39 | P1 | Specialize hot comparison paths | T-326 | More definitely-string or definitely-numeric comparisons bypass generic `qk_compare_values`, with focused coverage for mixed-value correctness and benchmark confirmation on the NOAA workload | done |
| T-332 | P39 | P0 | Validate the performance phase against baseline and references | T-327, T-328, T-329, T-330 | Updated steady-state benchmark runs show the post-phase direct-binary results against the recorded baseline and `gawk --posix`, with no regression in the focused correctness suites and reference surfaces used for this phase | pending |

## Active Phase

### P39: Runtime Performance Gap Closure

Objective:
- close the measured steady-state runtime performance gap against `gawk --posix`
  for long-running workloads without weakening the compiled backend/runtime
  execution model

In scope:
- keep a stable NOAA-style benchmark harness, with steady-state timing as the
  decision-making signal for long-running workloads
- extend runtime profiling so optimization work is driven by elapsed-time hot
  spots rather than call counts alone
- reduce hot-path string copying and repeated string/number coercion in the
  runtime
- expand lowering-time specialization for hot scalar access and comparison paths
- re-benchmark after each slice and validate that focused correctness coverage
  still passes

Exit criteria:
- the live benchmark workflow produces reproducible steady-state measurements
  against the stored baseline and `gawk --posix`
- runtime profiling identifies elapsed-time hot spots clearly enough to justify
  the implemented optimization slices
- string capture, coercion, scalar access, and comparison hot paths all have at
  least one landed optimization with focused correctness coverage
- the phase closes only with benchmark-backed evidence of improvement and no
  loss of existing correctness coverage

Validation status:
- focused perf regressions and `compat_corpus` currently pass
- `compat_reference` still has open mismatches in `p.26a`, `p.50`, and `t.a`
- the steady-state NOAA benchmark matches the reference output at `smoke` scale
  but still diverges at `medium` and `large` in the monthly summary output, so
  `T-332` remains open

## Recent Completed Phases

| Phase | Summary |
|---|---|
| P36 | Large implementation modules were split by ownership, with `src/quawk/backend/` and the source map now carrying the main readability burden. |
| P37 | Parser coverage was audited directly against `docs/quawk.ebnf`, and parser-facing grammar/AST docs were brought into line with the tested implementation. |
| P38 | Focused regressions closed the function-local binding and concatenated string-return bugs that the NOAA sample had exposed. |

Earlier completed phases and the full task-by-task ledger are preserved in the
archive.

## Notes For Future Roadmap Updates

- start new implementation work by adding or updating tasks here rather than
  editing the archive
- move completed phase detail to the archive when the live roadmap stops being
  easy to scan
- keep the live roadmap focused on current status, next tasks, and active
  contract decisions
