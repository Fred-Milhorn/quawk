# Roadmap

This document is the phased implementation roadmap and active backlog for `quawk`.

## Planning Assumptions

- language target is POSIX-oriented AWK first
- implementation language is Python `3.14.x`
- developer workflow baseline is `uv` managing Python `3.14.x` and the project `.venv`
- current LLVM-backed execution uses local LLVM tools (`lli`)
- remaining execution-model work closes the last claimed backend gaps and removes the last Python-side semantic fallback as part of the same implementation wave, so the reusable AOT-oriented program/runtime split is the only public execution path
- the grammar contract and compiled execution contract must stay coupled: a form should not remain admitted by `docs/quawk.ebnf` without end-to-end lowering through the LLVM backend/runtime path
- reference behavior is checked against `one-true-awk` and `gawk --posix`
- implementation grows from an initial end-to-end JIT path
- phase delivery uses TDD for the next capability increment
- `pytest` is the default test framework

## Phase Overview

| Phase | Name | Primary Outcome |
|---|---|---|
| P0 | Python Bootstrap and Tooling | Package skeleton, env bootstrap, and local tooling basics |
| P1 | End-to-End MVP Path | First runnable `quawk` JIT path for the simplest AWK program |
| P2 | Core Subset Expansion | `BEGIN`, scalar expressions, simple record actions, and control flow |
| P3 | Mixed Program Execution | `BEGIN` + record actions + `END` in one executable program |
| P4 | Regex and Expression Surface | Regex-driven pattern selection and core operator surface |
| P5 | Functions and Scope | User-defined functions, symbol/scoping rules, and legality checks |
| P6 | Initial Nominal Functional Completion | Major POSIX AWK construct families all have at least one executable implementation |
| P7 | POSIX Core Syntax and AST Completion | Frontend covers the remaining POSIX-core concrete syntax and AST surface |
| P8 | POSIX Core Runtime and Builtins Completion | Public execution covers POSIX-core semantics, builtins, and builtin variables |
| P9 | Backend Parity and Inspection Completion | LLVM/reusable backend and inspection modes cover the same POSIX-core surface |
| P10 | Grammar Contract and Doc Alignment | Full `quawk.ebnf` implementation and honest design/AST docs |
| P11 | Compatibility and Hardening | Differential compatibility gates and regression control |
| P12 | Pre-Release Readiness | Documentation completion, release checklist, and polish |
| P13 | AOT Contract Completion | Every currently claimed behavior executes through the compiled backend/runtime path |
| P14 | POSIX Compatibility Completion | Remaining in-scope POSIX feature and behavior gaps are closed and corroborated |
| P15 | Remaining POSIX Gap Closure | Explicitly tracked post-`P14` POSIX gaps are closed or intentionally left as permanent reviewed skips |
| P16 | Testing Surface Cleanup | Test entrypoints, markers, CI commands, and corpus surfaces are renamed and consolidated into a clearer workflow |
| P17 | Compatibility Tooling Namespace Cleanup | Corpus and upstream-compatibility tooling move under `quawk.compat`, and the singleton script wrapper is removed |
| P18 | Remaining POSIX Surface Closure And Widening Decisions | The last known claimed POSIX gap is closed, and any broader POSIX expression-surface expansion happens only through an explicit decision-gated wave |
| P19 | Residual Host-Runtime Boundary Audit | Residual public host-runtime routing is inventoried, classified, and turned into an explicit backend-first follow-up plan |
| P20 | Claimed Value-Fallback Cleanup | The remaining claimed programs that still depend on host-side value semantics are inventoried, backended, and removed from public fallback |
| P21 | Logical-Or and Comparison Widening | `||` and the broader comparison family become claimed only when they execute through the compiled backend/runtime path with inspection parity and no public host fallback |
| P22 | Arithmetic Widening | The broader arithmetic family becomes claimed only when it executes through the compiled backend/runtime path with inspection parity and no public host fallback |
| P23 | Ternary Widening | Ternary expressions become claimed only when they execute through the compiled backend/runtime path with inspection parity and no public host fallback |
| P24 | Match and Membership Widening | Match operators and `in` become claimed only when they execute through the compiled backend/runtime path with inspection parity and no public host fallback |
| P25 | Static Variable Slots | Compile-time allocation of typed variable slots in state struct instead of string-named hash table entries |
| P26 | Type Inference | Static inference of numeric vs string types for variables to enable specialized code generation |
| P27 | Specialized Operations | Type-aware code generation for numeric/string fast paths in comparisons, arithmetic, and variable access |
| P28 | LLVM Optimization Integration | Optional optimization passes for generated IR to enable constant folding and register allocation |
| P29 | Runtime ABI Refinement | Direct-call convention improvements for hot paths to reduce function call overhead |
| P30 | Execution Completeness Closure | The remaining grammar-valid backend gaps are closed so admitted forms execute end-to-end through the compiled backend/runtime path |
| P31 | Remaining POSIX Contract Closure | The remaining product-side execution and contract gaps are classified explicitly and closed where they are POSIX-required |
| P32 | Final POSIX Compatibility Corroboration | The remaining reviewed upstream anchors and reference-policy gaps are closed for the implemented POSIX surface |
| P33 | Direct-Path Removal And Route Cleanup | The restricted direct lowering lane is removed, reusable lowering becomes the only compiled execution route, and stale backend gates are eliminated |
| P34 | Local Scalar SSA Promotion | Action-local numeric scalars move out of `%quawk.state` when safe so LLVM can optimize hot loops against local values instead of state traffic |
| P35 | Agent Workflow Documentation Alignment | `AGENTS.md` and linked workflow docs are aligned with current setup, validation, compatibility, architecture, and doc-update guidance |
| P36 | Implementation Readability Refactor | Large implementation modules are split by responsibility so contributors can understand and modify the compiler/runtime pipeline more easily |

## Phase Entry and Exit Rules

Entry gate for every phase:

1. author tests for the next capability increment in phase scope
2. check in those tests before or alongside implementation
3. use `xfail` only where it makes the temporary expected failure clearer
4. start implementation only after the target behavior is concretely specified in tests

Phase completion rule:
- a phase should not close while its claimed behavior still lacks real test coverage
- the roadmap, not a custom validator, is the source of truth for phase status

## Phase Details

### P0: Python Bootstrap and Tooling

Objective:
- establish Python project scaffolding and enforce reproducible local workflow

In scope:
- create `src/`, `tests/`, and `scripts/`
- add initial package and CLI entrypoint placeholder
- add `pyproject.toml` and dependency policy
- add baseline local format/lint/type/test checks

Exit criteria:
- bootstrap flow works from a clean checkout
- documented local checks run successfully in the project environment

### P1: End-to-End MVP Path

Objective:
- execute the simplest useful AWK program through the full CLI-to-JIT pipeline

In scope:
- inline program text and `-f` file input
- minimal lexer and parser support for `BEGIN { print "literal" }`
- LLVM lowering and runtime path sufficient for the MVP
- stable stdout, exit status, and basic CLI invocation
- CLI-driven end-to-end tests as the primary acceptance signal

Exit criteria:
- `quawk 'BEGIN { print "hello" }'` executes correctly
- the same program executes from `-f`
- unsupported syntax fails cleanly without pretending broader support exists

### P2: Core Subset Expansion

Objective:
- establish the first coherent executable AWK subset beyond the initial `P1` path

In scope:
- each increment must name the exact AWK behavior it delivers, plus example programs that should execute at phase completion
- each increment should have lex, parse, lowering/runtime, and integration-test work scoped to that behavior
- semantic checks land only when the increment requires them
- diagnostics improvements follow the related execution support rather than leading it

Exit criteria:
- the core executable subset includes scalar `BEGIN` programs, simple record actions, and `BEGIN` control flow
- the earlier working `P1` path stays green as coverage expands
- the supported subset is always explicit in tests and docs

Planned capability increments inside `P2`:

1. Numeric print in `BEGIN`
   Target programs:
   - `BEGIN { print 1 }`
   - `BEGIN { print 1 + 2 }`
2. Scalar variables and assignment in `BEGIN`
   Target programs:
   - `BEGIN { x = 1; print x }`
   - `BEGIN { x = 1 + 2; print x }`
3. Record loop with bare actions and simple fields
   Target programs:
   - `{ print $0 }`
   - `{ print $1 }`
4. Comparisons and control flow over the supported subset
   Target programs:
   - `BEGIN { if (1 < 2) print 3 }`
   - `BEGIN { while (x < 3) x = x + 1 }`

### P3: Mixed Program Execution

Objective:
- execute real AWK programs that combine `BEGIN`, record actions, and `END`

In scope:
- multiple top-level pattern-action items in one program
- `END` support
- mixed execution order across `BEGIN`, input records, and `END`
- general field reads beyond `$0` and `$1`
- enough runtime state to make the record loop feel like AWK rather than a narrow demo path

Exit criteria:
- `BEGIN { print "start" } { print $2 } END { print "done" }` executes correctly
- the same program executes from `-f` and with stdin/file inputs
- the implementation no longer relies on a bare-action-only record path

### P4: Regex and Expression Surface

Objective:
- support pattern selection and core expressions broadly enough for ordinary AWK filtering logic, on top of a runtime architecture that scales to real AWK-sized inputs

In scope:
- replace concrete-input lowering with reusable program IR for record-driven execution
- introduce a small runtime support layer for streaming input, field access, regex matching, and output helpers
- make `--ir` / `--asm` report reusable program artifacts for record-driven programs
- regex literals and `/` vs regex disambiguation
- core relational/equality/logical operator surface
- pattern expressions driven by regexes and comparisons
- expression conformance fixtures for the supported subset

Exit criteria:
- `/foo/ { print $0 }` executes correctly
- mixed and regex-driven programs no longer require whole-input materialization before lowering
- `--ir` for record-driven programs succeeds without specializing to the current input stream
- representative boolean/comparison/arithmetic programs execute correctly
- parser/lexer behavior for regex syntax is deterministic and tested

### P5: Functions and Scope

Objective:
- support reusable user-defined computation with stable symbol and scope rules

In scope:
- function definitions, calls, and returns
- symbol tables and scope handling
- legality checks for assignments, control flow, and function declarations
- diagnostics for invalid user-defined constructs

Exit criteria:
- `function f(x) { return x + 1 } BEGIN { print f(2) }` executes correctly
- scope and legality diagnostics are deterministic for the supported subset

### P6: Initial Nominal Functional Completion

Objective:
- cross the line from a strong executable subset to an implementation that has working examples for the major POSIX AWK construct families

In scope:
- arrays and associative indexing
- `for`, `for ... in`, and `delete`
- builtins required for common POSIX AWK workflows
- normalization/backend work needed to support the major language families

Implemented in this phase:
- associative arrays on the executable path, including indexed assignment, indexed reads, and default element behavior
- array mutation and traversal through `delete`, classic `for`, and `for ... in`
- the first builtin subset needed for the active P6 deliverable
- normalization/backend support needed to execute the active major language families coherently

Exit criteria:
- every major POSIX AWK construct family has at least one working executable implementation
- remaining gaps may still include whole POSIX-core families, backend-only limitations, and narrowed semantics
- compatibility work does not start from this milestone; it starts only after `P7`, `P8`, and `P9` close

### P7: POSIX Core Syntax and AST Completion

Objective:
- close the remaining frontend gap between the current executable subset and the POSIX-core concrete language surface

In scope:
- remaining POSIX-core tokens, keywords, operators, and separators
- parser coverage for remaining statement and expression families
- AST/lvalue shape needed for the POSIX-core target
- semantic validation for the completed syntax surface
- doc alignment between the chosen pre-compatibility target and the grammar/ASDL references

Exit criteria:
- parser and semantic layers cover the remaining POSIX-core statement and expression families
- no whole POSIX-core grammar family is still missing purely because the frontend cannot represent it
- grammar/ASDL/docs mismatch is reduced to explicitly deferred non-POSIX or post-compatibility behavior only

### P8: POSIX Core Runtime and Builtins Completion

Objective:
- make public `quawk` execution cover POSIX-core runtime semantics, builtins, and builtin variables

In scope:
- AWK-style scalar value/coercion model
- remaining POSIX-core statement/runtime semantics
- field, record, and pattern sequencing semantics
- POSIX-core builtins
- POSIX-core builtin variables and mutable runtime state

Exit criteria:
- public `quawk` execution covers the chosen POSIX-core surface end to end
- remaining known gaps are backend/instrumentation issues or explicitly deferred non-POSIX extensions
- builtin and builtin-variable behavior is specified by real CLI or corpus tests

### P9: Backend Parity and Inspection Completion

Objective:
- make the LLVM/reusable backend and inspection modes cover the completed pre-compatibility surface and shrink the remaining documented fallback families

In scope:
- lowering and runtime ABI expansion for the completed POSIX-core AST
- removal of the largest host-runtime-only gaps in the supported core-language families
- `--ir` and `--asm` parity for representative programs across the completed surface
- backend-vs-reference parity checks before compatibility work starts

Exit criteria:
- representative programs for the completed array, iteration, builtin, and record families execute through the backend path
- `--ir` and `--asm` work for representative programs across the completed supported surface
- any remaining host-runtime fallback is explicitly documented and narrowed to deferred families rather than the core array/iteration/builtin surface

### P10: Grammar Contract and Doc Alignment

Objective:
- make `quawk.ebnf` the implemented concrete-syntax contract and align the surrounding design and AST docs with the shipped implementation

In scope:
- finish parser support for the full `quawk.ebnf` surface
- remove remaining parser, semantic, runtime, and backend narrowing for grammar-admitted forms
- refresh `design.md` current-state sections so they describe the real implementation
- consolidate the AST contract into one implemented `quawk.asdl` schema

Success in this phase looks like:
- every `quawk.ebnf` production family is intentionally covered by parser conformance tests
- no parser-only narrowing remains for valid grammar constructs in the chosen language contract
- public execution covers the admitted grammar surface instead of failing on grammar-valid forms
- `design.md` accurately distinguishes parser, public execution, and backend or inspection support
- `quawk.asdl` is the single documented AST contract for the implemented parser output

Exit criteria:
- every `quawk.ebnf` production is parseable
- the remaining grammar-admitted forms execute through public `quawk` execution
- `design.md`, `quawk.ebnf`, and `quawk.asdl` are internally consistent
- compatibility work no longer needs to discover missing grammar implementation work

Follow-up correction:
- later execution-model work showed that parser admission still outran backend lowering in a few residual areas
- that parseable-but-not-lowerable split is now treated as execution-completeness debt, not as an acceptable resting state
- the remaining cleanup is tracked explicitly in `P30`

### P11: Compatibility and Hardening

Objective:
- maximize POSIX compatibility and reduce behavioral gaps after feature completion is already in place

In scope:
- pinned upstream source trees for One True Awk and gawk
- repo-managed local builds of the reference engines
- upstream-suite-derived compatibility execution and classification
- divergence classification workflow and reviewed compatibility notes
- supplemental repo-owned regression corpus maintenance
- regression triage and targeted fixes
- implementation details for `T-035` live in [compatibility.md](compatibility.md)

Success in this phase looks like:
- supported parser, semantic, and runtime behavior runs through stable pinned upstream compatibility infrastructure instead of only ad hoc local checks
- reviewed AST snapshot surfaces are pinned by deterministic golden coverage where they improve coverage and reviewability
- semantic diagnostics have stable public error codes in addition to source spans and human-readable messages
- the normal local workflow builds One True Awk and gawk from pinned upstream sources rather than relying on host `awk`
- upstream-suite-derived compatibility runs against `quawk`, One True Awk, and gawk produce normalized comparable results for the selected portable cases
- every observed compatibility gap in the active upstream compatibility surface is either fixed or explicitly classified in checked-in divergence metadata and reviewed notes

Exit criteria:
- selected AST golden fixtures are stable and reviewed
- semantic errors emit stable public codes without losing source-span precision
- required compatibility runs do not depend on host `awk`
- the repo builds and resolves pinned local One True Awk and gawk binaries for normal compatibility runs
- the upstream compatibility harness executes a checked-in selected subset from both upstream suites across `quawk`, One True Awk, and gawk
- no failing required compatibility tests remain in the active hardening test set
- known divergences are documented, tagged, and classified in checked-in metadata and companion docs
- hardening pass closes or explicitly triages all high-severity regressions discovered during the phase

### P12: Pre-Release Readiness

Objective:
- ship an initial public release candidate

In scope:
- CLI contract freeze and doc completion
- release packaging metadata and changelog process
- contributor/support workflow polish

Exit criteria:
- release checklist is complete
- smoke test matrix passes on declared environments
- documentation is internally consistent and accurate

### P13: AOT Contract Completion

Objective:
- make AOT compilation plus backend/runtime execution the real product contract for every behavior currently claimed as implemented

In scope:
- inventory and test baselines for every claimed feature family that still depends on Python-side semantic execution
- backend lowering and runtime-ABI expansion for the remaining claimed host-runtime families, with representative user-defined functions, `exit`, `nextfile`, and scalar-string/coercion paths already completed
- removal of Python-side semantic fallback from the public execution path only when the remaining claimed families already have compiled execution and `--ir` / `--asm` parity
- one combined implementation wave for the remaining claimed backend families plus full `--ir` / `--asm` parity
- architecture audits and doc updates that prove Python is compile/orchestration only for claimed AWK semantics
- implementation details for this phase live in [POSIX.md](../POSIX.md)

Exit criteria:
- every behavior marked `implemented` in `SPEC.md` executes through the compiled backend/runtime path
- public `quawk` execution no longer depends on Python-side semantic execution for claimed behavior
- `--ir` and `--asm` succeed for all claimed execution families, or `SPEC.md` is narrowed before the phase closes
- `SPEC.md` and `docs/design.md` describe one execution model rather than a split Python/backend execution story

### P14: POSIX Compatibility Completion

Objective:
- close the remaining in-scope POSIX feature and behavior gaps once the execution model is honest

In scope:
- split and align `SPEC.md` rows so POSIX-facing claims are granular enough to expose real gaps
- full POSIX `print` behavior, output variables, output redirection, and `printf` parity
- missing POSIX builtins, `getline`, and builtin variables
- remaining parser continuation/newline gaps and reviewed runtime sequencing mismatches
- CLI preassignment and environment-sensitive behavior needed for ordinary POSIX `awk` usage
- upstream corroboration expansion and a final POSIX gap audit
- implementation details for this phase live in [POSIX.md](../POSIX.md)

Exit criteria:
- `SPEC.md` matches the current POSIX claim set at feature-family granularity
- all known in-scope POSIX gaps tracked in `POSIX.md` are fixed or explicitly documented as out-of-scope
- local and upstream-backed tests corroborate every claimed POSIX family
- remaining divergences are limited to documented extensions or explicitly deferred non-POSIX behavior

### P15: Remaining POSIX Gap Closure

Objective:
- close the explicitly tracked post-`P14` POSIX gaps that were narrowed in
  `SPEC.md` rather than treated as silently complete

In scope:
- in-program `FS` / `RS` assignment and the downstream field-splitting cases it unlocks
- bare `length` parity with POSIX `length($0)`
- remaining numeric comparison and expression-pattern selection mismatches
- the reviewed reusable-backend crashes in `gsub`, field-mutation, `$0` rebuild, and numeric-expression paths
- explicit policy for non-UTF-8 input in reviewed corpus and upstream cases
- remaining corroboration gaps such as `splitvar` and CLI-sensitive `argarray`
- final public-claim expansion only after the fixed families are corroborated
- implementation details for this phase live in [POSIX.md](../POSIX.md)

Exit criteria:
- every remaining in-scope POSIX gap from the `T-167` audit is either fixed or
  explicitly moved to a permanent reviewed skip or out-of-scope claim
- `SPEC.md`, `POSIX.md`, and the upstream manifest agree on any widened POSIX
  claim set after the fixes land
- unsuitable corroborating anchors remain explicit reviewed skips rather than
  implicit backlog debt

### P16: Testing Surface Cleanup

Objective:
- make the repo test workflow easier to understand by replacing negative or
  misleading suite names, reducing overlap between local compatibility
  surfaces, and documenting the resulting commands consistently

In scope:
- replace `not compat` with a positive default test-surface marker
- rename the reference-engine compatibility suite so it reflects reference
  comparison rather than a false upstream relationship
- rename the repo-owned local compatibility suite so it reads as corpus-backed
  coverage rather than a vague local bucket
- merge the overlapping local differential corpus pytest files into one clearer
  compatibility surface
- standardize the release-smoke entrypoint and decide whether it is marker-based
  or file-based
- reclassify the `corpus` CLI as a manual harness tool rather than a primary
  test gate
- implementation details for this phase live in [history/testing-refactor.md](history/testing-refactor.md)

Exit criteria:
- the primary pytest surfaces are named positively and described consistently in
  `pyproject.toml`, docs, and CI
- `ci-fast` runs the renamed default core suite rather than a negative marker
  selection
- the reference-engine compatibility gate uses the renamed reference-oriented
  marker everywhere
- the repo-owned local differential compatibility surface is represented by one
  pytest entrypoint instead of two overlapping ones
- release-smoke invocation is documented one way only, and docs plus checklist
  agree on that command
- `corpus` remains available, but docs describe it as a harness/debugging tool
  instead of a parallel first-class test gate

### P17: Compatibility Tooling Namespace Cleanup

Objective:
- clean up the package layout so product/runtime/compiler code stays at the top
  level while corpus and upstream-compatibility tooling live under a dedicated
  `quawk.compat` namespace

In scope:
- create `src/quawk/compat/` as the dedicated home for corpus and upstream
  compatibility modules
- move the current flat compatibility modules into that namespace
- remove the singleton `scripts/upstream_compat.py` wrapper
- replace the wrapper with package-owned entrypoints while keeping the `corpus`
  command stable
- update internal imports, tests, docs, and CI references together so the repo
  no longer depends on the old flat module layout
- implementation details for this phase live in [history/repo-refactor.md](history/repo-refactor.md)

Exit criteria:
- compatibility and corpus tooling are grouped under `quawk.compat`
- the top-level `quawk` package remains focused on product/runtime/compiler code
- `scripts/upstream_compat.py` is gone
- a package-owned upstream bootstrap entrypoint exists and is used by docs and
  CI
- the `corpus` command remains stable while resolving through the new namespace
- focused compatibility-tooling tests and the broader `core` and
  `compat_reference` pytest surfaces pass against the new layout

### P18: Remaining POSIX Surface Closure And Widening Decisions

Objective:
- close the last known claimed POSIX product gap and separate that work from any
  optional widening of the still-unclaimed broader POSIX expression surface

In scope:
- fix the remaining `$0` / `NF` rebuild behavior mismatch tracked in `SPEC.md`
  and `POSIX.md`
- promote or precisely reclassify the corroborating `p.35` / `t.NF` anchors
  once the behavior is fixed
- make an explicit product decision about whether to widen the currently
  unclaimed POSIX expression surface beyond the existing AOT-backed subset
- if widening is approved, stage it as a separate test-first implementation
  wave with matching backend/inspection parity and doc updates
- implementation details for the current remaining gaps live in
  [POSIX.md](../POSIX.md)

Exit criteria:
- the claimed POSIX surface no longer has the remaining `$0` / `NF` rebuild
  mismatch recorded in `SPEC.md`
- the reviewed `p.35` / `t.NF` anchors are either runnable or narrowed to a
  smaller, explicitly documented non-product corroboration issue
- any broader POSIX expression-surface expansion happens only after an explicit
  roadmap decision, with tests, `SPEC.md`, and backend claims updated together
- if no widening is approved, the roadmap and docs make it explicit that the
  broader operator families remain intentionally unclaimed rather than
  implicitly unfinished

### P19: Residual Host-Runtime Boundary Audit

Objective:
- inventory the remaining public routes to the Python host runtime and turn
  that residual boundary into an explicit backend-first follow-up plan

In scope:
- document the backend-first purpose and current host-runtime boundary
- identify the public entry points that can still reach `execute_host_runtime()`
- check in a residual host-only matrix for representative public forms
- add routing regressions for representative residual host-routed forms
- classify residual cases as claimed AOT debt, backend-ready widening
  candidates, backend-incomplete work, or intentionally out-of-contract forms
- make an explicit product decision about whether ordinary `quawk` should keep
  temporary host fallback for unclaimed forms or fail clearly outside the
  AOT-backed contract
- implementation details for this phase live in
  [plans/host-runtime-boundary-audit.md](plans/host-runtime-boundary-audit.md)
  and [plans/residual-host-runtime-matrix.md](plans/residual-host-runtime-matrix.md)

Exit criteria:
- the current public host-runtime routes are explicitly inventoried and checked
  in
- the residual representative host-routed forms are pinned by direct tests
- the roadmap and docs distinguish clearly between claimed AOT debt and
  intentionally unclaimed host-routed surface
- the repo has an explicit next-step policy for unclaimed host-routed programs
  instead of relying on implicit behavior

### P25: Static Variable Slots

Objective:
- allocate known variables in fixed struct offsets instead of string-named
  hash table entries, enabling direct memory access for compile-time-known
  variables

In scope:
- design slot allocation data structures (`VariableSlot`, `SlotAllocation`)
- implement slot allocation pass over normalized AST
- generate LLVM struct type with typed variable slots for the state struct
- add runtime slot accessor functions for numeric and string slots
- update lowering to emit slot addresses for known variables
- preserve fallback to string-named hash for dynamic/unknown variables
- implementation details live in [performance-implementation.md](performance-implementation.md)

Exit criteria:
- all scalar variables in `BEGIN` blocks use static slots in generated IR
- slot-based variable access tests pass
- string-based hash access still works for dynamic cases
- `--ir` output shows direct slot access for simple programs

### P26: Type Inference

Objective:
- infer whether variables are numeric-only, string-only, or mixed at compile
  time, enabling type-aware code generation

In scope:
- define type lattice with `UNKNOWN`, `NUMERIC`, `STRING`, `MIXED`
- implement type inference pass over AST
- propagate types through assignments and expressions
- handle control flow conservatively (assume any execution count)
- classify field access (`$1`) and user input as `MIXED`
- store type annotations in lowering state for use during code generation
- implementation details live in [performance-implementation.md](performance-implementation.md)

Exit criteria:
- type inference pass produces type annotations for all variables
- numeric-only variables identified in simple programs (e.g., `for (i=1; i<=10; i++)`)
- inference tests cover numeric, string, mixed, and unknown cases
- no regression in correctness for mixed-type programs

### P27: Specialized Operations

Objective:
- generate type-specialized IR for operations where types are known

In scope:
- numeric fast path for arithmetic on known-numeric variables
- numeric fast path for comparisons where both operands are numeric
- string fast path for concatenation where strings are known
- slot-based direct load/store for known-type variables
- fallback to full AWK semantics for mixed/unknown types
- implementation details live in [performance-implementation.md](performance-implementation.md)

Exit criteria:
- numeric-only loops show direct `fcmp` instructions in `--ir` output
- arithmetic on numeric variables uses direct `fadd`/`fsub`/`fmul`/`fdiv`
- full AWK semantics preserved for mixed/unknown types
- performance benchmarks show measurable improvement

### P28: LLVM Optimization Integration

Objective:
- apply LLVM optimization passes to generated IR for constant folding, dead
  code elimination, and register allocation

In scope:
- add `--optimize` / `-O` CLI flag
- implement IR optimization using LLVM `opt` tool
- define pass pipeline for level 1 (basic) and level 2 (aggressive)
- integrate optimization into public execution path
- add `--ir=optimized` mode for inspection
- handle missing `opt` gracefully with fallback
- implementation details live in [performance-implementation.md](performance-implementation.md)

Exit criteria:
- `quawk -O program.awk` produces optimized IR
- constant expressions like `1 + 2` are folded by optimizer
- dead variable stores are eliminated
- optimization is optional and does not affect correctness

### P29: Runtime ABI Refinement

Objective:
- reduce function call overhead for hot operations through inline-able fast
  paths and optimized calling conventions

In scope:
- profile current hot paths to identify top-called runtime functions
- add slot storage arrays to runtime struct for slot-based variables
- add inline slot accessor functions for hot variable operations
- create slot-aware runtime entry point
- generate IR calls to fast-path entry points where applicable
- document ABI stability guarantees
- implementation details live in [performance-implementation.md](performance-implementation.md)

Exit criteria:
- hot paths identified with profiling data
- slot-based inline accessors available in runtime
- generated IR uses fast-path calls for slot variables
- microbenchmarks show reduced call overhead
- runtime ABI documented for future stability

### P30: Execution Completeness Closure

Objective:
- eliminate the remaining grammar/backend split so grammar-valid, semantically
  admitted AWK forms execute end-to-end through the compiled backend/runtime
  path

In scope:
- add execution-completeness guardrails so new parser widening does not outrun
  backend support again
- implementation details live in
  [execution-completeness-plan.md](plans/execution-completeness-plan.md)

Exit criteria:
- representative programs for the remaining gap buckets execute through
  ordinary public `quawk`
- the same representative programs work under `--ir` and `--asm`
- the direct-function subset is no longer required as a long-term special-case
  execution lane for richer functions
- parseable-but-not-lowerable admitted forms are eliminated from the checked-in
  grammar contract

### P31: Remaining POSIX Contract Closure

Objective:
- turn the remaining product-side end-to-end gaps into an explicit POSIX
  closure wave instead of leaving them under vague "broader corners" wording

In scope:
- baseline the remaining parser-admitted product gaps with POSIX-vs-extension
  classification
- implement remaining POSIX-required forms such as compound assignment if they
  stay in the public contract
- decide contract treatment for non-name array-target forms, broader
  substitution targets, and builtin names outside the current subset
- retire or narrow the direct-function special execution lane
- implementation details live in
  [remaining-posix-compatibility-plan.md](plans/remaining-posix-compatibility-plan.md)

Exit criteria:
- the remaining product-side gaps are explicitly classified as POSIX-required,
  extension-only, or intentionally out of contract
- any remaining POSIX-required gaps execute through ordinary public `quawk`
  plus `--ir` and `--asm`
- the direct-function special lane is no longer required for claimed behavior,
  or is documented as non-contract internal debt with explicit tests

### P32: Final POSIX Compatibility Corroboration

Objective:
- finish the remaining upstream-corroboration and reviewed-skip cleanup for the
  implemented POSIX surface

In scope:
- resolve the `rand()` corroboration or reference-disagreement policy
- complete the final compatibility stop-line audit
- implementation details live in
  [remaining-posix-compatibility-plan.md](plans/remaining-posix-compatibility-plan.md)

Exit criteria:
- no stale reviewed compatibility anchors remain for implemented POSIX
  families
- any remaining upstream disagreement is explicitly classified
- `SPEC.md`, `docs/compatibility.md`, the upstream manifest, and the roadmap
  agree on the final implemented POSIX surface

### P33: Direct-Path Removal And Route Cleanup

Objective:
- remove the remaining restricted direct lowering path from `jit.py` and make
  reusable backend/runtime lowering the only compiled execution route for
  in-contract programs

In scope:
- remove dead or stale direct-lowering helpers, guards, and error messages that
  no longer match the intended execution model
- widen backend routing so forms already implemented by reusable lowering do
  not fail behind stale direct-path gates
- add focused regressions for the representative over-gated programs identified
  in the backend audit, including `BEGIN { print $1 }`, `BEGIN { x = !1 }`,
  `BEGIN { x = ++y }`, `BEGIN { x = 1; x += 2 }`,
  `BEGIN { if ("a" "b") x = 1 }`, and `BEGIN { x = a["k"] }`
- rebaseline roadmap and design text so the reusable backend path is described
  as the only compiled execution route
- implementation details live in
  [direct-path-removal-plan.md](plans/direct-path-removal-plan.md)

Exit criteria:
- `lower_to_llvm_ir()` no longer keeps a separate restricted direct lowering
  fallback for supported public execution
- representative previously over-gated programs execute and inspect through the
  reusable backend/runtime path
- remaining backend `RuntimeError` messages correspond only to genuinely
  unsupported reusable-backend gaps rather than stale routing debt
- roadmap and design docs no longer describe the direct path as active product
  behavior

### P34: Local Scalar SSA Promotion

Objective:
- promote action-local numeric scalars out of `%quawk.state` when their lifetime
  and observability stay local to one lowered function, so LLVM can optimize hot
  loops against local values instead of repeated state loads and stores

In scope:
- baseline the current optimizer-kernel and representative runtime-workload IR
  so the remaining state-shaped scalar traffic is explicit before implementation
- add a conservative residency classifier that decides which numeric scalars must
  stay in `%quawk.state` and which can stay backend-local to one lowered
  function
- lower the first supported subset of non-escaping numeric scalars through
  function-local storage instead of `%quawk.state`
- reshape local-scalar lowering so representative loops are friendly to LLVM
  `mem2reg`/SSA-style cleanup after `opt`
- preserve `%quawk.state` residency for escaping, mixed, string, field, array,
  builtin-coupled, and cross-phase values whose state must remain AWK-visible
- rebaseline the optimized-vs-unoptimized benchmark suite and focused `--ir`
  regressions against the new lowering shape
- implementation notes should extend
  [performance-implementation.md](performance-implementation.md) when
  implementation begins

Historical `T-290` baseline anchors before `T-292`:
- `scalar_fold_loop` still keeps `n`, `s`, `bias`, `scale`, `i`, `base`, `x`,
  `y`, `z`, and `dead` in `%quawk.state`
- `branch_rewrite_loop` still keeps `n`, `total`, `limit`, `i`, `left`,
  `right`, and `always` in `%quawk.state`
- `field_aggregate` remains runtime-shaped, with `qk_get_field_inline` calls
  plus state-backed locals such as `a`, `b`, `c`, `derived`, `total`, and
  `count`

Exit criteria:
- representative scalar kernels no longer keep loop-local numeric temporaries in
  `%quawk.state` when those values are safe to keep local
- focused `--ir` regressions show materially fewer state loads and stores for
  promoted locals, with optimized IR collapsing to direct arithmetic/comparison
  shapes for representative loops
- ordinary execution preserves existing AWK-visible behavior for values that
  still need runtime/state residency
- the optimized-vs-unoptimized benchmark suite is rerun against the promoted-
  local lowering, and roadmap/benchmark docs explain clearly whether the current
  workload mix shows enough `lli_only` movement to justify `-O`

### P35: Agent Workflow Documentation Alignment

Objective:
- make `AGENTS.md` the useful first-read workflow guide for coding agents by
  aligning it with the current setup, testing, compatibility, architecture, and
  documentation expectations spread across the rest of the repo

In scope:
- resolve the stale `docs/agent-workflow.md` references by either linking to
  `AGENTS.md` directly or adding a deliberate shim
- add complete setup and validation guidance to `AGENTS.md`, including LLVM
  prerequisites, editable dev install, submodule initialization, upstream
  reference bootstrap, static checks, and marker-based pytest suites
- add testing and compatibility decision rules for corpus cases, ordinary
  Python tests, `xfail`, pinned One True Awk, pinned `gawk --posix`, and
  divergence classification
- add implementation guardrails that keep claimed AWK semantics on the compiled
  backend/runtime path rather than Python semantic fallback
- add a compact documentation source-of-truth map for `SPEC.md`,
  `docs/design.md`, grammar/AST docs, roadmap, changelog, release checklist,
  and compatibility notes
- tighten git and documentation hygiene guidance for dirty worktrees, staging,
  and relative links
- implementation details live in
  [agent-workflow-doc-alignment-plan.md](plans/agent-workflow-doc-alignment-plan.md)

Exit criteria:
- `AGENTS.md` includes the setup, validation, testing, compatibility,
  architecture, doc-update, changelog, git-safety, and relative-link guidance
  needed for ordinary coding-agent work
- README and contributor guidance point to the actual agent workflow document
  rather than a missing path
- touched docs avoid introducing new absolute local filesystem links
- relevant documentation validation is run or any skipped check is explained

P35 completion result:
- `AGENTS.md`, README, contributing docs, getting-started docs, and testing docs
  now agree on the agent workflow document path, `uv`-first command style,
  compatibility reference workflow, compiled-backend implementation guardrails,
  documentation update expectations, and dirty-worktree staging guidance

## Immediate Next Tasks

Start here unless priorities change:

`T-296` through `T-301` are complete. `P35` is complete.

Immediate next tasks:
- no active `P35` tasks remain; future agent-workflow changes should start as
  a new scoped follow-on task

P35 closeout validation:
- `uv run pytest -m docs_contract`
- `uv run pytest -q -m core`

### P36: Implementation Readability Refactor

Objective:
- make the implementation easier to read and safely modify by splitting large
  modules along real compiler/runtime ownership boundaries, adding a source map,
  and reducing repeated AST traversal and raw LLVM string construction

Current status:
- the P36 foundation work is already landed: the source-level implementation
  map exists, AST definitions/formatting no longer live in `parser.py`, and
  shared AST traversal helpers are checked in and adopted by analysis passes
- `T-306` is now complete: backend tool orchestration, runtime ABI declarations,
  driver IR generation, and lowering state now live under `src/quawk/backend/`,
  while `jit.py` remains the public facade
- `T-307` is now complete: a lightweight LLVM IR builder exists under
  `src/quawk/backend/`, and representative lowering paths now use it without
  changing the public backend facade
- active implementation work now starts at `T-308`, focused on the lowering
  module split, runtime-split decision, and test discoverability

In scope:
- add a source-level implementation map for the `src/quawk` package
- split AST node definitions and AST formatting out of `parser.py`
- introduce shared AST traversal helpers for analysis passes
- extract backend orchestration, runtime ABI declarations, driver IR generation,
  and lowering state out of `jit.py`
- introduce a small LLVM IR builder for recurring instruction/text emission
- split statement, expression, lvalue, and builtin lowering into focused backend
  modules
- split `qk_runtime.c` by runtime domain or record a checked-in decision for
  deferring that split
- improve test discoverability by moving newly touched task-numbered tests
  toward behavior-oriented names
- implementation details live in
  [implementation-readability-refactor-plan.md](plans/implementation-readability-refactor-plan.md)

Exit criteria:
- `src/quawk/README.md` or equivalent source map exists
- parser, AST definitions, and AST formatting have separate ownership
- at least the highest-churn AST analysis passes share traversal helpers
- backend orchestration, runtime ABI declarations, lowering state, statement
  lowering, and expression lowering are no longer all owned by `jit.py`
- runtime C source is split or a reviewed deferral decision is checked in
- core validation passes after the final refactor task

## Immediate Next Tasks

Start here unless priorities change:

`T-296` through `T-301` are complete. `P35` is complete.
`T-302` through `T-305` are complete. `P36` is active.

Immediate next tasks:
- `T-308`: Split statement, expression, lvalue, and builtin lowering modules.
- `T-309`: Split or explicitly defer splitting the C runtime source.
- `T-310`: Improve test discoverability for newly touched refactor coverage.
- `T-311`: Validate and close the implementation readability refactor.

P36 entry criteria:
- the current implementation review identified `jit.py`, `parser.py`, repeated
  AST traversal, `qk_runtime.c`, and task-numbered tests as the main
  readability hotspots
- the current checked-in baseline already covers the source map, AST split, and
  shared traversal-helper foundation, so remaining execution should start with
  backend ownership cleanup rather than reopening those completed moves
- implementation notes for `P36` should follow
  [implementation-readability-refactor-plan.md](plans/implementation-readability-refactor-plan.md)

## Backlog

Status values:
- `todo`
- `in_progress`
- `blocked`
- `done`

Priority values:
- `P0`
- `P1`
- `P2`

| ID | Phase | Priority | Task | Depends On | Acceptance | Status |
|---|---|---|---|---|---|---|
| T-000 | P0 | P0 | Rebaseline docs to the Python/LLVM implementation plan | none | Core docs reflect Python 3.14 + `uv` workflow | done |
| T-001 | P0 | P0 | Create `src/`, `tests/`, and `scripts/` directories | none | Directories exist and are documented | done |
| T-002 | P0 | P0 | Add `pyproject.toml` with package metadata and console entrypoint | T-001 | `quawk --help` entrypoint resolves in the local `.venv` | done |
| T-003 | P0 | P0 | Add initial `src/quawk/__init__.py` and `src/quawk/cli.py` placeholders | T-002 | Placeholder package imports cleanly | done |
| T-004 | P0 | P1 | Add `uv` bootstrap instructions for Python `3.14.x` and the project `.venv` | none | Clean checkout setup succeeds with documented `uv` commands | done |
| T-005 | P0 | P1 | Add `uv`-based contributor command shortcuts or workflow notes | T-004 | Common contributor commands run cleanly from the documented `uv` environment | done |
| T-006 | P0 | P0 | Keep testing workflow centered on pytest rather than custom gate tooling | none | Repo workflow is described without a second metadata/checking system | done |
| T-007 | P0 | P1 | Document local format/lint/type/test checks | T-002 | Common local quality checks are documented and runnable | done |
| T-008 | P0 | P1 | Add `CONTRIBUTING.md` workflow and review expectations | none | README links contributing guide and guide is coherent | done |
| T-043 | P1 | P0 | Author P1 MVP end-to-end tests for the initial executable path | T-002, T-006 | Minimal end-to-end CLI execution tests are committed before implementation | done |
| T-049 | P1 | P0 | Implement minimal lexer support for `BEGIN`, `print`, braces, and string literals | T-043 | MVP tokenization is stable and supporting lexer tests pass | done |
| T-050 | P1 | P0 | Implement minimal parser for `BEGIN { print "literal" }` | T-049 | MVP program parses into a stable AST form | done |
| T-051 | P1 | P0 | Implement lowering/runtime for literal-print `BEGIN` programs | T-050 | MVP program executes through the JIT path | done |
| T-052 | P1 | P0 | Wire CLI execution for inline programs and `-f` files | T-051 | MVP path runs from both invocation forms | done |
| T-053 | P1 | P0 | Add end-to-end tests for stdout and exit status of the MVP path | T-052 | Inline and file-based MVP smoke cases pass end-to-end | done |
| T-054 | P2 | P0 | Refactor the frontend architecture before the next syntax increment | T-053 | Source manager/cursor replaces concatenated source, scanner/token model are generalized, and parser uses broader `Program`/`PatternAction`/`Action`/`Stmt`/`Expr` categories without materially expanding accepted syntax | done |
| T-055 | P2 | P0 | Author end-to-end tests for numeric print in `BEGIN` | T-054 | CLI tests exist for `BEGIN { print 1 }` and `BEGIN { print 1 + 2 }` before implementation | done |
| T-009 | P2 | P0 | Extend token/source-span modeling for numeric literals and `+` | T-054, T-055 | Token/span code cleanly supports numeric literals and additive operators | done |
| T-010 | P2 | P0 | Extend lexing for numeric literals, `+`, and the print-expression path | T-009, T-054, T-055 | Lexer fixtures pass for the numeric-print increment | done |
| T-011 | P4 | P1 | Implement `REGEX` vs `/` context-sensitive lexing when regex support becomes active | T-010 | Dedicated ambiguity tests pass when regex literals are in scope | done |
| T-012 | P2 | P0 | Define AST nodes for numeric literals and additive binary expressions | T-009, T-054, T-055 | AST matches the numeric-print increment | done |
| T-013 | P2 | P0 | Extend the parser for `print` expressions in `BEGIN` | T-012, T-054, T-055 | The parser accepts `BEGIN { print 1 }` and the additive form | done |
| T-014 | P2 | P1 | Implement additive precedence for the numeric-print increment | T-013 | `1 + 2 + 3` parses and executes with stable precedence behavior | done |
| T-016 | P10 | P2 | Add parser golden tests for AST snapshots where they improve reviewability | T-012, T-014 | Golden outputs are deterministic and useful | done |
| T-017 | P4 | P1 | Add parser conformance fixtures mapped to supported grammar sections | T-092, T-100 | Coverage matrix shows supported grammar areas | done |
| T-044 | P5 | P1 | Author semantic tests for the first user-defined function behavior | T-017 | Tests exist for the initial function-call path and its first legality checks before implementation | done |
| T-018 | P5 | P1 | Build symbol table/scoping support when variables or functions require it | T-012, T-044 | Scope tests pass for supported constructs | done |
| T-019 | P5 | P1 | Implement semantic checks for lvalues and assignment legality as needed | T-018 | Invalid assignment tests fail with expected diagnostics | done |
| T-020 | P5 | P1 | Implement control-flow legality checks when loops/functions land | T-018 | `break`/`continue`/`return` legality tests pass for supported constructs | done |
| T-021 | P5 | P2 | Implement function declaration/definition checks when functions land | T-018 | Duplicate/conflicting definitions handled deterministically | done |
| T-022 | P6 | P1 | Add normalization only where backend support needs it | T-019, T-020, T-021 | Lowering consumes stable normalized forms for supported behavior | done |
| T-023 | P10 | P2 | Define semantic error code catalog after core execution behavior stabilizes | T-019, T-020, T-021 | Errors emitted with stable code and source span | done |
| T-024 | P2 | P0 | Extend the runtime value model for numeric values in the current increment | T-014 | Runtime representation supports numeric literals and additive results | done |
| T-025 | P2 | P0 | Extend lowering from supported AST forms to LLVM IR for numeric print | T-024 | `BEGIN { print 1 }` and `BEGIN { print 1 + 2 }` execute through the LLVM-backed path | done |
| T-026 | P3 | P0 | Implement runtime input loop (`BEGIN`, records, `END`) when mixed program execution becomes active | T-024, T-025 | Mixed `BEGIN` / record / `END` fixtures pass for the supported subset | todo |
| T-027 | P6 | P1 | Implement builtins only as required by the active deliverable or compatibility goals | T-024, T-026 | Builtin fixture tests pass for the selected subset | done |
| T-107 | P6 | P0 | Author end-to-end tests for associative arrays and indexed access | T-100 | CLI tests exist for the first array read/write programs before implementation | done |
| T-108 | P6 | P0 | Implement associative arrays and indexed assignment/read | T-107, T-022 | `BEGIN { a["x"] = 1; print a["x"] }` executes correctly | done |
| T-109 | P6 | P0 | Author end-to-end tests for `delete`, `for`, and `for ... in` | T-108 | CLI tests exist for representative array deletion and iteration programs before implementation | done |
| T-110 | P6 | P0 | Implement `delete`, `for`, and `for ... in` for the array model | T-109, T-108 | Representative array deletion and iteration programs execute correctly | done |
| T-111 | P7 | P0 | Author parser and semantic baselines for the remaining POSIX-core syntax surface | T-017 | Tests exist for the remaining POSIX-core statements, operators, and lvalue forms before implementation | done |
| T-112 | P7 | P0 | Extend token and lexer support for the remaining POSIX-core operators and keywords | T-111 | Lexer fixtures pass for the remaining POSIX-core token surface | done |
| T-113 | P7 | P0 | Complete parser and AST support for the remaining POSIX-core statement, expression, and lvalue forms | T-112 | The parser accepts the remaining POSIX-core statement and expression families with stable AST shapes | done |
| T-114 | P7 | P1 | Complete semantic validation for the remaining POSIX-core syntax surface | T-113 | Semantics enforce legality for the completed POSIX-core frontend surface with deterministic diagnostics | done |
| T-115 | P8 | P0 | Author runtime and builtin baselines for the remaining POSIX-core execution surface | T-114 | CLI and corpus tests exist for the remaining POSIX-core runtime, builtin, and builtin-variable behaviors before implementation | done |
| T-116 | P8 | P0 | Replace the scalar runtime model with AWK-style value cells and coercions | T-115 | Runtime values support AWK-style numeric/string duality, truthiness, and conversion rules across the supported surface | done |
| T-117 | P8 | P0 | Implement the remaining POSIX-core runtime semantics for statements, patterns, records, and fields | T-116 | Public execution supports the remaining POSIX-core control-flow, pattern, record, and field behaviors | done |
| T-118 | P8 | P0 | Implement the remaining POSIX-core builtins and builtin variables | T-116, T-117 | Public execution covers the chosen POSIX-core builtin set and builtin-variable semantics | done |
| T-119 | P9 | P0 | Author backend-parity and inspection baselines for the completed POSIX-core subset | T-118 | Tests specify backend execution and `--ir` / `--asm` behavior for representative programs across the completed surface before implementation | done |
| T-120 | P9 | P0 | Extend lowering and runtime ABI coverage to the completed POSIX-core subset | T-119 | Representative programs across the completed POSIX-core subset execute through the backend path and lower to reusable artifacts | done |
| T-121 | P9 | P1 | Remove the remaining array, iteration, and builtin host-runtime-only gaps and close the major pre-compatibility backend gaps | T-120 | Representative array, iteration, builtin, and record programs no longer stay on the host runtime, and any remaining fallback families are explicitly documented | done |
| T-028 | P2 | P1 | Add integration tests for stdout/stderr/exit status of the numeric-print increment | T-025 | Integration tests run for the current increment in required CI jobs | done |
| T-056 | P2 | P0 | Author end-to-end tests for scalar variables and assignment in `BEGIN` | T-028 | CLI tests exist for `BEGIN { x = 1; print x }` and `BEGIN { x = 1 + 2; print x }` before implementation | done |
| T-057 | P2 | P0 | Extend token/source-span modeling for names and `=` | T-028 | Token/span code cleanly supports assignment-oriented syntax | done |
| T-058 | P2 | P0 | Extend lexing for names, `=`, and assignment-oriented statement paths | T-057, T-056 | Lexer fixtures pass for the assignment increment | done |
| T-059 | P2 | P0 | Define AST nodes for names, assignments, and variable references | T-057, T-056 | AST matches the assignment increment | done |
| T-060 | P2 | P0 | Extend the parser for assignment statements and variable expressions in `BEGIN` | T-059, T-056 | The parser accepts assignment and variable-read programs for the increment | done |
| T-061 | P2 | P0 | Extend the runtime value model for scalar bindings | T-060 | Runtime representation supports assignment and lookup of scalar values | done |
| T-062 | P2 | P0 | Extend LLVM lowering for assignment and variable reads | T-061 | `BEGIN { x = 1; print x }` and `BEGIN { x = 1 + 2; print x }` execute through the LLVM-backed path | done |
| T-063 | P2 | P1 | Add integration tests for stdout/stderr/exit status of the assignment increment | T-062 | Integration tests run for the assignment increment in required CI jobs | done |
| T-064 | P2 | P0 | Author end-to-end tests for bare actions and simple field reads | T-063 | CLI tests exist for `{ print $0 }` and `{ print $1 }` before implementation | done |
| T-065 | P2 | P0 | Extend token/source-span modeling for `$` and field-oriented record syntax | T-063 | Token/span code cleanly supports the record-loop increment | done |
| T-066 | P2 | P0 | Extend lexing for `$` and the active record-processing path | T-065, T-064 | Lexer fixtures pass for the record-loop increment | done |
| T-067 | P2 | P0 | Define AST nodes for bare actions, field references, and record-driven execution | T-065, T-064 | AST matches the record-loop increment | done |
| T-068 | P2 | P0 | Extend the parser for bare action programs and `$` field expressions | T-067, T-064 | The parser accepts `{ print $0 }` and `{ print $1 }` | done |
| T-069 | P2 | P0 | Implement the runtime input loop for record-driven execution | T-068 | Runtime executes actions once per input record | done |
| T-070 | P2 | P0 | Extend LLVM lowering for `$0` and `$1` reads in bare actions | T-069 | Bare action programs execute through the LLVM-backed path | done |
| T-071 | P2 | P1 | Add integration tests for stdout/stderr/exit status of the record-loop increment | T-070 | Integration tests run for the record-loop increment in required CI jobs | done |
| T-072 | P2 | P0 | Author end-to-end tests for comparisons and control flow in `BEGIN` | T-071 | CLI tests exist for the planned `if` and `while` examples before implementation | done |
| T-073 | P2 | P0 | Extend token/source-span modeling for comparison and control-flow syntax | T-071 | Token/span code cleanly supports the control-flow increment | done |
| T-074 | P2 | P0 | Extend lexing for `<`, parentheses, and the active control-flow keywords | T-073, T-072 | Lexer fixtures pass for the control-flow increment | done |
| T-075 | P2 | P0 | Define AST nodes for comparisons, blocks, `if`, and `while` | T-073, T-072 | AST matches the control-flow increment | done |
| T-076 | P2 | P0 | Extend the parser for comparison expressions and control-flow statements | T-075, T-072 | The parser accepts the planned `if` and `while` examples | done |
| T-077 | P2 | P0 | Extend runtime state for branching and loop execution | T-076 | Runtime can execute the supported control-flow constructs | done |
| T-078 | P2 | P0 | Extend LLVM lowering for comparisons and control flow | T-077 | The supported control-flow examples execute through the LLVM-backed path | done |
| T-079 | P2 | P1 | Add integration tests for stdout/stderr/exit status of the control-flow increment | T-078 | Integration tests run for the control-flow increment in required CI jobs | done |
| T-122 | P10 | P0 | Author grammar-contract baselines and a conformance checklist for the remaining doc-vs-implementation gaps | T-114, T-118, T-121 | Tests and checklist make the remaining `quawk.ebnf`/design/AST drift explicit before implementation | done |
| T-123 | P10 | P0 | Implement the remaining `quawk.ebnf` parser gaps and remove parser-side narrowing | T-122 | The parser accepts the full `quawk.ebnf` surface with stable AST shapes for the admitted language | done |
| T-124 | P10 | P0 | Remove semantic, runtime, and backend narrowing for grammar-admitted forms | T-123 | Public execution no longer fails on grammar-valid forms, and backend limits are narrowed to explicitly documented non-grammar gaps | done |
| T-125 | P10 | P1 | Rewrite `design.md` current-state sections and add explicit `quawk.ebnf` conformance notes | T-124 | Design docs accurately describe the parser, public execution, and backend support model | done |
| T-126 | P10 | P1 | Consolidate AST docs around the chosen `quawk.asdl` contract | T-124 | AST docs clearly describe the implemented parser output through one aligned schema | done |
| T-039 | P12 | P1 | Expand CLI behavior only as execution support justifies it | T-026 | Help/version/run-path behavior is stable for supported features | done |
| T-047 | P11 | P0 | Author compatibility tests as `xfail` baseline for the supported subset | T-028 | Compatibility baseline committed with expected failures | done |
| T-035 | P11 | P0 | Implement differential test runner (`one-true-awk`, `gawk --posix`, `quawk`) | T-028, T-047 | Runner emits comparable normalized outputs | done |
| T-036 | P11 | P0 | Seed compatibility corpus for supported parser/runtime behaviors | T-035 | Core corpus executes and reports per-case status | done |
| T-037 | P11 | P1 | Add divergence manifest and classification workflow | T-035 | Divergences tracked with explicit categories | done |
| T-127 | P11 | P0 | Define the next compatibility corpus expansion from the public feature matrix | T-036, T-037, T-040 | `docs/compatibility.md` maps each implemented feature family to a target coverage level and names the next required corpus cases for every area still at `none` or `smoke` | done |
| T-128 | P11 | P0 | Add differential corpus coverage for user-defined functions and standard loop families | T-127 | New corpus cases cover at least one happy-path and one edge-path for functions, `while`, standard classic `for`, plain `for ... in`, `break`, and `continue`; required compatibility suites pass or all new divergences are classified | done |
| T-129 | P11 | P0 | Add differential corpus coverage for CLI/runtime option interactions and builtin variables | T-127 | New corpus cases cover `-v`, stdin `-`, `--`, multi-file `FILENAME`, and multi-file builtin-variable behavior; required compatibility suites pass or all new divergences are classified | done |
| T-130 | P11 | P1 | Add differential corpus coverage for coercions, regex/range boundaries, and builtin boundary behavior | T-127 | New corpus cases cover at least one additional coercion/truthiness case, one regex boundary case, one range boundary case, and boundary cases for the currently claimed builtins; required compatibility suites pass or all new divergences are classified | done |
| T-131 | P11 | P1 | Rebaseline the compatibility coverage matrix after the expansion wave | T-128, T-129, T-130 | `docs/compatibility.md` reflects the new case inventory, updated coverage levels, and the remaining gaps after the new cases land | done |
| T-137 | P11 | P0 | Pin One True Awk and gawk upstream sources and define the repo-managed bootstrap workflow | T-131 | `third_party/` holds pinned upstream source trees, and the local bootstrap/build flow is implemented and documented | done |
| T-138 | P11 | P0 | Remove host-`awk` aliasing and resolve only pinned local reference binaries | T-137 | Compatibility code fails clearly when the repo-managed reference builds are missing and never treats host `awk` as One True Awk | done |
| T-139 | P11 | P0 | Add the upstream suite inventory and checked-in selection manifest | T-137, T-138 | The repo classifies which upstream cases are run or skipped, with explicit reasons and adapter metadata for both upstream suites | done |
| T-140 | P11 | P1 | Implement the first upstream-suite-derived compatibility subset for One True Awk and gawk | T-139 | A portable, POSIX-relevant selected subset from both upstream suites executes across `quawk`, One True Awk, and gawk with deterministic reporting | done |
| T-141 | P11 | P1 | Reclassify the repo-owned corpus as supplemental `compat_local` coverage | T-140 | The local corpus remains green and fast, but docs and pytest surfaces no longer present it as the primary compatibility authority | done |
| T-142 | P11 | P1 | Add evaluated-divergence metadata and companion compatibility notes for upstream-suite failures | T-140 | Executed upstream failures are either fixed or classified with checked-in metadata plus reviewed human-readable notes, and stale or unclassified entries fail the gate | done |
| T-143 | P11 | P2 | Add the optional CI job and promotion criteria for the upstream compatibility gate | T-140, T-141, T-142 | CI can build the pinned references and run the selected upstream compatibility subset, and the roadmap/docs define when that job becomes required | done |
| T-144 | P11 | P0 | Map implemented feature families in `SPEC.md` to the upstream case inventory | T-143 | `tests/upstream/selection.toml` and `docs/compatibility.md` make it explicit which upstream cases or skips cover every `implemented` feature family in `SPEC.md` | done |
| T-145 | P11 | P0 | Expand in-scope One True Awk `p.*` coverage across implemented POSIX families | T-144 | Adapter-compatible, in-scope One True Awk `p.*` cases are broadly classified `run` or `skip`, and the runnable set expands coverage across the implemented family matrix | done |
| T-146 | P11 | P1 | Add gawk fixture-backed corroborating coverage for implemented POSIX families | T-144 | For each major implemented family with clean `.ok` or `.in/.ok` fixtures, the selection manifest includes at least one runnable gawk corroborating case or an explicit reviewed skip | done |
| T-147 | P11 | P1 | Fill remaining implemented-family gaps with selected One True Awk `t.*` cases | T-145, T-146 | No `implemented` feature family in `SPEC.md` lacks runnable upstream coverage from at least one suite unless the gap is explicitly deferred in reviewed selection metadata | done |
| T-148 | P11 | P1 | Add selected shell-driver adapters only for still-uncovered in-scope families | T-147 | One True Awk `T.*` and gawk `.sh` support lands only where direct-file fixtures cannot cover a claimed in-scope family, and shell-driver-only skips remain explicit | done |
| T-149 | P11 | P0 | Complete the upstream-suite done-line audit and stop criteria | T-147, T-148 | Every `implemented` family in `SPEC.md` has upstream coverage, no blocking `posix-required-fix` entries remain for claimed behavior, and the local corpus is no longer the sole compatibility evidence for any implemented POSIX family | done |
| T-048 | P12 | P0 | Author release-readiness smoke tests as `xfail` baseline | T-036, T-037 | Release-readiness baseline committed with expected failures | done |
| T-040 | P12 | P1 | Add `SPEC.md` feature matrix (implemented/planned/out-of-scope) | T-036 | Feature matrix aligns with tests and docs | done |
| T-042 | P12 | P1 | Finalize release checklist and changelog workflow | T-039, T-040 | Checklist is complete and versioned | done |
| T-150 | P13 | P0 | Author the architecture-audit baseline for claimed backend execution | T-149, T-042 | Tests and docs enumerate every currently claimed feature family that still lacks full backend/runtime execution or `--ir` / `--asm` support | done |
| T-151 | P13 | P0 | Lower user-defined functions through the compiled backend/runtime path | T-150 | Representative claimed function programs execute without Python-side semantic fallback, and `--ir` / `--asm` support those programs | done |
| T-152 | P13 | P0 | Lower `exit` and `nextfile` through the compiled backend/runtime path | T-150 | Representative claimed `exit` and `nextfile` programs execute through the backend/runtime path and support inspection output | done |
| T-153 | P13 | P0 | Lower the remaining claimed scalar-string and coercion families through the backend/runtime path | T-150 | Claimed concatenation/coercion-heavy execution paths no longer require Python-side semantic fallback, and their backend tests are explicit | done |
| T-154 | P13 | P1 | Fold Python-fallback removal into the remaining backend-parity wave instead of landing it as a standalone regression step | T-153 | Roadmap, POSIX plan, and follow-on tasks treat fallback removal as part of the same implementation wave that closes the remaining claimed backend gaps | done |
| T-155 | P13 | P1 | Close the remaining audited claimed backend-execution and `--ir` / `--asm` parity gaps as one implementation wave | T-151, T-152, T-153 | The remaining audited claimed families gain compiled execution plus inspection support, leaving `T-156` to rebaseline the broader AOT-only contract docs and fallback story | done |
| T-156 | P13 | P1 | Add the architecture audit gate and rebaseline the docs for the AOT-only contract | T-155 | Tests, `SPEC.md`, and `docs/design.md` all prove that Python is compile/orchestration only for claimed AWK semantics | done |
| T-157 | P14 | P0 | Audit and split `SPEC.md` rows for POSIX-facing feature families | T-156 | `SPEC.md` no longer hides known POSIX gaps behind broad rows for `print`, builtins, builtin variables, CLI variables, or backend parity | done |
| T-158 | P14 | P0 | Implement full POSIX `print` behavior | T-157 | Bare `print`, multi-argument `print`, `OFS`, and `ORS` behave correctly under direct CLI tests and can be corroborated by promoted upstream cases | done |
| T-159 | P14 | P0 | Implement POSIX formatting variables | T-158 | `OFMT` and `CONVFMT` influence output and formatting as claimed by `SPEC.md` | done |
| T-160 | P14 | P1 | Implement POSIX output redirection and pipe output | T-158 | `print` / `printf` support `>`, `>>`, `|`, and `close()` for the forms claimed in `SPEC.md` | done |
| T-161 | P14 | P0 | Close the reviewed `printf` parity gaps | T-158, T-159 | The reviewed formatting and `substr(..., ..., ...)`-inside-`printf` mismatches are fixed or replaced with narrower classified gaps | done |
| T-162 | P14 | P0 | Implement the missing POSIX string and regex builtins | T-157 | `index`, `match`, `sub`, `gsub`, `sprintf`, `tolower`, and `toupper` have parser, runtime, and compatibility coverage | done |
| T-163 | P14 | P1 | Implement the missing POSIX numeric and system builtins | T-157 | `int`, `rand`, `srand`, `system`, and any remaining required POSIX math builtins are covered by direct and compatibility tests | done |
| T-164 | P14 | P0 | Implement `getline`, the remaining builtin variables, and CLI or environment preassignment behavior | T-157 | `getline`, `ARGC`, `ARGV`, `ENVIRON`, `SUBSEP`, and string-valued `-v` behave as claimed and are covered by tests | done |
| T-165 | P14 | P0 | Close the remaining POSIX parser-continuation and runtime-sequencing gaps | T-158, T-159, T-164 | Reviewed multiline/parser cases, default-print expression-pattern mismatches, and cases like `END { print NR }` are fixed or reclassified precisely | done |
| T-166 | P14 | P1 | Re-audit the upstream manifest and promote corroborating POSIX cases | T-158, T-159, T-160, T-161, T-162, T-163, T-164, T-165 | Clean upstream cases are promoted for every major fixed POSIX family, and no stale skip reason remains after a semantic fix lands | done |
| T-167 | P14 | P0 | Complete the POSIX done-line audit | T-157, T-166 | `SPEC.md`, `POSIX.md`, the upstream manifest, and the required tests agree on the remaining in-scope POSIX surface with no untracked gaps | done |
| T-168 | P15 | P0 | Implement in-program `FS` / `RS` assignment for the current record surface | T-167 | Direct CLI tests and reviewed upstream `p.5` / `p.5a` style cases show runtime separator changes affect record and field splitting as in POSIX | done |
| T-169 | P15 | P1 | Re-audit and promote `FS`-sensitive upstream direct-file cases | T-168 | Clean `p.5`, `p.5a`, `p.35`, `p.36`, `p.48`, `p.50`, `p.51`, and `p.52` cases move to `run` or to narrower residual reasons | done |
| T-170 | P15 | P0 | Fix bare `length` POSIX semantics and re-expand the builtin claim | T-167 | Bare `length` behaves as `length($0)` and the reviewed `p.30` anchor becomes clean | done |
| T-171 | P15 | P0 | Fix remaining numeric comparison and expression-pattern mismatches | T-167 | `p.7`, `p.8`, `p.21a`, and `t.next` become clean or are narrowed to one smaller remaining operator family | done |
| T-172 | P15 | P0 | Fix the runtime-backed numeric-expression lowering gap | T-167 | The reviewed `getnr2tb` anchor becomes clean and no longer fails on `NR " " 10/NR` in compiled execution | done |
| T-173 | P15 | P0 | Eliminate reviewed reusable-backend crashes in field and record rebuild paths | T-167 | `p.29`, `p.32`, and `t.set0a` run clean without `lli` aborts | done |
| T-174 | P15 | P1 | Decide and implement the non-UTF-8 input policy | T-167 | Reviewed cases such as `t.NF` either run under a documented byte-oriented policy or are explicitly marked out-of-scope in the public contract | done |
| T-175 | P15 | P1 | Fix the remaining `split` target-variable mismatch and re-audit corroboration | T-167 | `splitvar` becomes clean or is replaced by a narrower classified skip backed by direct repo-owned tests | done |
| T-176 | P15 | P1 | Improve CLI-sensitive corroboration coverage | T-167 | `argarray` is either runnable with a clean adapter or superseded by an equivalent corroborating anchor for `ARGV` / multifile behavior | done |
| T-177 | P15 | P0 | Re-expand `SPEC.md` and complete the post-gap POSIX audit | T-169, T-170, T-171, T-172, T-173, T-174, T-175, T-176 | Public claims widen only for fixed families, unsuitable anchors such as `p.43`, `p.48b`, and `range1` remain explicit reviewed skips, and the docs plus manifest agree on the resulting surface | done |
| T-178 | P16 | P0 | Author the testing-surface rename and consolidation baseline | T-177 | `docs/history/testing-refactor.md`, `docs/testing.md`, and focused regression tests make the current marker names, command surfaces, and overlap explicit before implementation | done |
| T-179 | P16 | P0 | Rename pytest markers and default suite selection to positive, accurate names | T-178 | `core`, `compat_reference`, and `compat_corpus` replace the old marker names in `pyproject.toml`, tests, and command documentation without leaving stale references | done |
| T-180 | P16 | P0 | Update CI, contributor commands, and compatibility docs to the renamed testing surfaces | T-179 | `ci-fast`, the reference compatibility workflow, README, and testing/compatibility docs all use the new command vocabulary consistently | done |
| T-181 | P16 | P1 | Merge the overlapping local differential corpus pytest files into one surface | T-179 | The two near-identical local differential corpus pytest entrypoints are replaced by one shared `compat_corpus` differential surface with stable case selection | done |
| T-182 | P16 | P1 | Reclassify the `corpus` CLI and standardize the smoke entrypoint | T-180, T-181 | Docs present `corpus` as a manual harness tool, and release-smoke invocation is standardized to one documented command style | done |
| T-183 | P16 | P1 | Rebaseline testing docs and final workflow audit after the cleanup lands | T-180, T-181, T-182 | `docs/testing.md`, `docs/release-checklist.md`, and any remaining workflow references agree on the final testing surfaces with no stale old-marker wording | done |
| T-184 | P17 | P0 | Author the compatibility-tooling namespace baseline and import audit | T-183 | Tests and docs make the current flat compatibility module layout, wrapper script dependency, and target `quawk.compat` namespace explicit before implementation | done |
| T-185 | P17 | P0 | Create `quawk.compat` and move corpus/upstream modules into the dedicated namespace | T-184 | `corpus`, `upstream_compat`, `upstream_inventory`, `upstream_suite`, `upstream_divergence`, and `upstream_audit` live under `src/quawk/compat/` with no functional behavior change | done |
| T-186 | P17 | P0 | Replace `scripts/upstream_compat.py` with package-owned entrypoints | T-185 | The singleton wrapper is removed, a package-owned upstream bootstrap entrypoint exists, and the `corpus` command still resolves cleanly through the new namespace | done |
| T-187 | P17 | P1 | Update imports, tests, docs, and CI references to the new namespace and commands | T-185, T-186 | Internal imports, pytest modules, contributor docs, and CI bootstrap commands all use `quawk.compat` and the package-owned entrypoints consistently | done |
| T-188 | P17 | P1 | Rebaseline repo layout docs and final namespace audit after the refactor lands | T-187 | `docs/history/repo-refactor.md`, roadmap/docs, and focused compatibility-tooling regressions agree on the final layout, and no stale flat-module or wrapper-script references remain | done |
| T-189 | P18 | P0 | Author the remaining POSIX surface baseline and widening decision gate | T-188 | Tests and docs make the remaining claimed `$0` / `NF` rebuild gap, the `p.35` / `t.NF` corroboration targets, and the currently unclaimed broader POSIX expression families explicit before further implementation | done |
| T-190 | P18 | P0 | Fix the remaining claimed `$0` / `NF` rebuild mismatch | T-189 | Public execution no longer diverges on the reviewed `$0` reconstruction cases after `NF` or field mutation, and direct tests pin the corrected behavior | done |
| T-191 | P18 | P1 | Re-audit and promote the `p.35` / `t.NF` corroborating anchors | T-190 | The reviewed `p.35` / `t.NF` anchors move to `run` or are narrowed to smaller explicit non-product corroboration reasons after the behavior fix | done |
| T-192 | P18 | P0 | Decide and document whether to widen the broader unclaimed POSIX expression surface | T-191 | `SPEC.md`, `POSIX.md`, and the roadmap state clearly whether operators such as `||`, broader comparisons, arithmetic, ternary, match operators, and `in` remain intentionally unclaimed or are approved for the next implementation wave | done |
| T-193 | P18 | P1 | Author tests and claim updates for the next POSIX expression wave if widening is approved | T-192 | If widening is approved, failing tests and explicit `SPEC.md` target rows are checked in for the exact next operator/forms wave before implementation starts | blocked |
| T-194 | P18 | P0 | Implement the chosen broader POSIX expression and operator wave | T-193 | The approved next operator/forms wave executes correctly through the public path with parser, runtime, and JIT coverage | blocked |
| T-195 | P18 | P1 | Close backend/inspection parity and corroboration for newly claimed expression families | T-194 | Any newly claimed broader expression families support `--ir` / `--asm` as claimed and gain direct or upstream corroborating coverage where clean anchors exist | blocked |
| T-196 | P18 | P1 | Rebaseline the public POSIX contract after the remaining gap and any approved widening land | T-191, T-192, T-195 | `SPEC.md`, `POSIX.md`, `docs/compatibility.md`, and the roadmap agree on the resulting claimed POSIX surface with no stale implied debt | blocked |
| T-197 | P19 | P0 | Author the residual host-runtime boundary audit baseline and scope | T-192 | `docs/plans/host-runtime-boundary-audit.md`, `POSIX.md`, and the roadmap make the backend-first purpose, audit scope, and required outputs explicit before new implementation decisions start | done |
| T-198 | P19 | P0 | Inventory public routes to the Python host runtime and produce the residual host-only matrix | T-197 | A checked-in matrix identifies residual host-routed forms, their claimed status, backend/inspection status, and whether they are reachable from ordinary public execution | done |
| T-199 | P19 | P1 | Add focused routing regressions for representative residual host-routed forms | T-198 | Direct tests pin whether representative forms route to the backend, fall back to the host, or fail under `--ir` / `--asm` today | done |
| T-200 | P19 | P0 | Classify residual host-routed forms and identify accidental AOT debt | T-198, T-199 | Each residual host-routed form is marked as AOT debt, unclaimed but backend-ready, unclaimed and backend-incomplete, or host-only by design | done |
| T-201 | P19 | P0 | Decide public behavior for unclaimed host-routed programs | T-200 | The roadmap, `SPEC.md`, and `docs/design.md` state whether ordinary `quawk` keeps temporary host fallback for those forms or fails explicitly outside the AOT-backed contract | done |
| T-202 | P19 | P1 | Rebaseline the execution-model docs after the host-boundary audit | T-201 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the resulting host-runtime boundary and the ranked next follow-up wave | done |
| T-203 | P20 | P0 | Inventory the remaining claimed value-fallback cases | T-202 | A checked-in plan or matrix identifies every representative claimed public case that still depends on `requires_host_runtime_value_execution()` or equivalent host-assisted value semantics | done |
| T-204 | P20 | P1 | Add focused routing regressions for the claimed value-fallback cases | T-203 | Direct tests pin which claimed programs still rely on the host evaluator today and prove the behavioral requirement they preserve | done |
| T-205 | P20 | P0 | Close the backend/runtime value-semantics gaps for the claimed cases | T-204 | The backend/runtime path matches the claimed unset-value and coercion behavior for the inventoried cases | done |
| T-206 | P20 | P0 | Remove the remaining claimed public value fallback | T-205 | Ordinary public execution no longer routes claimed programs through the host evaluator for value semantics | done |
| T-207 | P20 | P1 | Rebaseline the execution-model docs after claimed fallback removal | T-206 | `SPEC.md`, `docs/design.md`, the roadmap, and focused regressions agree that the full claimed surface no longer uses public host fallback | done |
| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |
| T-209 | P21 | P0 | Implement backend/runtime support for logical-or | T-208 | Representative `||` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-210 | P21 | P0 | Implement backend/runtime support for broader comparisons | T-208 | Representative `<=`, `>`, `>=`, and `!=` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-211 | P21 | P1 | Close inspection parity, routing coverage, and corroboration for the widened logical-or and comparison surface | T-209, T-210 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P21` surface with no stale host-only gap | done |
| T-212 | P21 | P1 | Rebaseline the public contract after logical-or and comparison widening | T-211 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P21` claim with no implied host dependency | done |
| T-213 | P22 | P0 | Author the backend-only baseline, target claims, and direct tests for broader arithmetic | T-212 | Failing direct tests and explicit `SPEC.md` target rows define the exact `-`, `*`, `/`, `%`, and `^` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |
| T-214 | P22 | P0 | Implement backend/runtime support for subtraction, multiplication, and division | T-213 | Representative `-`, `*`, and `/` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-215 | P22 | P0 | Implement backend/runtime support for modulo and exponentiation | T-213 | Representative `%` and `^` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-216 | P22 | P1 | Close inspection parity, routing coverage, and corroboration for the widened arithmetic surface | T-214, T-215 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P22` surface with no stale host-only gap | done |
| T-217 | P22 | P1 | Rebaseline the public contract after arithmetic widening | T-216 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P22` claim with no implied host dependency | done |
| T-218 | P23 | P0 | Author the backend-only baseline, target claims, and direct tests for ternary expressions | T-217 | Failing direct tests and explicit `SPEC.md` target rows define the ternary forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |
| T-219 | P23 | P0 | Implement backend/runtime support for ternary expressions | T-218 | Representative ternary programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-220 | P23 | P1 | Close inspection parity, routing coverage, and corroboration for ternary | T-219 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover ternary with no stale host-only gap | done |
| T-221 | P23 | P1 | Rebaseline the public contract after ternary widening | T-220 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P23` claim with no implied host dependency | done |
| T-222 | P24 | P0 | Author the backend-only baseline, target claims, and direct tests for match operators and membership | T-221 | Failing direct tests and explicit `SPEC.md` target rows define the `~`, `!~`, and `in` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |
| T-223 | P24 | P0 | Implement backend/runtime support for match operators | T-222 | Representative `~` and `!~` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-224 | P24 | P0 | Implement backend/runtime support for membership tests | T-222 | Representative `in` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |
| T-225 | P24 | P1 | Close inspection parity, routing coverage, and corroboration for match operators and membership | T-223, T-224 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P24` surface with no stale host-only gap | done |
| T-226 | P24 | P1 | Rebaseline the public contract after match and membership widening | T-225 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P24` claim with no implied host dependency | done |
| T-080 | P3 | P0 | Author end-to-end tests for mixed `BEGIN` / record / `END` execution | T-079 | CLI tests exist for the mixed-program deliverable before implementation | done |
| T-081 | P3 | P0 | Extend token/span and AST support for `END` and multiple top-level items | T-080 | Frontend structures cleanly represent mixed-program execution | done |
| T-082 | P3 | P0 | Extend the parser for multiple pattern-actions and `END` | T-081, T-080 | The parser accepts the mixed-program deliverable | done |
| T-083 | P3 | P0 | Extend runtime sequencing for `BEGIN`, record actions, and `END` | T-082 | Execution order matches the supported mixed-program model | done |
| T-084 | P3 | P0 | Extend field handling beyond `$0` and `$1` for the supported subset | T-083 | The mixed-program deliverable can read `$2` and later fields correctly | done |
| T-085 | P3 | P0 | Extend LLVM lowering for mixed program execution | T-083, T-084 | The mixed-program deliverable executes through the LLVM-backed path | done |
| T-086 | P3 | P1 | Add integration tests for stdout/stderr/exit status of the mixed-program deliverable | T-085 | Integration tests run for the mixed-program deliverable in required CI jobs | done |
| T-087 | P4 | P0 | Author end-to-end tests for regex-driven record filtering | T-086 | CLI tests exist for `/foo/ { print $0 }` before implementation | done |
| T-088 | P4 | P0 | Define AST support for regex patterns in the supported subset | T-011, T-087 | Frontend structures cleanly represent regex-driven pattern actions | done |
| T-089 | P4 | P0 | Extend the parser for regex-driven pattern actions | T-088, T-087 | The parser accepts `/foo/ { print $0 }` | done |
| T-090 | P4 | P0 | Implement runtime regex matching for record filtering | T-089 | Regex patterns can select records in the supported subset | done |
| T-091 | P4 | P0 | Extend LLVM lowering for regex-driven filtering | T-090 | `/foo/ { print $0 }` executes through the LLVM-backed path | done |
| T-092 | P4 | P1 | Add integration tests for stdout/stderr/exit status of the regex-filter increment | T-091 | Integration tests run for the regex-filter increment in required CI jobs | done |
| T-101 | P4 | P0 | Author backend and CLI tests for reusable IR on record-driven programs | T-092 | Tests specify reusable `--ir` / `--asm` behavior for bare actions, mixed programs, and regex filters before the refactor lands | done |
| T-102 | P4 | P0 | Introduce a small C runtime support layer for streaming input and field access | T-101 | Runtime support owns record iteration, field splitting, output helpers, and regex matching behind a stable ABI | done |
| T-103 | P4 | P0 | Replace concrete-input lowering with reusable `BEGIN` / record / `END` program lowering | T-102 | Record-driven lowering emits reusable program IR rather than one module per concrete input stream | done |
| T-104 | P4 | P0 | Route public execution through the reusable program/runtime split | T-103 | Record-driven execution no longer depends on Python-side whole-input materialization or regex filtering | done |
| T-105 | P4 | P0 | Make `--ir` and `--asm` use reusable lowering for record-driven programs | T-103 | `--ir` and `--asm` succeed for supported record-driven programs without consuming or specializing to the input stream | done |
| T-106 | P4 | P1 | Add regression tests for bounded-memory record-driven execution shape | T-104, T-105 | Tests prove the public record-driven path no longer relies on whole-input collection before lowering | done |
| T-093 | P4 | P0 | Author end-to-end tests for broader expression support (`==` and `&&`) | T-106 | CLI tests exist for `BEGIN { print 1 == 1 }` and `BEGIN { print (1 < 2) && (2 < 3) }` before implementation | done |
| T-094 | P4 | P0 | Extend token/source-span modeling for `==`, `&&`, and parenthesized boolean expressions | T-093 | Token/span code cleanly supports equality, logical AND, and grouped boolean expressions | done |
| T-095 | P4 | P0 | Extend lexing for `==`, `&&`, and the current boolean-expression programs | T-094, T-093 | Lexer fixtures pass for `==`, `&&`, and parentheses in the planned expression-support programs | done |
| T-096 | P4 | P0 | Define AST nodes for equality and logical-AND expressions | T-094, T-093 | AST matches `BEGIN { print 1 == 1 }` and `BEGIN { print (1 < 2) && (2 < 3) }` | done |
| T-097 | P4 | P0 | Extend the parser for `==`, `&&`, and parenthesized boolean expressions | T-096, T-093 | The parser accepts the planned equality/logical-expression programs with stable precedence and grouping | done |
| T-098 | P4 | P0 | Extend runtime support for boolean results, equality, and logical AND | T-097, T-106 | Runtime executes `==` and `&&` correctly for the planned `BEGIN` programs on the reusable streaming backend | done |
| T-099 | P4 | P0 | Extend LLVM lowering for `==`, `&&`, and parenthesized boolean expressions | T-098 | `BEGIN { print 1 == 1 }` and `BEGIN { print (1 < 2) && (2 < 3) }` execute through the reusable LLVM-backed path | done |
| T-100 | P4 | P1 | Add integration tests for stdout/stderr/exit status of broader expression support | T-099 | Integration tests pass for the planned equality/logical-expression programs on the reusable runtime path | done |

| T-227 | P25 | P0 | Design slot allocation data structures for compile-time variable slots | T-226 | `VariableSlot` and `SlotAllocation` structs are defined and reviewed in `docs/performance-implementation.md` | done |
| T-228 | P25 | P0 | Implement slot allocation pass over normalized AST | T-227 | Pass produces `SlotAllocation` with variable slot indices | done |
| T-229 | P25 | P0 | Generate LLVM struct type for extended state | T-228 | `--ir` shows `%quawk.state` struct with variable slots | done |
| T-230 | P25 | P1 | Add runtime slot accessor functions in C | - | `qk_slot_get_number`, `qk_slot_set_number`, etc. compile and link | done |
| T-231 | P25 | P0 | Update lowering to use slot addresses for known variables | T-228, T-229 | Numeric variables use direct slot access in generated IR | done |
| T-232 | P25 | P1 | Preserve fallback to hash lookup for dynamic variables | T-231 | Dynamic/unknown variables still work via string-named hash | done |
| T-233 | P25 | P1 | Add tests for slot-based variable access | T-231 | Variable access tests pass with slot-based implementation | done |
| T-234 | P25 | P2 | Benchmark slot vs hash access performance | T-233 | Microbenchmarks show measurable improvement | done |
| T-235 | P26 | P0 | Define type lattice and join operation | - | `LatticeType` enum with `NUMERIC`, `STRING`, `MIXED`, `UNKNOWN` and join semantics | done |
| T-236 | P26 | P0 | Implement expression type inference | T-235 | Simple expressions (`1`, `"x"`, `x + 1`) infer correct types | done |
| T-237 | P26 | P0 | Implement variable type propagation | T-236 | Variables get consistent types across assignments | done |
| T-238 | P26 | P1 | Handle control flow conservatively in type inference | T-237 | Loops and conditionals don't lose type information incorrectly | done |
| T-239 | P26 | P1 | Add field access type (always mixed) | T-236 | Field expressions typed as `MIXED` | done |
| T-240 | P26 | P1 | Store type annotations in lowering state | T-237, T-238, T-239 | `LoweringState` has `type_info` member | done |
| T-241 | P26 | P2 | Add tests for type inference correctness | T-237, T-238 | All inference tests pass | done |
| T-242 | P27 | P0 | Implement numeric comparison fast path | T-25, P26-T02 | Direct `fcmp` instruction emitted for `numeric <op> numeric` | done |
| T-243 | P27 | P0 | Implement numeric arithmetic fast path | T-25, P26-T02 | Direct `fadd`/`fsub`/`fmul`/`fdiv` for numeric ops | done |
| T-244 | P27 | P1 | Implement string concat fast path | T-26 | Direct `qk_concat` call for string operands without coercion overhead | done |
| T-245 | P27 | P0 | Implement slot-based numeric variable read/write | P25, P26 | Direct `load`/`store` for slot-based numeric variables | done |
| T-246 | P27 | P1 | Implement slot-based string variable read/write | P25, P26 | Direct string slot access for known-string variables | done |
| T-247 | P27 | P1 | Add slow-path fallback for mixed-type operations | T-242 through T-246 | Mixed/unknown types use full AWK comparison semantics | done |
| T-248 | P27 | P2 | Add tests for specialized operations | T-242 through T-247 | Tests pass, `--ir` shows specialized fast paths | done |
| T-249 | P27 | P2 | Benchmark numeric loop performance improvement | T-248 | Measurable speedup over current implementation | done |
| T-250 | P28 | P0 | Add `--optimize` / `-O` CLI flag | - | Flag parses and enables optimization mode | done |
| T-251 | P28 | P0 | Implement `optimize_ir()` function with opt subprocess | - | Function invokes LLVM `opt` with pass pipeline | done |
| T-252 | P28 | P0 | Integrate optimization into execute path | T-251 | Programs run with `-O` show optimized IR | done |
| T-253 | P28 | P1 | Add `--ir=optimized` for inspection mode | T-251, T-250 | Shows optimized IR when requested | done |
| T-254 | P28 | P1 | Define pass pipeline for each optimization level | T-251 | Level 1 (basic) and level 2 (aggressive) pipelines documented | done |
| T-255 | P28 | P2 | Handle opt not found gracefully | T-251 | Warning emitted, fallback to unoptimized | done |
| T-256 | P28 | P2 | Add tests for optimization flag behavior | T-252 | Tests pass with optimization enabled | done |
| T-257 | P28 | P2 | Benchmark optimized vs unoptimized performance | T-256 | Numbers show benefit of optimization passes | done |
| T-258 | P29 | P1 | Profile current hot paths in runtime | - | Top 10 called functions identified with call counts | done |
| T-259 | P29 | P0 | Add slot storage arrays to runtime struct | P25 | `qk_runtime` has `numeric_slots`, `string_slots`, and `mixed_slots` arrays | done |
| T-260 | P29 | P0 | Add inline slot accessor functions | T-259 | `qk_slot_get_number_inline`, etc. defined in header | done |
| T-261 | P29 | P0 | Create slot-based runtime entry point | T-259 | `qk_runtime_create_with_slots()` available | done |
| T-262 | P29 | P1 | Add inline fast-path versions of hot functions | T-258, T-260 | Inline-able fast paths for top hot paths | done |
| T-263 | P29 | P1 | Update generated IR to use fast-path entry points | P27, T-262 | IR emits slot-based calls where applicable | done |
| T-264 | P29 | P2 | Benchmark fast-path improvements | T-263 | Measurable speedup in hot-path benchmarks | done |
| T-265 | P29 | P2 | Document ABI stability guarantees for runtime | T-260 | Runtime ABI documented for future stability | done |
| T-266 | P30 | P0 | Author execution-completeness baseline and representative gap tests | T-265 | Direct tests and a checked-in matrix pin the remaining grammar-valid backend gaps before implementation | done |
| T-267 | P30 | P0 | Widen runtime-backed user-defined function lowering and retire direct-function-only restrictions | T-266 | Imperative user-function bodies execute through the compiled backend/runtime path without relying on the narrow direct-function lane | done |
| T-268 | P30 | P0 | Add multi-subscript array read/write/delete lowering and runtime support | T-266 | Representative composite-subscript array programs execute correctly through public execution and inspection paths | done |
| T-269 | P30 | P1 | Lower side-effectful ternary expressions with correct short-circuit control flow | T-266 | Representative ternary programs with assignment, increment, and builtin side effects execute correctly and inspect cleanly | done |
| T-270 | P30 | P1 | Remove remaining grammar-valid builtin-call shape restrictions | T-266, T-268 | Representative dynamic-`printf` and related grammar-valid builtin forms execute through the compiled backend/runtime path | done |
| T-271 | P30 | P1 | Re-audit the grammar contract against backend execution and inspection support | T-267, T-268, T-269, T-270 | `docs/quawk.ebnf`, `design.md`, and the gap inventory agree that admitted forms execute end-to-end through the backend/runtime path | done |
| T-272 | P31 | P0 | Author the remaining product-side POSIX gap inventory and classification baseline | T-271 | `SPEC.md`, the roadmap, and a checked-in plan explicitly classify compound assignment, non-name array-target forms, broader substitution targets, extra builtin names, top-level item shapes, and the direct-function lane before implementation choices start | done |
| T-273 | P31 | P0 | Rebaseline the public contract for the remaining product-side gaps | T-272 | `SPEC.md`, `docs/design.md`, and the roadmap name the remaining product gaps explicitly instead of relying on vague “broader corners” wording | done |
| T-274 | P31 | P0 | Compound assignment end to end through public execution and inspection | T-272 | Representative `+=`, `-=`, `*=`, `/=`, `%=` and `^=` programs execute through the backend/runtime path and inspect cleanly | done |
| T-275 | P31 | P0 | Parenthesized array-target wrappers end to end through public execution and inspection | T-272 | Representative parenthesized `for ... in`, `expr in array`, and `split()` target wrapper programs execute through the backend/runtime path and inspect cleanly | done |
| T-276 | P31 | P0 | Close substitution-target lvalue gaps and classify builtin names | T-272, T-275 | Representative `sub()` / `gsub()` programs over scalar variables, fields, and multi-subscript array lvalues execute correctly, while builtin names beyond the current subset are documented as intentionally out of contract | done |
| T-277 | P31 | P1 | Retire or collapse the narrow direct-function execution lane | T-274, T-275, T-276 | Claimed function programs now use the reusable backend lowering path and the separate restricted direct-function route is retired | done |
| T-278 | P31 | P1 | Re-audit the remaining product-side admitted surface after the closure wave | T-274, T-275, T-276, T-277 | Contract docs, backend gap inventory, and direct tests agree that the only remaining product-side gaps are the explicit builtin-name and top-level-item exclusions | done |
| T-279 | P32 | P0 | Author the remaining POSIX corroboration-gap baseline | T-278 | `docs/compatibility.md`, `SPEC.md`, and focused tests explicitly list the remaining corroboration-only gaps for field rebuild, record-target `gsub`, and `rand()` | done |
| T-280 | P32 | P0 | Re-audit and resolve the field rebuild corroboration anchors | T-279 | The `p.35` / `t.NF` style anchors are promoted, reclassified, or documented with a precise reviewed reason | done |
| T-281 | P32 | P1 | Re-audit and resolve the record-target `gsub` reviewed skip | T-279 | The selected upstream `p.29` anchor is promoted, reclassified, or documented with a precise reviewed reason | done |
| T-282 | P32 | P1 | Resolve the `rand()` compatibility strategy | T-279 | `rand()` has either a stable corroborating anchor or a checked-in classified reference-disagreement policy | done |
| T-283 | P32 | P0 | Complete the final POSIX end-to-end compatibility audit | T-280, T-281, T-282 | `SPEC.md`, `docs/compatibility.md`, the upstream manifest, and the roadmap agree on the final implemented POSIX surface with no stale reviewed gaps | done |
| T-284 | P33 | P0 | Author the direct-path-removal baseline and representative routing regressions | T-283 | Focused tests and roadmap text make the remaining direct-lane entrypoints, stale guards, and representative over-gated programs explicit before implementation | done |
| T-285 | P33 | P0 | Remove the restricted direct lowering lane and dead direct-only helpers | T-284 | `lower_to_llvm_ir()` no longer emits the standalone direct-lowered `quawk_main()` fallback, and dead direct-function or record-loop helpers are removed or made unreachable by design | done |
| T-286 | P33 | P0 | Widen reusable-backend routing and remove stale pre-routing backend gates | T-285 | Programs already implemented by reusable lowering route through the backend/runtime path instead of failing behind `supports_runtime_backend_subset()` or `has_host_runtime_only_operations()` false negatives | done |
| T-287 | P33 | P1 | Remove stale direct-backend diagnostics and keep only genuine reusable-backend limits | T-286 | `jit.py` no longer raises misleading direct-backend limitation errors for supported public programs, and remaining runtime errors correspond to real reusable-backend gaps only | done |
| T-288 | P33 | P1 | Close execution and inspection parity for the representative over-gated programs | T-286, T-287 | Representative programs such as static field print in `BEGIN`, unary or increment-heavy `BEGIN` programs, scalar compound assignment, concatenation-driven conditions, and scalar array-read cases execute under ordinary `quawk` and succeed under `--ir` and `--asm` | done |
| T-289 | P33 | P1 | Rebaseline the execution-model docs after direct-path collapse | T-288 | `docs/design.md`, the roadmap, and any direct-path inventory notes agree that the reusable backend path is the only compiled execution route and no stale direct-lane wording remains | done |
| T-290 | P34 | P0 | Author the local-scalar promotion baseline and representative benchmark/IR anchors | T-289 | Focused roadmap notes and regressions make the remaining `%quawk.state` traffic in representative scalar kernels explicit before implementation choices start | done |
| T-291 | P34 | P0 | Implement conservative residency classification for backend-local numeric scalars | T-290 | Lowering can distinguish numeric scalars that must remain in `%quawk.state` from those whose lifetime stays local to one lowered function | done |
| T-292 | P34 | P1 | Lower the first supported subset of non-escaping numeric scalars through local storage | T-291 | Representative loops no longer read and write `%quawk.state` for promoted locals whose values do not escape the lowered function | done |
| T-293 | P34 | P1 | Make promoted-local lowering mem2reg-friendly for LLVM cleanup | T-292 | After `opt`, representative loops collapse to direct arithmetic/comparison-heavy IR with materially fewer redundant loads and stores | done |
| T-294 | P34 | P1 | Preserve AWK-visible runtime/state boundaries for promoted locals | T-292 | Escaping, mixed, string, field, array, builtin-coupled, and cross-phase values remain state-backed, and correctness regressions stay green | done |
| T-295 | P34 | P2 | Rebaseline optimized-vs-unoptimized benchmarks and docs for local-scalar promotion | T-293, T-294 | The optimized-vs-unoptimized suite is rerun against the post-`T-294` lowering, and roadmap/benchmark docs record the current `lli_only` outcome honestly, including when the suite-level geometric mean remains flat | done |
| T-296 | P35 | P0 | Author the agent-workflow documentation alignment plan | T-295 | `docs/plans/agent-workflow-doc-alignment-plan.md` records the missing guidance, desired steady state, cleanup phases, validation direction, and acceptance criteria before docs are rewritten | done |
| T-297 | P35 | P0 | Resolve the agent workflow document path | T-296 | README and contributor guidance point to the actual agent workflow document, or a deliberate `docs/agent-workflow.md` shim exists and points to `AGENTS.md` | done |
| T-298 | P35 | P0 | Expand `AGENTS.md` setup, validation, testing, and compatibility guidance | T-296, T-297 | `AGENTS.md` covers LLVM prerequisites, editable dev install, submodules, upstream bootstrap, static validation commands, marker-based suites, corpus/test selection, `xfail`, pinned references, and divergence classification | done |
| T-299 | P35 | P1 | Add architecture, doc-update, changelog, and git-safety guardrails to `AGENTS.md` | T-298 | `AGENTS.md` summarizes compiled-backend execution constraints, maps change types to the right docs, calls out changelog expectations for user-visible changes, and prevents accidental staging of unrelated dirty-worktree changes | done |
| T-300 | P35 | P1 | Clean touched workflow docs for relative links and stale guidance | T-297, T-299 | Docs touched by the alignment avoid new absolute local filesystem links, stale `docs/agent-workflow.md` references are gone or intentional, and workflow guidance no longer conflicts across README, contributing docs, `AGENTS.md`, and testing docs | done |
| T-301 | P35 | P2 | Validate and close the agent workflow documentation alignment | T-300 | Relevant documentation checks pass or skipped checks are explained, and the roadmap marks `P35` complete only after `AGENTS.md` and linked workflow docs agree on setup, validation, compatibility, architecture, and doc-update expectations | done |
| T-302 | P36 | P0 | Author the implementation readability refactor plan | T-301 | `docs/plans/implementation-readability-refactor-plan.md` records the hotspots, proposed refactor phases, guardrails, validation commands, and definition of done before code moves begin | done |
| T-303 | P36 | P0 | Add a source-level implementation map | T-302 | `src/quawk/README.md` or an equivalent source map explains the implementation pipeline, package layout, major modules, and current refactor direction for new readers | done |
| T-304 | P36 | P0 | Extract AST definitions and formatting out of `parser.py` | T-303 | AST dataclasses/enums live in a focused module, AST formatting lives separately, parser imports are updated, and parser/golden/conformance tests pass | done |
| T-305 | P36 | P0 | Introduce shared AST traversal helpers for analysis passes | T-304 | At least two existing passes use shared traversal helpers for expressions, statements, lvalues, patterns, or programs without behavior changes | done |
| T-306 | P36 | P0 | Split backend orchestration, driver IR, runtime ABI, and lowering state out of `jit.py` | T-305 | LLVM tool/link orchestration, generated driver IR, runtime declarations, and lowering context/state each have focused ownership outside the monolithic backend file | done |
| T-307 | P36 | P1 | Add a small LLVM IR builder and migrate representative lowering paths | T-306 | Common call/load/store/branch/binop/select/GEP emission goes through a lightweight helper in representative statement and expression lowering code | done |
| T-308 | P36 | P1 | Split statement, expression, lvalue, and builtin lowering into focused backend modules | T-307 | Backend lowering modules have clear ownership and `jit.py` is reduced to a thin compatibility/public API facade or removed from the hot path | todo |
| T-309 | P36 | P1 | Split or explicitly defer splitting the C runtime source | T-308 | `qk_runtime.c` is split by runtime domain with build support, or a checked-in reviewed decision explains why the split should wait | todo |
| T-310 | P36 | P2 | Improve test discoverability for newly touched refactor coverage | T-304, T-308 | Newly touched tests prefer behavior-oriented module names or comments that preserve task traceability without requiring task-ID knowledge | todo |
| T-311 | P36 | P2 | Validate and close the implementation readability refactor | T-309, T-310 | Focused parser/backend/runtime checks and `uv run pytest -q -m core` pass, and the roadmap records the final readability-refactor closeout state | todo |

## Cross-Cutting Tracks

- documentation maintenance
- CI coverage and quality gates
- risk tracking and decision log updates
- phase TDD discipline

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AWK semantic corner-case drift | High | Differential tests and explicit divergence classification |
| LLVM toolchain integration complexity | High | Keep backend abstraction narrow and preserve a simple end-to-end execution path |
| Over-scoped early milestones | High | Force work into a working end-to-end path before broad feature coverage |
| Scope creep from extensions | Medium | POSIX-first gate and defer extensions until compatibility baseline |
| Python dependency drift | Medium | Pin dependency ranges and enforce CI |

## Maintenance Rules

- any accepted scope change must update both the roadmap text and the backlog in the same change
- new tasks must include phase, dependencies, and acceptance criteria
- completed tasks should reference the implementing commit or PR in follow-up notes
- phase implementation tasks should not move to `in_progress` until that phase's test-baseline task is `done`
