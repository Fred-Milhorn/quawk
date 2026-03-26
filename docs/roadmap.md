# Roadmap

This document is the phased implementation roadmap and active backlog for `quawk`.

## Planning Assumptions

- language target is POSIX-oriented AWK first
- implementation language is Python `3.14.x`
- developer workflow baseline is `uv` managing Python `3.14.x` and the project `.venv`
- current LLVM-backed execution uses local LLVM tools (`lli`)
- the next backend refactor replaces input-specialized lowering with a reusable AOT-oriented program/runtime split
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
| P10 | Compatibility and Hardening | Differential compatibility gates and regression control |
| P11 | Pre-Release Readiness | Documentation completion, release checklist, and polish |

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
- create `src/`, `tests/`, `examples/`, and `scripts/`
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
- diagnostics and recovery improvements follow the related execution support rather than leading it

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
- the first builtin tranche needed for the active P6 deliverable
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

### P10: Compatibility and Hardening

Objective:
- maximize POSIX compatibility and reduce behavioral gaps after feature completion is already in place

In scope:
- differential runner against `one-true-awk` and `gawk --posix`
- divergence classification workflow
- parser/runtime/regex/io compatibility corpus expansion
- regression triage and targeted fixes

Success in this phase looks like:
- supported parser, semantic, and runtime fixtures run through stable compatibility infrastructure instead of only ad hoc local checks
- parser diagnostics can report more than one error where recovery is expected, and the reviewed AST snapshot surfaces are pinned by deterministic golden coverage
- semantic diagnostics have stable public error codes in addition to source spans and human-readable messages
- differential runs against `quawk`, `one-true-awk`, and `gawk --posix` produce normalized comparable results for the supported corpus
- every observed compatibility gap in the compatibility corpus is either fixed or explicitly classified in a checked-in divergence manifest

Exit criteria:
- parser multi-error fixtures and selected AST golden fixtures are stable and reviewed
- semantic errors emit stable public codes without losing source-span precision
- differential runner executes the supported compatibility corpus across `quawk`, `one-true-awk`, and `gawk --posix`
- no failing required compatibility tests remain in the active hardening test set
- known divergences are documented, tagged, and classified in the checked-in manifest
- hardening pass closes or explicitly triages all high-severity regressions discovered during the phase

### P11: Pre-Release Readiness

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

## Immediate Next Tasks

Start here unless priorities change:

Next deliverable: P10 compatibility and hardening

Target outcome:
- compatibility infrastructure is ready to measure parser, semantic, and runtime gaps against other AWK implementations

1. `T-023` define semantic error code catalog after core execution behavior stabilizes
2. `T-015` add parser error recovery at statement boundaries
3. `T-016` add parser golden tests for AST snapshots where they improve reviewability
4. `T-047` author compatibility tests as `xfail` baseline for the supported subset
5. `T-035` implement differential test runner (`ota`, `gawk --posix`, `quawk`)
6. `T-036` seed compatibility corpus for supported parser/runtime behaviors
7. `T-037` add divergence manifest and classification workflow

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
| T-001 | P0 | P0 | Create `src/`, `tests/`, `examples/`, and `scripts/` directories | none | Directories exist and are documented | done |
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
| T-015 | P10 | P2 | Add parser error recovery at statement boundaries | T-013 | Multi-error fixture tests produce stable error counts | todo |
| T-016 | P10 | P2 | Add parser golden tests for AST snapshots where they improve reviewability | T-012, T-014 | Golden outputs are deterministic and useful | todo |
| T-017 | P4 | P1 | Add parser conformance fixtures mapped to supported grammar sections | T-092, T-100 | Coverage matrix shows supported grammar areas | done |
| T-044 | P5 | P1 | Author semantic tests for the first user-defined function behavior | T-017 | Tests exist for the initial function-call path and its first legality checks before implementation | done |
| T-018 | P5 | P1 | Build symbol table/scoping support when variables or functions require it | T-012, T-044 | Scope tests pass for supported constructs | done |
| T-019 | P5 | P1 | Implement semantic checks for lvalues and assignment legality as needed | T-018 | Invalid assignment tests fail with expected diagnostics | done |
| T-020 | P5 | P1 | Implement control-flow legality checks when loops/functions land | T-018 | `break`/`continue`/`return` legality tests pass for supported constructs | done |
| T-021 | P5 | P2 | Implement function declaration/definition checks when functions land | T-018 | Duplicate/conflicting definitions handled deterministically | done |
| T-022 | P6 | P1 | Add normalization only where backend support needs it | T-019, T-020, T-021 | Lowering consumes stable normalized forms for supported behavior | done |
| T-023 | P10 | P2 | Define semantic error code catalog after core execution behavior stabilizes | T-019, T-020, T-021 | Errors emitted with stable code and source span | todo |
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
| T-039 | P11 | P1 | Expand CLI behavior only as execution support justifies it | T-026 | Help/version/run-path behavior is stable for supported features | todo |
| T-047 | P10 | P0 | Author compatibility tests as `xfail` baseline for the supported subset | T-028 | Compatibility baseline committed with expected failures | todo |
| T-035 | P10 | P0 | Implement differential test runner (`ota`, `gawk --posix`, `quawk`) | T-028, T-047 | Runner emits comparable normalized outputs | todo |
| T-036 | P10 | P0 | Seed compatibility corpus for supported parser/runtime behaviors | T-035 | Core corpus executes and reports per-case status | todo |
| T-037 | P10 | P1 | Add divergence manifest and classification workflow | T-035 | Divergences tracked with explicit categories | todo |
| T-048 | P11 | P0 | Author release-readiness smoke tests as `xfail` baseline | T-036, T-037 | Release-readiness baseline committed with expected failures | todo |
| T-040 | P11 | P1 | Add `SPEC.md` feature matrix (implemented/planned/out-of-scope) | T-036 | Feature matrix aligns with tests and docs | todo |
| T-042 | P11 | P1 | Finalize release checklist and changelog workflow | T-039, T-040 | Checklist is complete and versioned | todo |
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
