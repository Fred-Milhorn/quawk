# Roadmap

This document is the live roadmap and active backlog for `quawk`.

Historical phase detail, completed task history, and the prior full roadmap
ledger now live in [docs/roadmap-archive.md](roadmap-archive.md).

## Current Status

- `P0` through `P37` are complete.
- `P38` is now active.
- The current claimed `quawk` surface is documented as a best-effort
  POSIX-complete implementation of AWK.
- The NOAA climate-report example now has a reference-awk baseline under
  `one-true-awk` and `gawk --posix`.
- The active backlog is a focused quawk follow-up on function-local semantics
  and concatenated string-return behavior.

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

The current implementation phase is `P38`.

| ID | Phase | Priority | Task | Depends On | Acceptance | Status |
|---|---|---|---|---|---|---|
| T-318 | P38 | P0 | Add end-to-end regressions for AWK-style extra-parameter locals | - | Direct runtime tests fail under current quawk and pass under the reference awk baseline for representative zero-argument helper and `function f(x,    tmp) { ... }` local-parameter shapes | done |
| T-319 | P38 | P0 | Add regressions for concatenated string returns and helper-built text | - | Direct runtime tests fail under current quawk and pass under the reference awk baseline for simple concatenation, date/helper, and report-fragment string-return shapes | done |
| T-320 | P38 | P1 | Diagnose the function-local binding failure in quawk | T-318 | The implementation path that misbinds or loses AWK-style local parameters is identified and documented in the code or task notes | done |
| T-321 | P38 | P1 | Diagnose the string-return and concatenation failure in quawk | T-319 | The implementation path that collapses returned concatenated strings is identified and documented in the code or task notes | done |
| T-322 | P38 | P0 | Fix quawk function-local semantics | T-320 | AWK-style extra-parameter locals behave like one-true-awk and `gawk --posix` in direct runtime tests | done |
| T-323 | P38 | P0 | Fix quawk string-return semantics | T-321 | Helper-built and concatenated string returns preserve the full expected text in direct runtime tests | done |
| T-324 | P38 | P1 | Validate focused function regressions plus the NOAA sample workflow | T-322, T-323 | The new focused regressions pass and the NOAA sample matches the reference-awk baseline under the documented stdin-streaming workflow | done |

## Active Phase

### P38: Function Semantics Regression Closure

Objective:
- close the newly exposed runtime gaps in function-local binding and
  concatenated string-return behavior, using a reference-awk baseline and
  focused regressions outside the NOAA example

In scope:
- add small direct regressions for AWK-style extra-parameter locals used as true
  function-local storage
- add small direct regressions for helper functions that return concatenated
  strings or formatted report fragments
- diagnose the lowering/runtime path for each failure separately
- fix quawk itself rather than narrowing the example around the bugs
- use the NOAA climate-report sample as a final validation workload after the
  direct regressions are in place

Exit criteria:
- direct tests pin the function-local and string-return failures independently of
  the NOAA example
- quawk matches `one-true-awk` and `gawk --posix` for the new direct
  regressions
- the NOAA bundled-sample workflow matches the reference-awk baseline under both
  direct-file and stdin-stream input shapes
- the roadmap can move `P38` to the completed set without leaving this behavior
  as hidden example-only debt

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
