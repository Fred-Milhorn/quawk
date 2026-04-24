# Roadmap

This document is the live roadmap and active backlog for `quawk`.

Historical phase detail, completed task history, and the prior full roadmap
ledger now live in [docs/roadmap-archive.md](roadmap-archive.md).

## Current Status

- `P0` through `P39` are complete.
- No new implementation phase is currently selected.
- The current claimed `quawk` surface is documented as a best-effort
  POSIX-complete implementation of AWK.
- The NOAA climate-report example now has a reference-awk baseline under
  `one-true-awk` and `gawk --posix`.
- The most recent active backlog closed the measured steady-state runtime
  performance gap validation work for long-running workloads.

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

No active implementation tasks are currently queued. Start the next phase by
adding its scoped tasks here.

| ID | Phase | Priority | Task | Depends On | Acceptance | Status |
|---|---|---|---|---|---|---|

## Active Phase

No active phase is currently selected.

The next active phase should be added here when scoped.

## Recent Completed Phases

| Phase | Summary |
|---|---|
| P36 | Large implementation modules were split by ownership, with `src/quawk/backend/` and the source map now carrying the main readability burden. |
| P37 | Parser coverage was audited directly against `docs/quawk.ebnf`, and parser-facing grammar/AST docs were brought into line with the tested implementation. |
| P38 | Focused regressions closed the function-local binding and concatenated string-return bugs that the NOAA sample had exposed. |
| P39 | Runtime performance gap closure added steady-state NOAA benchmarking, elapsed-time profiling, hot-path scalar/string optimizations, numeric array accumulation caching, and final reference validation. |

Earlier completed phases and the full task-by-task ledger are preserved in the
archive.

## Notes For Future Roadmap Updates

- start new implementation work by adding or updating tasks here rather than
  editing the archive
- move completed phase detail to the archive when the live roadmap stops being
  easy to scan
- keep the live roadmap focused on current status, next tasks, and active
  contract decisions
