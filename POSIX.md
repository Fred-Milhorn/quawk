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

- `print` only supports one explicit argument in both the host runtime and the
  backend-lowered path.
  Evidence:
  [src/quawk/jit.py](/Users/fred/dev/quawk/src/quawk/jit.py#L1994),
  [src/quawk/jit.py](/Users/fred/dev/quawk/src/quawk/jit.py#L508)
- bare `print` remains unsupported as a normal POSIX form.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L176),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L617)
- multi-argument `print` remains unsupported.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L194),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L220)
- `OFS` and `ORS` driven `print` behavior is missing.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L424)
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

- the supported builtin-function set is still only `length`, `split`, and
  `substr`.
  Evidence:
  [src/quawk/builtins.py](/Users/fred/dev/quawk/src/quawk/builtins.py#L5),
  [SPEC.md](/Users/fred/dev/quawk/SPEC.md#L59)
- reviewed upstream skips already show missing POSIX builtins such as `gsub`
  and `system`.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L307),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L469)
- reviewed upstream skips show a real `split` behavior mismatch.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L751)
- `getline` does not appear in the current lexer, parser, semantics, or builtin
  metadata at all, so it should be treated as not implemented until proven
  otherwise.

#### Builtin Variables

- the supported builtin-variable set is still only `NR`, `FNR`, `NF`, and
  `FILENAME`.
  Evidence:
  [src/quawk/builtins.py](/Users/fred/dev/quawk/src/quawk/builtins.py#L6),
  [SPEC.md](/Users/fred/dev/quawk/SPEC.md#L58)
- standard variables such as `OFS`, `ORS`, `OFMT`, `CONVFMT`, `ARGC`, `ARGV`,
  `ENVIRON`, `RSTART`, `RLENGTH`, and `SUBSEP` should be treated as missing
  until implemented and tested.
- there is at least one reviewed builtin-variable sequencing mismatch:
  `END { print NR }`.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L241)

#### CLI and Preassignment

- string-valued `-v` assignments are still unsupported.
  Evidence:
  [SPEC.md](/Users/fred/dev/quawk/SPEC.md#L19)
- `ARGV` and `ARGC` coverage is still incomplete and currently represented only
  by reviewed skips and focused shell-driver coverage.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L451),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L702)

#### Parser and Syntax Gaps

- backslash-continued multi-line `print` still exposes a parser continuation
  gap.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L268)
- several multiline POSIX forms still expose newline-handling parser gaps.
  Evidence:
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L390),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L398),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L407),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L416),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L644),
  [tests/upstream/selection.toml](/Users/fred/dev/quawk/tests/upstream/selection.toml#L653)

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
  `exit`, user-defined functions, and richer scalar-string coercion paths.
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
- the current documented host-runtime families include user-defined functions,
  `exit`, `nextfile`, and richer scalar-string execution paths.

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

Current audited claimed families that still lack full backend/runtime execution
or `--ir` / `--asm` support:

| Family | Representative program | Current audited gap |
|---|---|---|
| `record-control-next` | `/skip/ { next } { print $0 }` | simple `next`-driven record control still falls back and has no inspection support |
| `scalar-string-coercions` | `BEGIN { x = "12"; print x + 1; print x "a" }` | richer scalar-string and concatenation paths still depend on host-side execution |
| `control-flow-do-while` | `BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }` | `do ... while` is claimed publicly but still lacks full backend execution and inspection support |
| `control-flow-loop-break-continue` | `BEGIN { for (i = 0; i < 5; i = i + 1) { if (i == 2) break; else continue } }` | representative loop-control programs still do not stay on the compiled backend path |
| `expression-pattern-actions` | `1 { print $0 }` | expression-pattern selection is claimed, but the backend only lowers regex expression patterns today |
| `default-print-expression-patterns` | `1` | bare expression-pattern default-print behavior still lacks full backend execution and inspection support |

### T-151 Function Backend Result

`T-151` is now complete for the first representative direct-BEGIN function
slice.

What landed:

- representative user-defined function programs no longer route through the
  Python host runtime when they fit the direct numeric backend subset
- `--ir` and `--asm` now work for that same function slice
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

#### POSIX-012: Close reviewed `printf` parity gaps

Scope:

- string-width formatting parity
- `substr(..., ..., ...)` in `printf`
- any remaining specifier/argument coercion mismatches

Acceptance:

- the reviewed `p.5` / `p.5a` class of upstream skips is either promoted or
  replaced by more specific classified gaps

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

Likely scope:

- `int`
- `rand`
- `srand`
- `system`
- any remaining POSIX math builtins required by the standard profile adopted by
  the repo

Acceptance:

- each builtin has parser, semantics, runtime, and compatibility coverage

#### POSIX-023: Implement `getline`

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

Scope:

- `ARGC`
- `ARGV`
- `ENVIRON`

Acceptance:

- CLI-sensitive upstream cases can run without reviewed skips due to missing
  `ARGV` shape

#### POSIX-033: Implement regex-result and array-separator variables

Scope:

- `RSTART`
- `RLENGTH`
- `SUBSEP`

Acceptance:

- builtin/function semantics that depend on these variables are correctly
  tested

### Parser and Runtime Tasks

#### POSIX-040: Close multiline and continuation parser gaps

Scope:

- backslash continuation
- newline-sensitive `if`, `for`, `do ... while`, and function-body forms

Acceptance:

- the reviewed parser-gap upstream skips move to `run` or to narrower non-parser
  classifications

#### POSIX-041: Close remaining default-print and expression-pattern mismatches

Acceptance:

- the reviewed `p.7`, `p.8`, and `p.21a` style mismatches are either fixed or
  reclassified with precise non-POSIX justification

#### POSIX-042: Fix builtin-variable sequencing mismatches

Acceptance:

- reviewed cases like `END { print NR }` become clean

### Compatibility and Evidence Tasks

#### POSIX-050: Re-audit the upstream manifest after each major semantic fix

Acceptance:

- no stale skip reason remains after the underlying gap is fixed

#### POSIX-051: Promote upstream cases that directly corroborate fixed gaps

Priority promotion targets after comment support:

- `getnr2tb`
- `splitvar`
- `substr`
- the print-surface `p.*` and `t.*` cases currently blocked only by print
  semantics

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

## Recommended Execution Order

Use this order so `SPEC.md` stops overclaiming early and the highest-value POSIX
gaps close first:

1. `POSIX-001` through `POSIX-003`
2. `POSIX-004`
3. `POSIX-010` and `POSIX-031`
4. `POSIX-040` and `POSIX-042`
5. `POSIX-020` through `POSIX-023`
6. `POSIX-030` through `POSIX-033`
7. `POSIX-041`
8. `POSIX-050` through `POSIX-052`
9. `POSIX-060` through `POSIX-062`

Why this order:

- `print` plus `OFS` / `ORS` unlocks a large number of currently reviewed
  upstream skips
- parser cleanup removes false negatives that currently hide real semantic gaps
- builtin and builtin-variable enumeration is necessary before `SPEC.md` can be
  trusted as a POSIX contract
- the execution-model rewrite needs to happen early so later tasks are planned
  against the intended AOT architecture instead of the current transitional
  mixed model

## Immediate Next Steps

The first concrete follow-up after this document should be:

1. update `SPEC.md` so it stops over-compressing POSIX areas such as `print`,
   builtin variables, and builtins
2. update `SPEC.md` and `docs/design.md` for `POSIX-004` so Python fallback is
   documented as transition debt, not target architecture
3. create a focused task for `POSIX-010` full POSIX `print`
4. create a focused task for `POSIX-031` output and formatting variables
5. create a focused task for `POSIX-040` multiline and continuation parser gaps

## Notes

This plan should stay stricter than the current compatibility plan:

- [docs/compatibility.md](/Users/fred/dev/quawk/docs/compatibility.md) is about
  the reviewed upstream suite and its growth policy
- `POSIX.md` is about the full standard-alignment gap inventory and the work
  needed to make the public contract honestly POSIX-compatible
