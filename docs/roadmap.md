# Roadmap

This document is the phased implementation roadmap and active backlog for `quawk`.

## Planning Assumptions

- language target is POSIX-oriented AWK first
- implementation language is Python `3.14.x`
- developer workflow baseline is `uv` managing Python `3.14.x` and the project `.venv`
- current LLVM-backed execution uses local LLVM tools (`lli`)
- reference behavior is checked against `one-true-awk` and `gawk --posix`
- implementation grows from an initial end-to-end JIT path
- phase delivery uses TDD for the next capability increment
- `pytest` is the default test framework

## Phase Overview

| Phase | Name | Primary Outcome |
|---|---|---|
| P0 | Python Bootstrap and Tooling | Package skeleton, env bootstrap, CI basics |
| P1 | End-to-End MVP Path | First runnable `quawk` JIT path for the simplest AWK program |
| P2 | Incremental Language Expansion | Grow supported AWK behavior from the initial `P1` path |
| P3 | Compatibility and Hardening | Differential compatibility gates and regression control |
| P4 | Pre-Release Readiness | Documentation completion, release checklist, and polish |

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
- add CI-ready baseline checks

Exit criteria:
- bootstrap flow works from a clean checkout
- CI required jobs pass on default branch target platforms

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

### P2: Incremental Language Expansion

Objective:
- expand the supported AWK subset one runnable capability increment at a time

In scope:
- each increment must name the exact AWK behavior it delivers, plus example programs that should execute at phase completion
- each increment should have lex, parse, lowering/runtime, and integration-test work scoped to that behavior
- semantic checks land only when the increment requires them
- diagnostics and recovery improvements follow the related execution support rather than leading it

Exit criteria:
- each newly claimed language feature has an executable implementation
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
5. Functions and broader POSIX-oriented coverage
   Target programs:
   - `function f(x) { return x + 1 } BEGIN { print f(2) }`

### P3: Compatibility and Hardening

Objective:
- maximize POSIX compatibility and reduce behavioral gaps

In scope:
- differential runner against `one-true-awk` and `gawk --posix`
- divergence classification workflow
- parser/runtime/regex/io compatibility corpus expansion
- regression triage and targeted fixes

Exit criteria:
- no failing `posix-required` tests in the release test set
- known divergences are documented and tagged
- hardening pass shows no high-severity regressions

### P4: Pre-Release Readiness

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

Next capability increment: comparisons and control flow over the supported subset

Target programs:
- `BEGIN { if (1 < 2) print 3 }`
- `BEGIN { x = 0; while (x < 3) { print x; x = x + 1 } }`

1. `T-073` extend token/source-span modeling for comparison and control-flow syntax
2. `T-074` extend lexing for `<`, parentheses, and the active control-flow keywords
3. `T-075` define AST nodes for comparisons, blocks, `if`, and `while`
4. `T-076` extend the parser for comparison expressions and control-flow statements
5. `T-077` extend runtime state for branching and loop execution
6. `T-078` extend LLVM lowering for comparisons and control flow
7. `T-079` add integration tests for stdout/stderr/exit status of the control-flow increment

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
| T-007 | P0 | P1 | Add CI workflow for format/lint/type/test checks | T-002 | CI blocks merges on required failures | done |
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
| T-011 | P2 | P1 | Implement `REGEX` vs `/` context-sensitive lexing when regex support becomes active | T-010 | Dedicated ambiguity tests pass when regex literals are in scope | todo |
| T-012 | P2 | P0 | Define AST nodes for numeric literals and additive binary expressions | T-009, T-054, T-055 | AST matches the numeric-print increment | done |
| T-013 | P2 | P0 | Extend the parser for `print` expressions in `BEGIN` | T-012, T-054, T-055 | The parser accepts `BEGIN { print 1 }` and the additive form | done |
| T-014 | P2 | P1 | Implement additive precedence for the numeric-print increment | T-013 | `1 + 2 + 3` parses and executes with stable precedence behavior | done |
| T-015 | P2 | P2 | Add parser error recovery at statement boundaries | T-013 | Multi-error fixture tests produce stable error counts | todo |
| T-016 | P2 | P2 | Add parser golden tests for AST snapshots where they improve reviewability | T-012, T-014 | Golden outputs are deterministic and useful | todo |
| T-017 | P2 | P1 | Add parser conformance fixtures mapped to supported grammar sections | T-013, T-014 | Coverage matrix shows supported grammar areas | todo |
| T-044 | P2 | P1 | Author tests for semantic checks needed by the next capability increment | T-017 | Semantic tests are committed before the related feature work | todo |
| T-018 | P2 | P1 | Build symbol table/scoping support when variables or functions require it | T-012, T-044 | Scope tests pass for supported constructs | todo |
| T-019 | P2 | P1 | Implement semantic checks for lvalues and assignment legality as needed | T-018 | Invalid assignment tests fail with expected diagnostics | todo |
| T-020 | P2 | P1 | Implement control-flow legality checks when loops/functions land | T-018 | `break`/`continue`/`return` legality tests pass for supported constructs | todo |
| T-021 | P2 | P2 | Implement function declaration/definition checks when functions land | T-018 | Duplicate/conflicting definitions handled deterministically | todo |
| T-022 | P2 | P1 | Add normalization only where backend support needs it | T-019, T-020, T-021 | Lowering consumes stable normalized forms for supported behavior | todo |
| T-023 | P2 | P2 | Define semantic error code catalog after core execution behavior stabilizes | T-019, T-020, T-021 | Errors emitted with stable code and source span | todo |
| T-024 | P2 | P0 | Extend the runtime value model for numeric values in the current increment | T-014 | Runtime representation supports numeric literals and additive results | done |
| T-025 | P2 | P0 | Extend lowering from supported AST forms to LLVM IR for numeric print | T-024 | `BEGIN { print 1 }` and `BEGIN { print 1 + 2 }` execute through the LLVM-backed path | done |
| T-026 | P2 | P0 | Implement runtime input loop (`BEGIN`, records, `END`) when record processing becomes active | T-024, T-025 | Record-processing fixtures pass for the supported subset | todo |
| T-027 | P2 | P1 | Implement builtins only as required by the active capability increment or compatibility goals | T-024, T-026 | Builtin fixture tests pass for the selected subset | todo |
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
| T-073 | P2 | P0 | Extend token/source-span modeling for comparison and control-flow syntax | T-071 | Token/span code cleanly supports the control-flow increment | todo |
| T-074 | P2 | P0 | Extend lexing for `<`, parentheses, and the active control-flow keywords | T-073, T-072 | Lexer fixtures pass for the control-flow increment | todo |
| T-075 | P2 | P0 | Define AST nodes for comparisons, blocks, `if`, and `while` | T-073, T-072 | AST matches the control-flow increment | todo |
| T-076 | P2 | P0 | Extend the parser for comparison expressions and control-flow statements | T-075, T-072 | The parser accepts the planned `if` and `while` examples | todo |
| T-077 | P2 | P0 | Extend runtime state for branching and loop execution | T-076 | Runtime can execute the supported control-flow constructs | todo |
| T-078 | P2 | P0 | Extend LLVM lowering for comparisons and control flow | T-077 | The supported control-flow examples execute through the LLVM-backed path | todo |
| T-079 | P2 | P1 | Add integration tests for stdout/stderr/exit status of the control-flow increment | T-078 | Integration tests run for the control-flow increment in required CI jobs | todo |
| T-039 | P2 | P1 | Expand CLI behavior only as execution support justifies it | T-026 | Help/version/run-path behavior is stable for supported features | todo |
| T-047 | P3 | P0 | Author compatibility tests as `xfail` baseline for the supported subset | T-028 | Compatibility baseline committed with expected failures | todo |
| T-035 | P3 | P0 | Implement differential test runner (`ota`, `gawk --posix`, `quawk`) | T-028, T-047 | Runner emits comparable normalized outputs | todo |
| T-036 | P3 | P0 | Seed compatibility corpus for supported parser/runtime behaviors | T-035 | Core corpus executes and reports per-case status | todo |
| T-037 | P3 | P1 | Add divergence manifest and classification workflow | T-035 | Divergences tracked with explicit categories | todo |
| T-038 | P3 | P1 | Establish CI release gate for `posix-required` tests | T-036, T-037 | CI fails on disallowed status transitions | todo |
| T-048 | P4 | P0 | Author release-readiness smoke tests as `xfail` baseline | T-038 | Release-readiness baseline committed with expected failures | todo |
| T-040 | P4 | P1 | Add `SPEC.md` feature matrix (implemented/planned/out-of-scope) | T-036 | Feature matrix aligns with tests and docs | todo |
| T-042 | P4 | P1 | Finalize release checklist and changelog workflow | T-039, T-040 | Checklist is complete and versioned | todo |

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
