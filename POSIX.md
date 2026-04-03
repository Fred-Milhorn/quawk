# POSIX Plan

This document is the starting plan for bringing `quawk` to an honest,
reviewable POSIX-compatibility contract.

It has three goals:

1. align [SPEC.md](/Users/fred/dev/quawk/SPEC.md) with expected POSIX behavior
2. identify and document the gaps between POSIX behavior and the current
   `quawk` implementation
3. define the work required to close those gaps

It also adopts this architectural constraint:

- Python is the compiler driver and orchestration layer
- AWK program semantics should execute in the compiled backend/runtime, not in a
  Python interpreter fallback

This is a planning document, not the source of truth for current shipped
behavior. Current shipped behavior still lives in [SPEC.md](/Users/fred/dev/quawk/SPEC.md),
[docs/design.md](/Users/fred/dev/quawk/docs/design.md), tests, and the reviewed
upstream manifest at
[tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml).

## Scope

In scope:

- POSIX `awk` public execution behavior
- CLI behaviors that are part of normal POSIX `awk` usage
- parser and runtime behavior needed to execute POSIX-valid programs
- compatibility evidence and documentation needed to support POSIX claims

Out of scope here:

- GNU-only `awk` extensions
- backend-only implementation details unless they block a POSIX public claim or
  violate the compiler-only role of the Python layer
- non-behavioral performance work

## Deliverables

This plan will be complete when the repo has:

- a `SPEC.md` that clearly distinguishes POSIX-required behavior, current gaps,
  extensions, and out-of-scope areas
- a checked-in POSIX gap inventory tied to code, tests, and reviewed upstream
  evidence
- a task backlog that can be executed incrementally until public POSIX claims
  are honest and well-covered

## Working Rules

Use these rules while executing the plan:

- do not claim a POSIX feature as `implemented` in `SPEC.md` if public `quawk`
  execution still rejects a normal POSIX use of that feature
- do not treat backend-only gaps as POSIX public-execution gaps unless they
  contradict a public `--ir` or `--asm` claim
- do not accept Python-side AWK semantic fallback as a steady-state solution
  for claimed POSIX behavior
- prefer verified gaps from tests and upstream-reviewed skips over memory or
  assumptions
- classify every mismatch as one of:
  - `spec-overclaim`
  - `parser-gap`
  - `runtime-gap`
  - `backend-only-gap`
  - `architecture-gap`
  - `compatibility-mismatch`
  - `extension-doc-gap`

### Architectural Rule

For this plan, `quawk` is an ahead-of-time compiler frontend plus backend
runtime, not a mixed compiler/interpreter.

That means:

- Python may parse, validate, normalize, compile, link, and drive tooling
- Python may not be the long-term execution engine for AWK program semantics
- any feature that only works because the Python host runtime interprets it
  remains incomplete for the target architecture, even if user-visible output is
  currently correct
- `SPEC.md` should not describe Python-side semantic fallback as the intended
  implementation model
- backend parity work is not optional cleanup; it is part of reaching the
  intended `quawk` architecture

## Phase 1: Align SPEC.md

Objective:

- make `SPEC.md` a reliable POSIX-facing contract instead of a coarse feature
  checklist

Work items:

1. audit every `implemented`, `partial`, and `planned` row in
   [SPEC.md](/Users/fred/dev/quawk/SPEC.md) against POSIX behavior, current
   tests, and reviewed upstream skips
2. split rows that currently collapse too much behavior into one label
   Example:
   `print` and `printf` should not hide multi-argument `print`, bare `print`,
   `OFS`, `ORS`, and `printf` formatting gaps.
3. distinguish public execution from backend inspection explicitly
   `SPEC.md` already starts this for `--ir` / `--asm`, but the same discipline
   is needed everywhere POSIX behavior is broader than backend parity.
4. mark non-POSIX admitted forms as extensions instead of letting them blur the
   POSIX contract
   Current examples already called out in the repo:
   - parenthesized `for ... in` iterable form
   - expression-list `for` init/update forms
5. add a POSIX-facing status note to each runtime area:
   - `aligned`
   - `partial`
   - `not yet implemented`
   - `extension`
   - `out-of-scope`
6. add an implementation-model note wherever current public execution still
   depends on Python-side semantic fallback
   Those notes should identify such behavior as transition debt, not the target
   design.

Acceptance:

- every row in `SPEC.md` can be defended against current tests and reviewed
  upstream evidence
- no known POSIX public-execution gap remains hidden behind a broad
  `implemented` row

## Phase 2: Build the POSIX Gap Inventory

Objective:

- create one reviewed inventory of all known POSIX gaps between the standard
  behavior and current `quawk`

Sources of truth for the inventory:

- [SPEC.md](/Users/fred/dev/quawk/SPEC.md)
- [docs/design.md](/Users/fred/dev/quawk/docs/design.md)
- [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml)
- existing CLI, parser, runtime, backend, corpus, and upstream pytest coverage

The inventory should track for each gap:

- area
- POSIX behavior expected
- current `quawk` behavior
- gap classification
- evidence
- likely ownership area
- whether the gap blocks `SPEC.md` alignment immediately

### Initial Verified Gap Inventory

The following gaps are already confirmed by checked-in code, tests, or reviewed
upstream skips.

#### Output and Print Surface

- output redirection and pipe output for `print` are outside the current claimed
  surface.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L433),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L442)
- `printf` still has at least one reviewed formatting mismatch.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L223)
- `printf` still has at least one parser/runtime gap around
  `substr(..., ..., ...)` inside `printf`.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L760)

#### Builtin Functions

- the current claimed builtin-function set now includes `atan2`, `close`,
  `cos`, `exp`, `gsub`, `index`, `int`, `length`, `log`, `match`, `rand`,
  `sin`, `split`, `sqrt`, `srand`, `sprintf`, `sub`, `substr`, `system`,
  `tolower`, and `toupper`.
  Evidence:
  [src/quawk/builtins.py](/Users/fred/dev/quawk/src/quawk/builtins.py#L5),
  [SPEC.md](/Users/fred/dev/quawk/SPEC.md#L59)
- reviewed upstream corroboration for `rand()` is still narrower than the
  direct coverage because the pinned references disagree on seeded randomized
  output.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L459)
- reviewed upstream skips show a real `split` behavior mismatch.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L751)
- `getline` is now implemented for the currently claimed POSIX forms:
  bare `getline`, `getline var`, `getline < file`, and `getline var < file`.
  Coverage:
  parser, CLI, runtime-baseline, JIT, and runtime-ABI tests.

#### Builtin Variables

- the implemented builtin-variable set now includes `NR`, `FNR`, `NF`,
  `FILENAME`, `OFS`, `ORS`, `OFMT`, `CONVFMT`, `RSTART`, and `RLENGTH`.
  Evidence:
  [src/quawk/builtins.py](/Users/fred/dev/quawk/src/quawk/builtins.py#L6),
  [SPEC.md](/Users/fred/dev/quawk/SPEC.md#L58)
- `ARGC`, `ARGV`, `ENVIRON`, and `SUBSEP` are now implemented and covered by
  direct CLI/runtime/JIT tests.
- the reviewed builtin-variable sequencing mismatch `END { print NR }` is now
  clean under direct tests and the runnable upstream subset case `one-true-awk:p.6`.

#### CLI and Preassignment

- string-valued `-v` assignments are now implemented and part of the claimed
  CLI surface.
- upstream corroboration for CLI-sensitive `ARGV` / `ARGC` behavior now
  includes the runnable direct-file case `one-true-awk:p.48a`; broader gawk
  operand-shape cases remain reviewed skips because their direct fixture
  adapters are not yet clean corroborating anchors.

#### Parser and Syntax Gaps

- backslash-continued multi-line `print` is now handled as normal POSIX line
  continuation and corroborated by the runnable upstream subset cases
  `one-true-awk:p.26` and `one-true-awk:p.26a`.
- reviewed newline-sensitive `if`, `for`, and `do ... while` forms now parse
  cleanly enough to promote `one-true-awk:t.a`, `one-true-awk:t.break`, and
  `one-true-awk:t.do`.
- the remaining reviewed `p.7`, `p.8`, and `p.21a` skips are no longer parser
  gaps; they are now classified precisely as semantic expression-pattern
  mismatches.

#### Pattern and Record Semantics

- some non-regex expression-pattern cases still mismatch under default-print
  behavior.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L250),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L259)
- one reviewed skip says the reusable backend record-selection path still
  narrows some non-regex expression patterns.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L259)

#### Backend-Only Gaps

- `--ir` and `--asm` still do not cover every public execution path.
  Evidence:
  [SPEC.md](/Users/fred/dev/quawk/SPEC.md#L75),
  [docs/design.md](/Users/fred/dev/quawk/docs/design.md#L203)
- the checked-in `T-150` audit expands that list into explicit claimed-family
  anchors, including expression-pattern selection, default-print expression
  patterns, `do ... while`, loop `break` or `continue`, `next`, `nextfile`,
  `exit`, user-defined functions, and scalar-string coercion paths.
  Evidence:
  [tests/architecture/audit.toml](/Users/fred/dev/quawk/tests/architecture/audit.toml#L1),
  [tests/test_architecture_audit.py](/Users/fred/dev/quawk/tests/test_architecture_audit.py#L1)

#### Architecture Gaps

- the current design docs still describe a public model where some AWK programs
  run through Python-host fallback instead of the compiled backend/runtime.
  Evidence:
  [docs/design.md](/Users/fred/dev/quawk/docs/design.md#L203),
  [docs/design.md](/Users/fred/dev/quawk/docs/design.md#L223)
- if the intended product is AOT-only execution, every remaining host-runtime
  family is an architecture gap in addition to any POSIX gap.
- the remaining documented host-runtime families should be kept current as
  backend parity work lands; stale examples weaken the AOT-only contract.

### Inventory Tasks

- keep the verified list above current as gaps are fixed or reclassified
- add any missing POSIX-required areas not yet represented by upstream review
- keep the checked-in architecture cross-reference in
  [tests/architecture/audit.toml](/Users/fred/dev/quawk/tests/architecture/audit.toml)
  aligned with the code and docs

### T-150 Backend Gap Baseline

`T-150` is now complete.

The checked-in architecture audit baseline lives in:

- [tests/architecture/audit.toml](/Users/fred/dev/quawk/tests/architecture/audit.toml)
- [src/quawk/architecture_audit.py](/Users/fred/dev/quawk/src/quawk/architecture_audit.py)
- [tests/test_architecture_audit.py](/Users/fred/dev/quawk/tests/test_architecture_audit.py)

There are no remaining audited claimed families lacking full backend/runtime
execution or `--ir` / `--asm` support.

### T-151 Function Backend Result

`T-151` is now complete for the first representative direct-BEGIN function
subset.

What landed:

- representative user-defined function programs no longer route through the
  Python host runtime when they fit the direct numeric backend subset
- `--ir` and `--asm` now work for that same function subset
- the checked-in architecture audit now treats `user-defined-functions` as
  backend-supported instead of still blocking the AOT contract

### T-152 Exit And Nextfile Backend Result

`T-152` is now complete for the representative `exit` and `nextfile` control
paths.

What landed:

- reusable backend lowering now supports `nextfile` by advancing the runtime to
  the next input file instead of falling back to Python
- reusable backend lowering now supports `exit` by recording runtime exit state
  that the execution driver honors while still running `END`
- `--ir` and normal execution now work for representative claimed `exit` and
  `nextfile` programs
- the checked-in architecture audit no longer treats `record-control-exit` or
  `record-control-nextfile` as blocking backend gaps

### T-153 Scalar-String Backend Result

`T-153` is now complete for the representative scalar-string coercion family.

What landed:

- reusable backend lowering now routes representative scalar variables through a
  typed runtime scalar ABI instead of depending on Python-side value execution
- compiled execution now preserves AWK-style string-to-number coercion,
  concatenation, and unset-scalar string behavior for the representative
  claimed family
- `--ir` and normal execution now work for representative scalar-string
  programs such as `BEGIN { x = "12"; print x + 1; print x "a" }`
- the checked-in architecture audit no longer treats
  `scalar-string-coercions` as a blocking backend gap

### T-155 Audited Backend Parity Result

`T-155` is now complete for the remaining audited backend-parity families.

What landed:

- reusable backend lowering now supports non-regex expression-pattern record
  selection instead of limiting record matching to regex-only predicates
- representative `next`, `do ... while`, loop `break` or `continue`, and bare
  expression-pattern default-print programs now execute through the compiled
  backend/runtime path and support `--ir` / `--asm`
- the checked-in architecture audit is now clean: every audited claimed family
  has compiled execution plus inspection support
- `T-156` remains responsible for rebaselining the broader AOT-only contract
  docs and any remaining fallback-story cleanup around the full claimed surface

### T-156 AOT Contract Rebaseline Result

`T-156` is now complete.

What landed:

- `SPEC.md` now distinguishes the currently claimed AOT-backed expression subset
  from broader frontend-admitted POSIX forms that still remain outside the
  claimed contract
- `docs/design.md` now states that all currently claimed language families
  execute through the compiled backend/runtime path, with broader unclaimed
  POSIX forms explicitly called out as `P14` work instead of being described as
  claimed fallback families
- the roadmap now treats `P13` as complete and advances the next deliverable to
  `P14` POSIX compatibility completion

### T-157 SPEC Posix-Facing Split Result

`T-157` is now complete.

What landed:

- `SPEC.md` now splits the old broad CLI-variable row into numeric and string
  `-v` behavior so the unsupported string-preassignment gap is explicit
- the old output/builtin compression is now split into single-argument
  `print`, bare `print`, multi-argument `print`, separator-variable behavior,
  `printf` parity, output redirection, builtin-variable families, builtin
  families, and `getline`
- backend parity now distinguishes the claimed AOT-backed surface from broader
  frontend-admitted POSIX forms that are still outside the current contract

### T-158 Print Surface Result

`T-158` is now complete.

What landed:

- bare `print` now follows POSIX `$0` defaulting instead of failing outside the
  one-argument path
- multi-argument `print` now joins arguments with `OFS`
- `ORS` now controls the output terminator for explicit and implicit `print`
  paths
- the reusable backend/runtime path and the host runtime now share the same
  print-surface behavior, with focused CLI, JIT, runtime, and runtime-support
  tests covering the result

### T-159 Formatting Variable Result

`T-159` is now complete.

What landed:

- `OFMT` now controls numeric `print` formatting
- `CONVFMT` now controls ordinary numeric-to-string coercion such as
  concatenation and other string-oriented conversions
- the host runtime and reusable backend/runtime path now share that formatting
  behavior, including runtime-side formatting for array-key coercion and scalar
  string views

## Phase 3: Task Backlog To Reach POSIX Compatibility

Task IDs below are proposed planning IDs for POSIX work. They do not replace
the roadmap yet.

### SPEC Alignment Tasks

#### POSIX-001: Audit SPEC rows against POSIX public behavior

Acceptance:

- every row in `SPEC.md` is reviewed against POSIX behavior, current tests, and
  upstream evidence
- each row is marked `aligned`, `partial`, `extension`, or `out-of-scope` in
  prose or notes

#### POSIX-002: Split over-broad SPEC rows

Acceptance:

- `print`, builtin variables, builtins, CLI variables, and backend parity are
  represented with enough granularity that no known POSIX gap is hidden

#### POSIX-003: Mark admitted non-POSIX forms explicitly as extensions

Acceptance:

- current admitted extensions remain documented without confusing the POSIX
  contract

#### POSIX-004: Rewrite SPEC and design language around the execution model

Acceptance:

- `SPEC.md` and `docs/design.md` describe Python as the compile/orchestration
  layer only
- any remaining Python-side AWK semantic execution is described as transition
  debt to be removed
- no doc text presents mixed Python execution as the intended end-state

### Public Execution Tasks

#### POSIX-010: Implement full POSIX `print`

Scope:

- bare `print`
- multi-argument `print`
- `OFS`
- `ORS`

Acceptance:

- local CLI and corpus tests cover all four behaviors
- reviewed upstream print-surface skips can be promoted or narrowed sharply

#### POSIX-011: Implement output redirection and pipe output

Scope:

- `print > file`
- `print >> file`
- `print | command`
- `close()`

Acceptance:

- currently reviewed out-of-surface POSIX cases move into claimed support or
  remain explicitly deferred in `SPEC.md`

### T-160 Output Redirection Result

- `print` and literal-format `printf` now support `>`, `>>`, and `|` in both
  the host runtime and the reusable backend/runtime path
- `close()` now closes redirected files and pipes by the same AWK string used
  to open them
- `SPEC.md` now treats output redirection and pipe output as part of the
  claimed surface

#### POSIX-012: Close reviewed `printf` parity gaps

Scope:

- string-width formatting parity
- `substr(..., ..., ...)` in `printf`
- any remaining specifier/argument coercion mismatches

Acceptance:

- the reviewed `p.5` / `p.5a` class of upstream skips is either promoted or
  replaced by more specific classified gaps

### T-161 Printf Parity Result

- parenthesized `printf(...)` now parses and executes through both the host
  runtime and the reusable backend/runtime path
- the reviewed `gawk:substr` case is now runnable because three-argument
  `substr(...)` inside `printf` is no longer blocked by the parser
- the older `p.5` / `p.5a` skips were narrowed to the real remaining gap:
  `FS = "\t"` field splitting, not `printf` string-width formatting

### T-162 String And Regex Builtin Result

- `index`, `match`, `sub`, `gsub`, `sprintf`, `tolower`, and `toupper` now
  execute through both the host runtime and the reusable backend/runtime path
- `match()` now updates `RSTART` and `RLENGTH`, and those variables are part of
  the current claimed builtin-variable surface
- the upstream compatibility subset now promotes `one-true-awk:t.printf` as
  corroborating `sprintf` coverage, while `one-true-awk:p.29` stays a narrower
  reviewed skip because record-target `gsub` still has a cwd-sensitive backend
  crash under installed-command execution

### Builtin Function Tasks

#### POSIX-020: Enumerate the full POSIX builtin-function contract

Acceptance:

- `POSIX.md` and `SPEC.md` both list the standard builtin functions that
  `quawk` must support for POSIX alignment

#### POSIX-021: Implement the missing string and regex builtins

Likely scope:

- `index`
- `match`
- `sub`
- `gsub`
- `sprintf`
- `tolower`
- `toupper`

Acceptance:

- builtins move from “partial” toward explicit POSIX coverage with tests and
  upstream corroboration

#### POSIX-022: Implement the missing numeric and system builtins

Completed scope:

- `int`
- `rand`
- `srand`
- `system`
- `atan2`
- `cos`
- `sin`
- `exp`
- `log`
- `sqrt`

Acceptance:

- each builtin has direct semantics/runtime/backend coverage
- the upstream subset includes corroborating `system()` coverage
- `rand()` remains documented as a narrower direct-only case until the pinned
  references agree on a stable seeded-output anchor

#### POSIX-023: Implement `getline`

Status:

- done via `T-164`

Acceptance:

- grammar, parser, semantics, and runtime all support the POSIX forms that the
  repo intends to claim
- `SPEC.md` reflects the exact supported forms

### Builtin Variable Tasks

#### POSIX-030: Enumerate the full POSIX builtin-variable contract

Acceptance:

- `SPEC.md` stops presenting four implemented variables as if that exhausted the
  POSIX surface

#### POSIX-031: Implement output and formatting variables

Scope:

- `OFS`
- `ORS`
- `OFMT`
- `CONVFMT`

Acceptance:

- `print` and numeric/string formatting obey the POSIX variables that influence
  output

#### POSIX-032: Implement CLI and environment variables

Status:

- done via `T-164`

Scope:

- `ARGC`
- `ARGV`
- `ENVIRON`

Acceptance:

- CLI-sensitive upstream cases can run without reviewed skips due to missing
  `ARGV` shape

#### POSIX-033: Implement regex-result and array-separator variables

Status:

- `SUBSEP` done via `T-164`; builtin-variable sequencing done via `T-165`

Scope:

- `SUBSEP`

Acceptance:

- remaining builtin/function semantics that depend on these variables are
  correctly tested

### Parser and Runtime Tasks

#### POSIX-040: Close multiline and continuation parser gaps

Status:

- done via `T-165`

Scope:

- backslash continuation
- newline-sensitive `if`, `for`, `do ... while`, and function-body forms

Acceptance:

- the reviewed parser-gap upstream skips move to `run` or to narrower non-parser
  classifications

#### POSIX-041: Close remaining default-print and expression-pattern mismatches

Status:

- done via `T-165`

Acceptance:

- the reviewed `p.7`, `p.8`, and `p.21a` style mismatches are either fixed or
  reclassified with precise non-POSIX justification

#### POSIX-042: Fix builtin-variable sequencing mismatches

Status:

- done via `T-165`

Acceptance:

- reviewed cases like `END { print NR }` become clean

### T-165 Parser And Sequencing Result

- backslash-newline continuation now lexes as trivia, so POSIX multi-line
  `print` forms no longer fail in the frontend
- newline-sensitive `if`, `for`, and `do ... while` bodies no longer block the
  reviewed multiline subset cases `p.26`, `p.26a`, `t.a`, `t.break`, and `t.do`
- `END`-only programs now consume main input before `END`, so `one-true-awk:p.6`
  is a clean runnable corroborating case for final `NR`
- the reviewed `p.7`, `p.8`, and `p.21a` cases remain skipped, but now with
  precise semantic mismatch reasons instead of parser-gap placeholders

### Compatibility and Evidence Tasks

#### POSIX-050: Re-audit the upstream manifest after each major semantic fix

Acceptance:

- no stale skip reason remains after the underlying gap is fixed

### T-166 Upstream Manifest Re-Audit Result

- the runnable upstream subset now includes corroborating direct-file cases for
  bare and multi-argument `print`, `NR` / `FILENAME`, `OFS` / `ORS`, output
  redirection, `ARGC` / `ARGV`, and the multiline/parser forms fixed in `T-165`
- newly promoted runnable cases include `p.1`, `p.2`, `p.4`, `p.24`, `p.27`,
  `p.34`, `p.38`, `p.40`, `p.41`, `p.42`, `p.44`, `p.45`, `p.47`, `p.48a`,
  `t.exit`, and `t.if`
- remaining reviewed skips now carry narrower current reasons such as missing
  `FS` assignment support, a bare-`length` mismatch, non-UTF-8 fixture input,
  numeric comparison mismatches under pattern selection or `next`, and a small
  set of reusable-backend crashes

#### POSIX-051: Promote upstream cases that directly corroborate fixed gaps

Remaining priority promotion targets after `T-166`:

- `getnr2tb`
- `splitvar`
- any remaining clean `FS`-sensitive direct-file anchors once field-separator
  assignment is implemented
- any remaining clean `next`-sensitive and `$0`-rebuild anchors once the
  reviewed numeric-comparison and backend-crash gaps are fixed

Acceptance:

- every major fixed POSIX gap gains upstream corroboration when a clean case
  exists

#### POSIX-052: Expand local corpus and direct CLI tests for POSIX-only claims

Acceptance:

- every POSIX claim in `SPEC.md` has direct repo-owned test coverage even before
  upstream corroboration is added

### Backend and Inspection Tasks

#### POSIX-060: Re-audit backend claims after public POSIX gaps shrink

Acceptance:

- backend rows in `SPEC.md` remain honest as public execution expands

#### POSIX-061: Close backend-only gaps for the final claimed POSIX surface

Acceptance:

- any POSIX behavior still requiring host-runtime fallback is either lowered or
  explicitly documented as outside current backend inspection support

#### POSIX-062: Eliminate Python-side semantic fallback for claimed POSIX behavior

Acceptance:

- every POSIX behavior claimed as implemented executes in the backend/runtime
- Python remains only the frontend/compiler driver and process orchestration
  layer
- the design docs no longer list host-runtime semantic families as an accepted
  steady state

Planning note:

- do not land this as a standalone public regression step for still-claimed
  behavior
- remove fallback only in the same implementation wave that closes the
  remaining claimed backend-execution and inspection gaps
- in roadmap terms, the fallback-removal intent is now folded into the
  remaining parity wave rather than treated as a separate post-`T-153` step

## Remaining Execution Order

The implementation backlog is now down to evidence and final contract cleanup:

1. `POSIX-052`
2. `POSIX-060` through `POSIX-062` only if a new POSIX claim exposes a backend-only gap

Why this order:

- the highest-value remaining work is to make `SPEC.md`, this plan, and the
  reviewed manifest agree on the narrowed remaining POSIX surface
- `SPEC.md`, this plan, and the reviewed manifest should converge before any
  further claim expansion
- backend-only follow-up should happen only when the public POSIX contract
  actually requires it

## Immediate Next Steps

The next concrete follow-up after this document should be:

1. execute `POSIX-052` / `T-167` so `SPEC.md`, `POSIX.md`, and the manifest
   agree on the remaining in-scope POSIX surface
2. decide whether any remaining backend-only mismatches deserve new public POSIX
   claims or should stay explicitly out of scope

## Notes

This plan should stay stricter than the current compatibility plan:

- [docs/compatibility.md](/Users/fred/dev/quawk/docs/compatibility.md) is about
  the reviewed upstream suite and its growth policy
- `POSIX.md` is about the full standard-alignment gap inventory and the work
  needed to make the public contract honestly POSIX-compatible
