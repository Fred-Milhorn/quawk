# Roadmap

This document is the live roadmap and active backlog for `quawk`.

Historical phase detail, completed task history, and the prior full roadmap
ledger now live in [docs/roadmap-archive.md](roadmap-archive.md).

## Current Status

- `P0` through `P37` are complete.
- The current claimed `quawk` surface is documented as a best-effort
  POSIX-complete implementation of AWK.
- No implementation phase is currently active.
- There is no active backlog.

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

There is no active implementation task at the moment.

If future priorities change, treat any broader POSIX expression-surface
widening as a new scoped initiative rather than as leftover live backlog from an
older phase.

## Recent Completed Phases

| Phase | Summary |
|---|---|
| P35 | Agent workflow docs were aligned around the current `uv`-first, backend-first workflow. |
| P36 | Large implementation modules were split by ownership, with `src/quawk/backend/` and the source map now carrying the main readability burden. |
| P37 | Parser coverage was audited directly against `docs/quawk.ebnf`, and parser-facing grammar/AST docs were brought into line with the tested implementation. |

Earlier completed phases and the full task-by-task ledger are preserved in the
archive.

## Notes For Future Roadmap Updates

- start new implementation work by adding or updating tasks here rather than
  editing the archive
- move completed phase detail to the archive when the live roadmap stops being
  easy to scan
- keep the live roadmap focused on current status, next tasks, and active
  contract decisions
