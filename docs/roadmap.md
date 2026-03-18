# Roadmap

This document is the phased implementation roadmap and active backlog for `quawk`.

## Planning Assumptions

- language target is POSIX-oriented AWK first
- implementation language is Python `3.14.x`
- developer workflow baseline is `uv` managing Python `3.14.x` and the project `.venv`
- LLVM-backed JIT uses `llvmlite`
- reference behavior is checked against `one-true-awk` and `gawk --posix`
- implementation grows by executable vertical slices
- phase delivery uses TDD for the next supported slice
- `pytest` is the default test framework

## Phase Overview

| Phase | Name | Primary Outcome |
|---|---|---|
| P0 | Python Bootstrap and Tooling | Package skeleton, env bootstrap, CI basics |
| P1 | Minimal Vertical Slice | First runnable `quawk` path for a tiny AWK subset |
| P2 | Incremental Language Expansion | Grow supported AWK behavior slice by slice |
| P3 | Compatibility and Hardening | Differential compatibility gates and regression control |
| P4 | Pre-Release Readiness | Documentation completion, release checklist, and polish |

## Phase Entry and Exit Rules

Entry gate for every phase:

1. author tests for the next supported slice in phase scope
2. check in those tests before or alongside implementation
3. use `xfail` only where it makes the temporary expected failure clearer
4. start implementation only after the slice is concretely specified in tests

Phase completion rule:
- a phase should not close while its claimed slice still lacks real test coverage
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

### P1: Minimal Vertical Slice

Objective:
- execute a tiny but real AWK program through the full pipeline

In scope:
- inline program text and `-f` file input
- minimal lexer and parser support for `BEGIN { print "literal" }`
- LLVM lowering and runtime path sufficient for that slice
- stable stdout, exit status, and basic CLI invocation

Exit criteria:
- `quawk 'BEGIN { print "hello" }'` executes correctly
- the same program executes from `-f`
- unsupported syntax fails cleanly without pretending broader support exists

### P2: Incremental Language Expansion

Objective:
- expand the supported AWK subset one coherent feature slice at a time

In scope:
- tokens, expressions, statements, and runtime behavior needed for the next slice
- semantic checks only when a new slice requires them
- records, fields, pattern-action execution, control flow, and functions in staged increments
- diagnostics and recovery improvements after the related execution path exists

Exit criteria:
- each newly claimed language feature has an executable implementation
- earlier working slices stay green as coverage expands
- the supported subset is always explicit in tests and docs

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

1. `T-043` write P1 vertical-slice tests as the initial `xfail` baseline
2. `T-049` implement minimal lexer support for `BEGIN`, `print`, braces, and string literals
3. `T-050` implement minimal parser support for `BEGIN { print "literal" }`
4. `T-051` implement LLVM lowering/runtime for literal-print `BEGIN` programs
5. `T-052` wire CLI execution for inline program text and `-f` files
6. `T-053` add end-to-end execution tests for the initial supported slice
7. `T-009` extend token/source-span modeling for the next supported slice
8. `T-010` extend lexing for the next supported slice

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
| T-000 | P0 | P0 | Rebaseline docs to Python/llvmlite implementation plan | none | Core docs reflect Python 3.14 + `uv` workflow | done |
| T-001 | P0 | P0 | Create `src/`, `tests/`, `examples/`, and `scripts/` directories | none | Directories exist and are documented | done |
| T-002 | P0 | P0 | Add `pyproject.toml` with package metadata and console entrypoint | T-001 | `quawk --help` entrypoint resolves in the local `.venv` | done |
| T-003 | P0 | P0 | Add initial `src/quawk/__init__.py` and `src/quawk/cli.py` placeholders | T-002 | Placeholder package imports cleanly | done |
| T-004 | P0 | P1 | Add `uv` bootstrap instructions for Python `3.14.x` and the project `.venv` | none | Clean checkout setup succeeds with documented `uv` commands | done |
| T-005 | P0 | P1 | Add `uv`-based contributor command shortcuts or workflow notes | T-004 | Common contributor commands run cleanly from the documented `uv` environment | done |
| T-006 | P0 | P0 | Keep testing workflow centered on pytest rather than custom gate tooling | none | Repo workflow is described without a second metadata/checking system | done |
| T-007 | P0 | P1 | Add CI workflow for format/lint/type/test checks | T-002 | CI blocks merges on required failures | done |
| T-008 | P0 | P1 | Add `CONTRIBUTING.md` workflow and review expectations | none | README links contributing guide and guide is coherent | done |
| T-043 | P1 | P0 | Author P1 vertical-slice tests for the initial executable slice | T-002, T-006 | Minimal end-to-end execution tests are committed before implementation | todo |
| T-049 | P1 | P0 | Implement minimal lexer support for `BEGIN`, `print`, braces, and string literals | T-043 | Initial slice tokenization is stable and tested | todo |
| T-050 | P1 | P0 | Implement minimal parser for `BEGIN { print "literal" }` | T-049 | Initial slice parses into a stable AST form | todo |
| T-051 | P1 | P0 | Implement lowering/runtime for literal-print `BEGIN` programs | T-050 | Minimal slice executes through the JIT path | todo |
| T-052 | P1 | P0 | Wire CLI execution for inline programs and `-f` files | T-051 | Minimal slice runs from both invocation forms | todo |
| T-053 | P1 | P0 | Add end-to-end tests for stdout and exit status of the initial slice | T-052 | Inline and file-based smoke cases pass end-to-end | todo |
| T-009 | P2 | P0 | Extend token types and source-span representation for the next supported slice | T-053 | Token/span modules support the next planned language increment | todo |
| T-010 | P2 | P0 | Extend lexing with separators and operators needed for the next slice | T-009 | Lexer fixtures pass for the next targeted syntax slice | todo |
| T-011 | P2 | P1 | Implement `REGEX` vs `/` context-sensitive lexing when regex support becomes active | T-010 | Dedicated ambiguity tests pass when regex literals are in scope | todo |
| T-012 | P2 | P0 | Define and extend AST nodes only as needed for the next supported slice | T-009 | AST model matches currently supported language forms | todo |
| T-013 | P2 | P0 | Extend parser for additional top-level items and statements | T-012 | Parser accepts the next planned runnable slice | todo |
| T-014 | P2 | P1 | Implement expression parsing with precedence and implicit concatenation | T-013 | Precedence and concat tests pass when that slice is enabled | todo |
| T-015 | P2 | P2 | Add parser error recovery at statement boundaries | T-013 | Multi-error fixture tests produce stable error counts | todo |
| T-016 | P2 | P2 | Add parser golden tests for AST snapshots where they improve reviewability | T-012, T-014 | Golden outputs are deterministic and useful | todo |
| T-017 | P2 | P1 | Add parser conformance fixtures mapped to supported grammar sections | T-013, T-014 | Coverage matrix shows supported grammar areas | todo |
| T-044 | P2 | P1 | Author tests for semantic checks needed by the next supported slice | T-017 | Semantic tests are committed before the related feature work | todo |
| T-018 | P2 | P1 | Build symbol table/scoping support when variables or functions require it | T-012, T-044 | Scope tests pass for supported constructs | todo |
| T-019 | P2 | P1 | Implement semantic checks for lvalues and assignment legality as needed | T-018 | Invalid assignment tests fail with expected diagnostics | todo |
| T-020 | P2 | P1 | Implement control-flow legality checks when loops/functions land | T-018 | `break`/`continue`/`return` legality tests pass for supported constructs | todo |
| T-021 | P2 | P2 | Implement function declaration/definition checks when functions land | T-018 | Duplicate/conflicting definitions handled deterministically | todo |
| T-022 | P2 | P1 | Add normalization only where backend support needs it | T-019, T-020, T-021 | Lowering consumes stable normalized forms for supported slices | todo |
| T-023 | P2 | P2 | Define semantic error code catalog after core execution slices stabilize | T-019, T-020, T-021 | Errors emitted with stable code and source span | todo |
| T-024 | P2 | P0 | Extend runtime value model for newly supported AWK semantics | T-022 | Runtime representation matches supported behavior | todo |
| T-025 | P2 | P0 | Extend lowering from supported IR/AST forms to LLVM IR via `llvmlite` | T-022 | New sample programs execute through JIT path | todo |
| T-026 | P2 | P0 | Implement runtime input loop (`BEGIN`, records, `END`) when record processing becomes active | T-024, T-025 | Record-processing fixtures pass for the supported subset | todo |
| T-027 | P2 | P1 | Implement builtins only as required by the active slice or compatibility goals | T-024, T-026 | Builtin fixture tests pass for the selected subset | todo |
| T-028 | P2 | P1 | Add integration tests for stdout/stderr/exit status across supported slices | T-025, T-026 | Integration tests run in required CI jobs | todo |
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
| LLVM binding feature limits (`llvmlite`) | High | Keep backend abstraction narrow; add fallback only if blocked |
| Over-scoped early milestones | High | Force work into small runnable slices before broad feature coverage |
| Scope creep from extensions | Medium | POSIX-first gate and defer extensions until compatibility baseline |
| Python dependency drift | Medium | Pin dependency ranges and enforce CI |

## Maintenance Rules

- any accepted scope change must update both the roadmap text and the backlog in the same change
- new tasks must include phase, dependencies, and acceptance criteria
- completed tasks should reference the implementing commit or PR in follow-up notes
- phase implementation tasks should not move to `in_progress` until that phase's `xfail` baseline task is `done`
