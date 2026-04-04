# Roadmap

This document is the phased implementation roadmap and active backlog for `quawk`.

## Planning Assumptions

- language target is POSIX-oriented AWK first
- implementation language is Python `3.14.x`
- developer workflow baseline is `uv` managing Python `3.14.x` and the project `.venv`
- current LLVM-backed execution uses local LLVM tools (`lli`)
- remaining execution-model work closes the last claimed backend gaps and removes the last Python-side semantic fallback as part of the same implementation wave, so the reusable AOT-oriented program/runtime split is the only public execution path
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
- implementation details for this phase live in [testing-refactor.md](../testing-refactor.md)

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

## Immediate Next Tasks

Start here unless priorities change:

Next deliverable: P16 testing surface cleanup

Target outcome:
- the next work replaces confusing test-surface names, consolidates overlapping
  local compatibility entrypoints, and makes docs plus CI agree on one testing
  workflow vocabulary

`P15` closeout is complete. The next planned cleanup is the testing-surface
refactor tracked in `P16`.

Immediate next tasks:
- `T-182` reclassify the `corpus` CLI and standardize the smoke entrypoint
- `T-183` rebaseline testing docs and final workflow audit after the cleanup
  lands

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
| T-178 | P16 | P0 | Author the testing-surface rename and consolidation baseline | T-177 | `testing-refactor.md`, `docs/testing.md`, and focused regression tests make the current marker names, command surfaces, and overlap explicit before implementation | todo |
| T-179 | P16 | P0 | Rename pytest markers and default suite selection to positive, accurate names | T-178 | `core`, `compat_reference`, and `compat_corpus` replace the old marker names in `pyproject.toml`, tests, and command documentation without leaving stale references | done |
| T-180 | P16 | P0 | Update CI, contributor commands, and compatibility docs to the renamed testing surfaces | T-179 | `ci-fast`, the reference compatibility workflow, README, and testing/compatibility docs all use the new command vocabulary consistently | done |
| T-181 | P16 | P1 | Merge the overlapping local differential corpus pytest files into one surface | T-179 | The two near-identical local differential corpus pytest entrypoints are replaced by one shared `compat_corpus` differential surface with stable case selection | done |
| T-182 | P16 | P1 | Reclassify the `corpus` CLI and standardize the smoke entrypoint | T-180, T-181 | Docs present `corpus` as a manual harness tool, and release-smoke invocation is standardized to one documented command style | todo |
| T-183 | P16 | P1 | Rebaseline testing docs and final workflow audit after the cleanup lands | T-180, T-181, T-182 | `docs/testing.md`, `docs/release-checklist.md`, and any remaining workflow references agree on the final testing surfaces with no stale old-marker wording | todo |
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
