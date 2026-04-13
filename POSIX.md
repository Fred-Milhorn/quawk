# POSIX Status And Gap Record

This document records `quawk`'s POSIX-alignment status, remaining reviewed
gaps, and the historical implementation notes behind the completed POSIX work.

It has three jobs:

1. keep [SPEC.md](SPEC.md) aligned with expected POSIX behavior
2. record the remaining reviewed gaps between POSIX behavior and the current
   `quawk` implementation
3. preserve the implementation history and rationale behind the completed
   `P13` through `P15` closeout work

It also adopts this architectural constraint:

- Python is the compiler driver and orchestration layer
- AWK program semantics should execute in the compiled backend/runtime, not in a
  Python interpreter fallback

This is a supporting status and audit document, not the primary source of truth
for current shipped behavior. Current shipped behavior still lives in
[SPEC.md](SPEC.md), [docs/design.md](docs/design.md), tests, and the reviewed
upstream manifest at [tests/upstream/selection.toml](tests/upstream/selection.toml).

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

## Role

This record is useful when the repo has:

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

## Historical Phase 1: Align SPEC.md

Objective:

- make `SPEC.md` a reliable POSIX-facing contract instead of a coarse feature
  checklist

Work items:

1. audit every `implemented`, `partial`, and `planned` row in
   [SPEC.md](SPEC.md) against POSIX behavior, current
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

## Historical Phase 2: Build the POSIX Gap Inventory

Objective:

- create one reviewed inventory of all known POSIX gaps between the standard
  behavior and current `quawk`

Sources of truth for the inventory:

- [SPEC.md](SPEC.md)
- [docs/design.md](docs/design.md)
- [tests/upstream/selection.toml](tests/upstream/selection.toml)
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
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L433),
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L442)
- `printf` still has at least one reviewed formatting mismatch.
  Evidence:
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L223)
- `printf` still has at least one parser/runtime gap around
  `substr(..., ..., ...)` inside `printf`.
  Evidence:
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L760)

#### Builtin Functions

- the current claimed builtin-function set now includes `atan2`, `close`,
  `cos`, `exp`, `gsub`, `index`, `int`, `length`, `log`, `match`, `rand`,
  `sin`, `split`, `sqrt`, `srand`, `sprintf`, `sub`, `substr`, `system`,
  `tolower`, and `toupper`.
  Evidence:
  [src/quawk/builtins.py](src/quawk/builtins.py#L5),
  [SPEC.md](SPEC.md#L59)
- reviewed upstream corroboration for `rand()` is still narrower than the
  direct coverage because the pinned references disagree on seeded randomized
  output.
  Evidence:
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L459)
- reviewed upstream skips show a real `split` behavior mismatch.
  Evidence:
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L751)
- `getline` is now implemented for the currently claimed POSIX forms:
  bare `getline`, `getline var`, `getline < file`, and `getline var < file`.
  Coverage:
  parser, CLI, runtime-baseline, JIT, and runtime-ABI tests.

#### Builtin Variables

- the implemented builtin-variable set now includes `NR`, `FNR`, `NF`,
  `FILENAME`, `OFS`, `ORS`, `OFMT`, `CONVFMT`, `RSTART`, and `RLENGTH`.
  Evidence:
  [src/quawk/builtins.py](src/quawk/builtins.py#L6),
  [SPEC.md](SPEC.md#L58)
- `ARGC`, `ARGV`, `ENVIRON`, and `SUBSEP` are now implemented and covered by
  direct CLI/runtime/JIT tests.
- the reviewed builtin-variable sequencing mismatch `END { print NR }` is now
  clean under direct tests and the runnable upstream subset case `one-true-awk:p.6`.

#### CLI and Preassignment

- string-valued `-v` assignments are now implemented and part of the claimed
  CLI surface.
- upstream corroboration for CLI-sensitive `ARGV` / `ARGC` behavior now
  includes the runnable direct-file case `one-true-awk:p.48a` plus the focused
  runnable gawk `argarray` corroboration for stable operand-shape behavior.

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
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L250),
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L259)
- one reviewed skip says the reusable backend record-selection path still
  narrows some non-regex expression patterns.
  Evidence:
  [tests/upstream/selection.toml](tests/upstream/selection.toml#L259)

#### Backend-Only Gaps

- `--ir` and `--asm` still do not cover every public execution path.
  Evidence:
  [SPEC.md](SPEC.md#L75),
  [docs/design.md](docs/design.md#L203)
- the checked-in `T-150` audit expands that list into explicit claimed-family
  anchors, including expression-pattern selection, default-print expression
  patterns, `do ... while`, loop `break` or `continue`, `next`, `nextfile`,
  `exit`, user-defined functions, and scalar-string coercion paths.
  Evidence:
  [tests/architecture/audit.toml](tests/architecture/audit.toml#L1),
  [tests/test_architecture_audit.py](tests/test_architecture_audit.py#L1)

#### Architecture Gaps

- the current design docs still describe a public model where some AWK programs
  run through Python-host fallback instead of the compiled backend/runtime.
  Evidence:
  [docs/design.md](docs/design.md#L203),
  [docs/design.md](docs/design.md#L223)
- if the intended product is AOT-only execution, every remaining host-runtime
  family is an architecture gap in addition to any POSIX gap.
- the remaining documented host-runtime families should be kept current as
  backend parity work lands; stale examples weaken the AOT-only contract.

### Inventory Tasks

- keep the verified list above current as gaps are fixed or reclassified
- add any missing POSIX-required areas not yet represented by upstream review
- keep the checked-in architecture cross-reference in
  [tests/architecture/audit.toml](tests/architecture/audit.toml)
  aligned with the code and docs

### T-150 Backend Gap Baseline

`T-150` is now complete.

The checked-in architecture audit baseline lives in:

- [tests/architecture/audit.toml](tests/architecture/audit.toml)
- [src/quawk/architecture_audit.py](src/quawk/architecture_audit.py)
- [tests/test_architecture_audit.py](tests/test_architecture_audit.py)

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

## Historical POSIX Task Backlog

The task IDs below are the original POSIX planning breakdown. They are kept for
historical traceability only; [docs/roadmap.md](docs/roadmap.md) is the
authoritative backlog.

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
  corroborating `sprintf` coverage, and the old `one-true-awk:p.29`
  record-target `gsub` crash has since been closed by `T-173`

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

### T-167 POSIX Done-Line Result

- `SPEC.md` now narrows the remaining public POSIX gaps instead of leaving them
  implicit: bare `length` remains partial, and repeated `$0` reassignment plus
  field rebuild is no longer overclaimed as fully complete
- `POSIX.md`, `SPEC.md`, and the reviewed upstream manifest now point at the
  same remaining in-scope gap classes: bare `length`, non-UTF-8 fixture input,
  numeric comparison mismatches, a few reusable-backend crashes, and a small
  set of corroborating-adapter gaps such as `argarray`
- with the remaining POSIX surface explicitly tracked, the roadmap can move
  directly into the explicit post-`P14` gap-closure wave instead of carrying
  another open `P14` audit task

### T-168 Input Separator Result

- in-program `FS` assignment now updates field splitting for subsequent records
  in both the host runtime and the compiled backend/runtime path
- in-program `RS` assignment now updates current record reads for subsequent
  input in both execution paths, keeping the current record model aligned with
  the claimed surface
- the remaining work after `T-168` is corroboration and narrower semantic
  cleanup, not a missing input-separator runtime feature

### T-169 FS-Sensitive Corroboration Result

- the reviewed direct-file anchors `p.5`, `p.5a`, `p.36`, `p.48`, `p.50`,
  `p.51`, and `p.52` are now runnable in the upstream subset because `T-168`
  removed their old separator blocker
- `p.35` stays reviewed, but its reason is now narrower: a `$0` field rebuild
  formatting mismatch after field mutation, not missing `FS` support
- the post-`P14` remaining work now starts with bare `length` in `T-170`

### T-170 Bare Length Result

- bare `length` now parses and executes as POSIX `length($0)` instead of
  reading an uninitialized variable named `length`
- the direct corroborating anchor `p.30` is now runnable in the upstream subset
- the remaining post-`P14` work now starts at the numeric comparison and
  expression-pattern bucket in `T-171`

### T-171 Comparison and Expression-Pattern Result

- AWK-style numeric-versus-string comparison selection now matches the pinned
  references for the remaining reviewed expression-pattern cases, including
  mixed numeric-field and nonnumeric-field comparisons under `next`
- regex literals now work as boolean condition terms inside nontrivial
  expression patterns such as `/Asia/ || /Africa/`
- the corroborating anchors `p.7`, `p.8`, `p.21a`, and `t.next` are now
  runnable in the upstream subset, so the remaining post-`P14` work starts at
  `T-172`

### T-172 Numeric-Expression Lowering Result

- the reusable backend now lowers ordinary numeric arithmetic inside
  string-producing record programs, including cases like `NR " " 10 / NR`
- the reviewed corroborating anchor `getnr2tb` is now runnable in the upstream
  subset instead of failing with a runtime-backed numeric-expression lowering
  error
- the remaining post-`P14` work now starts at the reviewed reusable-backend
  crash bucket in `T-173`

### T-173 Reusable-Backend Crash Result

- record-target `gsub`, field mutation with rebuild, and repeated `$0`
  reassignment now run clean through the reusable backend/runtime path instead
  of corrupting the active getline buffer and aborting later under `lli`
- the corroborating anchors `p.29`, `p.32`, and `t.set0a` are now runnable in
  the upstream subset
- the remaining post-`P14` work now starts at the explicit non-UTF-8 policy
  decision in `T-174`

### T-174 Byte-Oriented Input Policy Result

- the current public contract now treats input records and file-backed
  `getline` as byte-tolerant text rather than UTF-8-only text
- the Python-side runtime helpers now preserve undecodable bytes with
  `surrogateescape`, which keeps fallback/helper paths aligned with the
  compiled backend/runtime behavior on ordinary non-UTF-8 input
- the old `t.NF` skip reason was stale: input decoding is no longer the
  blocker, and the case is now narrowed to the real remaining `NF`-driven
  record-rebuild formatting mismatch
- the remaining post-`P14` work now starts at the corroboration-sensitive
  `splitvar` and `argarray` cases in `T-175` and `T-176`

### T-175 Split Target-Variable Result

- `split()` now treats an explicit third argument as a regexp separator in both
  the host runtime and the compiled backend/runtime path, including when that
  separator comes from a scalar variable
- the corroborating gawk anchor `splitvar` is now runnable in the upstream
  subset because the old `=+` separator mismatch is closed
- the remaining post-`P14` corroboration-sensitive work is now down to the
  CLI-shaped `argarray` case in `T-176`

### T-176 CLI-Sensitive Corroboration Result

- the gawk `argarray` selection now runs as a focused equivalent corroborating
  case instead of a stale direct-fixture skip
- the checked-in upstream subset now includes stable `ARGC` / `ARGV[1..]` and
  multi-file `FILENAME` corroboration without depending on engine-specific
  `ARGV[0]` or `BEGIN`-phase `FILENAME` details
- there are no remaining post-`P14` product gaps after the corroboration wave;
  the only remaining work is the final public-claim expansion and audit in
  `T-177`

### T-177 Final Claim Expansion And Audit Result

- `SPEC.md` now widens only the family that was still underclaimed: full POSIX
  `printf` parity is part of the current public contract
- the remaining reviewed skips stay explicit and non-product: unsuitable
  corroboration anchors (`p.43`, `p.48b`, `range1`), and
  reviewed-but-unnecessary anchors
  (`T.argv`, `T.builtin`, `T.expr`, `T.func`, `T.split`, `cmdlinefsbacknl`)
- stale references to open `P14` hardening work are gone from the public
  contract and architecture docs; the remaining partial rows now describe
  intentionally unclaimed surface rather than unfinished post-gap POSIX work
- the docs, manifest, and regression tests now agree on the resulting surface,
  so the post-`P14` remaining-gap wave is complete

## Post-P14 Remaining Gap Plan

The `T-167` audit left a smaller, explicit set of post-`P14` POSIX work. After
`T-177`, that remaining-gap wave is complete.

These are not product gaps and should stay reviewed as such unless better
anchors appear:

- reference-disagreement or unsuitable-corroboration cases
  Cases:
  `p.43`, `p.48b`, `range1`
- reviewed but unnecessary anchors for the current runnable subset
  Cases:
  `T.argv`, `T.builtin`, `T.expr`, `T.func`, `T.split`, `cmdlinefsbacknl`

Recommended execution order for the post-`P14` gap-closure wave:

1. widen `SPEC.md` only where the fixed and corroborated families justify it
2. keep unsuitable anchors as explicit reviewed skips instead of reopening them
   as implied product debt

Roadmap mapping:

- `T-168`: current record-surface `FS` / `RS` assignment
- `T-169`: re-audit and promote the unlocked `FS`-sensitive direct-file cases
- `T-171`: numeric comparison and expression-pattern fixes
- `T-172` through `T-173`: backend/lowering gap and crash cleanup
- `T-174`: byte-oriented input policy and stale-skip cleanup
- `T-175` through `T-176`: corroboration cleanup now completed
- `T-177`: final claim expansion and post-gap audit

#### POSIX-051: Promote upstream cases that directly corroborate fixed gaps

Remaining priority promotion targets after `T-166`:

- any remaining clean `next`-sensitive and `$0`-rebuild anchors once the
  reviewed backend-crash gaps are fixed

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

1. `POSIX-060` through `POSIX-062` only if a new POSIX claim exposes a backend-only gap
2. otherwise, move to post-`P14` work

Why this order:

- the highest-value remaining work was to make `SPEC.md`, this plan, and the
  reviewed manifest agree on the narrowed remaining POSIX surface
- that contract audit is now complete, so any new POSIX work should start from
  explicit public claim changes instead of implicit backlog debt
- backend-only follow-up should happen only when the public POSIX contract
  actually requires it

## Immediate Next Steps

The next concrete follow-up after this document should be:

1. treat the `P15` post-gap closeout as complete
2. start any future POSIX widening work from a fresh explicit roadmap task, not
   from implied debt in this document

## P18 Remaining Surface Baseline

The next remaining product work is narrower than the historical `P14` / `P15`
waves.

### T-190 Direct Rebuild Fix Result

The remaining direct product mismatch is now fixed:

- `$0` / `NF` rebuild behavior no longer remains a known claimed-surface gap.
- direct execution tests now pin:
  - `OFS`-preserving field rewrites such as `p.35`
  - `NF` truncation plus later field growth such as `t.NF`
- [SPEC.md](SPEC.md) now treats repeated `$0` / field rebuild as implemented
  again

Remaining `P18` work after `T-190`:

- re-audit the reviewed `p.35` / `t.NF` corroborating anchors and promote them
  to `run` if the pinned references agree cleanly
- keep the broader POSIX expression surface decision-gated until that narrower
  corroboration pass is complete

Current corroborating anchors for that rebuilt-record surface:

- `one-true-awk:p.35`
- `one-true-awk:t.NF`

At the end of `T-190`, those anchors were no longer known product mismatches;
they only remained pending the focused corroboration pass that `T-191` closes.

### T-191 Rebuild-Anchor Corroboration Result

The focused corroboration re-audit is now complete:

- `one-true-awk:p.35` is now runnable in the selected reference subset
- `one-true-awk:t.NF` is now runnable in the selected reference subset
- the remaining immediate `P18` work is now only the explicit decision about
  whether to widen the broader intentionally unclaimed expression surface

### T-192 Expression-Surface Decision Result

The broader intentionally unclaimed POSIX expression surface was not approved
for widening in the original `P18` roadmap wave.

Decision:

- keep the current claimed expression subset as-is
- do not start `T-193` through `T-196` in the current roadmap wave
- treat any future widening as a fresh explicit product decision, not implied
  debt from the current POSIX claim

Rationale:

- the current claimed AOT-backed contract is now coherent and corroborated for
  the selected POSIX surface
- widening operators such as `||`, broader comparisons, arithmetic families,
  ternary, match operators, and `in` would create a new feature wave rather
  than close a remaining known product gap
- the roadmap should not imply that broader expression support is already owed
  by the current public contract
- supporting analysis lives in:
  - [docs/plans/expression-surface-decision-table.md](docs/plans/expression-surface-decision-table.md)
  - [docs/plans/expression-surface-widening-analysis.md](docs/plans/expression-surface-widening-analysis.md)

Decision-gated broader surface, not current product debt:

- the broader POSIX expression surface remains intentionally unclaimed in
  `SPEC.md`
- this includes operators and forms such as:
  - `||`
  - `<=`, `>`, `>=`, `!=`
  - `-`, `*`, `/`, `%`, `^`
  - ternary
  - match operators
  - `in`
- any work on that broader expression family should start only after an
  explicit future roadmap decision to widen the claimed surface

Completed widening plan:

1. `P21`: logical-or and broader comparisons
2. `P22`: broader arithmetic
3. `P23`: ternary
4. `P24`: match operators and `in`

For every future widening phase, any newly claimed form must be fully
implemented on the compiled backend/runtime path with no public Python host
dependency for ordinary execution.

Residual host-runtime boundary follow-up:

- the broader expression surface originally remained intentionally unclaimed,
  and the repo needed a clearer inventory of where ordinary public execution
  could reach the Python host runtime
- that follow-up audit is planned separately in:
- [docs/plans/host-runtime-boundary-audit.md](docs/plans/host-runtime-boundary-audit.md)
- [docs/plans/residual-host-runtime-matrix.md](docs/plans/residual-host-runtime-matrix.md)

### T-202 Execution-Model Rebaseline Result

The `P19` host-boundary audit is now fully reflected in the public
execution-model docs.

What changed in the documented contract:

- representative unclaimed host-runtime-only programs now fail clearly in
  ordinary public execution instead of silently falling back
- the broader intentionally unclaimed POSIX expression surface remains outside
  the current AOT-backed contract
- every claimed execution family now has a compiled backend/runtime public path
- the former claimed value-fallback debt from `P20` is now closed for the
  current claimed surface

Supporting follow-on planning lives in:

- [docs/plans/host-runtime-boundary-audit.md](docs/plans/host-runtime-boundary-audit.md)
- [docs/plans/residual-host-runtime-matrix.md](docs/plans/residual-host-runtime-matrix.md)
- [docs/plans/claimed-value-fallback-cleanup.md](docs/plans/claimed-value-fallback-cleanup.md)
- [docs/plans/claimed-value-fallback-matrix.md](docs/plans/claimed-value-fallback-matrix.md)
- [docs/plans/expression-surface-widening-analysis.md](docs/plans/expression-surface-widening-analysis.md)
- [docs/plans/expression-surface-decision-table.md](docs/plans/expression-surface-decision-table.md)

### T-207 Execution-Model Final Rebaseline Result

The execution-model docs now reflect the final post-`P20` state.

What changed in the documented contract:

- `SPEC.md` now treats backend parity for every claimed execution path as
  implemented rather than partial
- `docs/design.md` no longer describes any remaining claimed public host
  fallback debt
- the roadmap now records `T-207` and `P20` as complete instead of presenting
  claimed value-fallback cleanup as the next deliverable
- the remaining host-runtime discussion is limited to the broader intentionally
  unclaimed expression surface, where public execution still fails clearly
  rather than silently falling back

### Ranked Widening Phases

The ranked widening of the intentionally unclaimed expression surface is now
complete:

1. `P21`: logical-or and broader comparisons
2. `P22`: broader arithmetic
3. `P23`: ternary
4. `P24`: match operators and `in`

For every future phase, the rule is strict: any newly claimed form must be
fully implemented in the compiled backend/runtime path, with no public Python
host dependency for ordinary execution.

### T-208 P21 Baseline Result

The `P21` baseline now fixes the exact next widening target:

- `||`
- `<=`, `>`, `>=`, `!=`

What is checked in for that baseline:

- `SPEC.md` now has explicit planned rows for the `P21` target surface and its
  backend or inspection gate
- direct tests now pin those exact forms as the next widening target rather
  than treating them as an undifferentiated part of the broader unclaimed
  surface
- the current starting point is pinned with parenthesized expression programs
  so the direct tests exercise comparison semantics rather than `print`
  redirection, and those representative `||`, `<=`, `>`, `>=`, and `!=` forms
  still fail cleanly outside the claimed surface
- the roadmap now treats `T-208` as complete and leaves `T-209` / `T-210` as
  the first implementation work inside `P21`

The contract rule remains strict: these forms do not become claimed until
ordinary public execution, `--ir`, and `--asm` all stay on the compiled
backend/runtime path with no public Python host dependency.

### T-209 And T-210 P21 Backend Result

The backend/runtime implementation for the exact `P21` target forms is now
complete:

- representative `||` programs now stay on the compiled backend/runtime path
  in ordinary public execution
- representative `<=`, `>`, `>=`, and `!=` programs now stay on the compiled
  backend/runtime path in ordinary public execution
- the direct `P21` target tests now pin the intended comparison semantics for
  representative string-vs-numeric cases

At the end of `T-210`, the remaining `P21` work is no longer implementation
support. It is inspection, routing, corroboration, and then the claim
rebaseline in `T-212`.

### T-211 P21 Inspection And Corroboration Result

The `P21` closeout evidence is now explicit:

- representative `||`, `<=`, `>`, `>=`, and `!=` programs now succeed under
  `--ir` and `--asm`
- focused routing regressions now pin those forms to the compiled
  backend/runtime path instead of the residual host-boundary path
- the existing runnable reference subset already corroborates this wave through
  cases such as `one-true-awk:p.7`, `one-true-awk:p.8`,
  `one-true-awk:p.21a`, and `one-true-awk:t.next`

That leaves `T-212` as the public-contract step: widen the actual claimed
surface only after the backend/runtime, inspection, and evidence closeout is
already checked in.

### T-212 P21 Public-Contract Rebaseline Result

The public contract now reflects the completed `P21` wave:

- `SPEC.md` now includes `||`, `<=`, `>`, `>=`, and `!=` in the claimed
  backend/runtime expression surface
- the `P21` target rows are no longer planned; they are now recorded as
  implemented execution and inspection parity
- `docs/design.md` now lists logical-or and the broader comparison family
  inside the currently claimed expression subset rather than inside the
  remaining unclaimed surface
- the roadmap now treats `P21` as complete and moves the next deliverable to
  the broader arithmetic wave in `P22`

The backend-only rule remains unchanged for every future widening phase: a form
does not become claimed until ordinary public execution, `--ir`, and `--asm`
all stay on the compiled backend/runtime path with no public Python host
dependency.

### T-222 P24 Baseline Result

The `P24` baseline now fixes the final ranked widening target:

- `~`, `!~`
- `expr in array`

What is checked in for that baseline:

- `SPEC.md` now has explicit target rows for the `P24` surface and its backend
  or inspection gate
- direct tests pin those exact forms as the final backend-only widening wave
- the direct baseline covers representative public execution, routing, and
  inspection expectations for `~`, `!~`, and `in`

### T-223 And T-224 P24 Backend Result

The backend/runtime implementation for the exact `P24` target forms is now
complete:

- representative `~` and `!~` programs now execute through ordinary public
  backend/runtime execution with no host fallback
- representative scalar-key `expr in array` programs now execute through
  ordinary public backend/runtime execution with no host fallback
- direct runtime checks now pin representative match and membership semantics
  for the widened family

### T-225 P24 Inspection And Corroboration Result

The `P24` closeout evidence is now explicit:

- representative `~`, `!~`, and `in` programs now succeed under `--ir` and
  `--asm`
- focused routing regressions now pin those forms to the compiled
  backend/runtime path instead of the residual host-boundary path
- no clean checked-in reference anchor is pinned for `P24` yet, so this wave
  is currently closed by direct backend, routing, inspection, and runtime
  coverage instead

That leaves `T-226` as the public-contract step: widen the actual claimed
surface only after the backend/runtime, inspection, and direct evidence
closeout is already checked in.

### T-226 P24 Public-Contract Rebaseline Result

The public contract now reflects the completed `P24` wave:

- `SPEC.md` now includes `~`, `!~`, and scalar-key `expr in array`
  membership in the claimed backend/runtime expression surface
- the `P24` target rows are now recorded as implemented execution and
  inspection parity
- `docs/design.md` now lists match operators and membership inside the
  currently claimed expression subset rather than inside the remaining
  unclaimed surface
- the roadmap now treats `P24` as complete and leaves no active widening phase
  scheduled

### T-213 P22 Baseline Result

The `P22` baseline now fixes the exact next widening target:

- `-`
- `*`
- `/`
- `%`
- `^`

What is checked in for that baseline:

- direct tests now pin those exact arithmetic forms as the next widening
  target
- the widening analysis and decision table now treat broader arithmetic as the
  dedicated next backend-only wave
- the contract rule remains strict: these forms do not become claimed until
  ordinary public execution, `--ir`, and `--asm` all stay on the compiled
  backend/runtime path with no public Python host dependency

### T-214 And T-215 P22 Backend Result

The backend/runtime implementation for the exact `P22` target forms is now
complete:

- representative subtraction, multiplication, and division programs now stay
  on the compiled backend/runtime path in ordinary public execution
- representative modulo and exponentiation programs now stay on the compiled
  backend/runtime path in ordinary public execution
- the direct `P22` target tests now pin representative arithmetic precedence
  and result semantics

At the end of `T-215`, the remaining `P22` work is no longer implementation
support. It is inspection, routing, corroboration, and then the claim
rebaseline in `T-217`.

### T-216 P22 Inspection And Corroboration Result

The `P22` closeout evidence is now explicit:

- representative `-`, `*`, `/`, `%`, and `^` programs now succeed under `--ir`
  and `--asm`
- focused routing regressions now pin those forms to the compiled
  backend/runtime path instead of the residual host-boundary path
- the existing runnable reference subset already corroborates this wave through
  cases such as `one-true-awk:p.25`, `one-true-awk:p.34`,
  `one-true-awk:p.36`, and `one-true-awk:p.44`

That leaves `T-217` as the public-contract step: widen the actual claimed
surface only after the backend/runtime, inspection, and evidence closeout is
already checked in.

### T-217 P22 Public-Contract Rebaseline Result

The public contract now reflects the completed `P22` wave:

- `SPEC.md` now includes `-`, `*`, `/`, `%`, and `^` in the claimed
  backend/runtime expression surface
- the `P22` target rows are now recorded as implemented execution and
  inspection parity
- `docs/design.md` now lists broader arithmetic inside the currently claimed
  expression subset rather than inside the remaining unclaimed surface
- the roadmap now treats `P22` as complete and moves the next deliverable to
  ternary in `P23`

The backend-only rule remains unchanged for every future widening phase: a form
does not become claimed until ordinary public execution, `--ir`, and `--asm`
all stay on the compiled backend/runtime path with no public Python host
dependency.

### T-218 P23 Baseline Result

The `P23` baseline now fixes the exact next widening target:

- pure ternary expressions over the current claimed numeric/string subset

What is checked in for that baseline:

- direct tests now pin those exact ternary forms as the next widening target
- the widening analysis and decision table now treat ternary as the dedicated
  next backend-only wave
- the contract rule remains strict: these forms do not become claimed until
  ordinary public execution, `--ir`, and `--asm` all stay on the compiled
  backend/runtime path with no public Python host dependency

### T-219 P23 Backend Result

The backend/runtime implementation for the exact `P23` target forms is now
complete:

- representative numeric ternary programs now stay on the compiled
  backend/runtime path in ordinary public execution
- representative string ternary programs now stay on the compiled
  backend/runtime path in ordinary public execution
- the direct `P23` target tests now pin representative nested ternary and
  branch-coercion behavior for the widened pure-expression family

At the end of `T-219`, the remaining `P23` work is no longer implementation
support. It is inspection, routing, direct corroboration, and then the claim
rebaseline in `T-221`.

### T-220 P23 Inspection And Corroboration Result

The `P23` closeout evidence is now explicit:

- representative ternary programs now succeed under `--ir` and `--asm`
- focused routing regressions now pin those forms to the compiled
  backend/runtime path instead of the residual host-boundary path
- no clean checked-in reference anchor is pinned for `P23` yet, so the ternary
  wave is currently closed by direct backend, routing, inspection, and runtime
  coverage instead

That leaves `T-221` as the public-contract step: widen the actual claimed
surface only after the backend/runtime, inspection, and direct evidence
closeout is already checked in.

### T-221 P23 Public-Contract Rebaseline Result

The public contract now reflects the completed `P23` wave:

- `SPEC.md` now includes pure ternary expressions over the current claimed
  numeric/string subset in the claimed backend/runtime expression surface
- the `P23` target rows are now recorded as implemented execution and
  inspection parity
- `docs/design.md` now lists ternary inside the currently claimed expression
  subset rather than inside the remaining unclaimed surface
- the roadmap now treats `P23` as complete and moves the next deliverable to
  match operators and membership in `P24`

The backend-only rule remains unchanged for every future widening phase: a form
does not become claimed until ordinary public execution, `--ir`, and `--asm`
all stay on the compiled backend/runtime path with no public Python host
dependency.

### T-279 P32 Corroboration Baseline Result

The remaining POSIX corroboration-only gaps are now explicit:

- `rand()` remains direct-test-only because the pinned references still
  disagree on deterministic seeded output

The checked-in P32 baseline now makes `rand()` disagreement the explicit
remaining corroboration-only gap for the implemented POSIX surface.

### T-280 Field Rebuild Corroboration Result

The field-rebuild corroboration re-audit is now complete:

- the reviewed `p.35` / `t.NF` anchors are promoted in the selected upstream
  subset
- field rebuild stays implemented end to end, with no remaining corroboration
  gap

The remaining P32 corroboration work now continues only with the reviewed
`rand()` reference-disagreement policy.

### T-281 Record-Target gsub Corroboration Result

The record-target `gsub` corroboration review is now complete:

- the selected upstream `p.29` anchor is runnable and corroborates the
  current record-target `gsub` behavior
- record-target `gsub` stays implemented end to end, with no remaining
  corroboration gap

The remaining P32 corroboration work now continues only with the `rand()`
reference-disagreement policy.

### T-282 Rand Corroboration Policy Result

The `rand()` corroboration strategy is now explicit:

- the pinned references still disagree on deterministic seeded output even
  after `srand`
- `rand()` stays direct-test-only under the checked-in reference-disagreement
  policy

The remaining POSIX corroboration closeout work is now reduced to the final
audit only.

### T-283 Final POSIX Compatibility Audit Result

The final POSIX end-to-end compatibility audit is now complete:

- `SPEC.md`, `docs/compatibility.md`, `tests/upstream/selection.toml`, and the
  roadmap all agree on the final implemented POSIX surface
- no stale reviewed gaps remain for the implemented POSIX families

`P32` is now closed out.

## Notes

This plan should stay stricter than the current compatibility plan:

- [docs/compatibility.md](docs/compatibility.md) is about
  the reviewed upstream suite and its growth policy
- `POSIX.md` is about the full standard-alignment gap inventory and the work
  needed to make the public contract honestly POSIX-compatible
