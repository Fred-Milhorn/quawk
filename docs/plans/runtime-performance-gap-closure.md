# Runtime performance gap closure plan

`quawk` is materially slower than `gawk --posix` on the NOAA climate-report
workload. The gap has two distinct components:

1. **startup overhead**
   - `uv run quawk` exaggerates the gap because environment startup, Python
     process startup, lowering, and compilation dominate small runs
2. **steady-state runtime overhead**
   - even the direct `.venv/bin/quawk` binary remains materially slower than
     `gawk` on a long-running repeated NOAA input

## Current findings

Measured locally on the repo-owned NOAA example fixture:

- startup-heavy loop:
  - `uv run quawk`: about `5.66s`
  - `gawk --posix`: about `0.08s`
- steady-state long run over repeated NOAA input:
  - `.venv/bin/quawk`: about `2.18s`
  - `gawk --posix`: about `0.50s`

Existing runtime call-count profiling (`QUAWK_RUNTIME_PROFILE=1`) shows the
hottest runtime surfaces on the NOAA workload are:

- `qk_capture_string_arg`
- `qk_compare_values`
- `qk_format_number`

These results point to excessive runtime string copying/coercion and generic
mixed-value handling as the first optimization targets. For the long-running
workloads this phase is targeting, startup caching is now out of scope.

## Approach

1. make benchmarking repeatable and comparable
   - keep a stable NOAA-style benchmark harness
   - use the direct-binary steady-state path as the primary validation signal
2. add better runtime timing visibility
   - extend the current runtime profile from call counts to include elapsed time
   - use it to confirm where wall-clock time is actually going
3. reduce string churn in the runtime
   - avoid unconditional `qk_capture_string_arg()` copies
   - capture only when values escape scratch storage or alias mutable buffers
4. reduce repeated string/number coercion
   - cache dual string/numeric views where the runtime already knows both
   - cut repeated `qk_parse_number_text()` / `qk_format_number()` round-trips
5. lower more hot names and compares into specialized fast paths
   - expand slot/local lowering to avoid generic scalar hash lookups
   - prove more comparisons numeric or string at lowering time so fewer go
     through `qk_compare_values`

## Todos

All P39 todos are complete:

1. built a stable benchmark harness for NOAA-like workloads
2. extended runtime profiling to collect elapsed time, not just call counts
3. cut avoidable `qk_capture_string_arg()` copies in hot lowering/runtime paths
4. added cached dual string/numeric value views for hot scalar/slot cases
5. expanded slot/local specialization for hot scalar accesses
6. reduced generic `qk_compare_values` use with more lowering-time specialization
7. re-benchmarked steady-state NOAA workloads and compared against `gawk`

## Validation update

- the benchmark harness supports `--family steady_state` so long-running
  workload validation can ignore startup-heavy timing
- focused perf regressions pass, including the benchmark/profiler harness tests,
  slot/cache regressions, and the direct string `-v` preassignment regression
- `compat_corpus` passes
- `compat_reference` passes
- the steady-state NOAA benchmark matches the reference output at `smoke`,
  `medium`, and `large` scale
- final single-run steady-state measurements in this closeout were:
  `medium` direct `quawk` at `9.96x` `gawk --posix`, and `large` direct
  `quawk` at `3.16x` `gawk --posix`

## Notes

- benchmark with the direct binary for steady-state runtime work; do not use
  `uv run` as the primary signal for runtime-core changes
- keep the NOAA example as one public benchmark, but add a larger repeated-input
  harness so small fixed startup costs do not dominate
- preserve the compiled-backend/runtime execution model; do not add Python-side
  semantic fallbacks in the name of speed
- optimize the shared runtime/lowering paths first, because the NOAA validation
  already exposed multiple real lifetime/capture costs there
- treat profiler output as the gate for new optimization work so we do not
  overfit to intuition
