# Roadmap

This document is the phased implementation roadmap and active backlog for `quawk`.

## Planning Assumptions

- language target is POSIX-oriented AWK first
- implementation language is Python `3.14.x`
- developer workflow baseline is `uv` managing Python `3.14.x` and the project `.venv`
- LLVM-backed JIT uses `llvmlite`
- reference behavior is checked against `one-true-awk` and `gawk --posix`
- phase delivery uses TDD with `xfail` baselines
- `pytest` is the default test framework
- `hypothesis` is the default property-testing framework
- phase-gate metadata validation is implemented in Python

## Phase Overview

| Phase | Name | Primary Outcome |
|---|---|---|
| P0 | Python Bootstrap and Tooling | Package skeleton, env bootstrap, CI basics |
| P1 | Frontend Parsing Core | Lexer/parser and AST for POSIX-core grammar |
| P2 | Semantic Analysis Core | Deterministic semantic checks and normalized IR |
| P3 | LLVM Lowering + Runtime Core | First runnable `quawk` execution path |
| P4 | JIT Execution + Cache Layer | Memory/disk cache with safe fallback |
| P5 | Compatibility and Hardening | Differential compatibility gates and regression control |
| P6 | Pre-Release Readiness | Documentation completion, perf baseline, release checklist |

## Phase Entry and Exit Rules

Entry gate for every phase:

1. author full planned tests for the phase scope
2. register tests in the runner with `xfail` status and reason `phase_bootstrap`
3. capture a baseline report showing expected failures
4. start implementation only after the baseline is checked in

Phase completion rule:
- a phase cannot close with remaining `xfail` tests tagged `phase_bootstrap`
- intentional residual `xfail` must be reclassified to `known_gap` with explicit tracking

## Phase Details

### P0: Python Bootstrap and Tooling

Objective:
- establish Python project scaffolding and enforce reproducible local workflow

In scope:
- create `src/`, `tests/`, `examples/`, and `scripts/`
- add initial package and CLI entrypoint placeholder
- add `pyproject.toml` and dependency policy
- add CI-ready baseline checks and phase-gate validator

Exit criteria:
- bootstrap flow works from a clean checkout
- CI required jobs pass on default branch target platforms
- phase-gate validation is executable in CI

### P1: Frontend Parsing Core

Objective:
- parse POSIX AWK core programs into a stable AST

In scope:
- token model and source spans
- context-sensitive lexer for `REGEX` vs `/`
- parser for program, function, pattern-action, statements, and expressions
- implicit concatenation handling
- diagnostics and statement-boundary recovery

Exit criteria:
- grammar forms are parsed or rejected correctly
- regex-vs-division and concat ambiguity tests pass
- diagnostics include stable source spans and error classes

### P2: Semantic Analysis Core

Objective:
- validate parsed AST and normalize into semantically checked IR

In scope:
- symbol tables and scope management
- function declaration and definition checks
- lvalue and assignment validity
- control-flow legality checks
- normalization for backend-ready forms

Exit criteria:
- invalid programs fail with deterministic diagnostics
- valid programs become stable backend inputs
- backend does not depend on parser-only assumptions

### P3: LLVM Lowering + Runtime Core

Objective:
- execute core AWK programs through LLVM-generated machine code

In scope:
- IR-to-LLVM lowering via `llvmlite`
- runtime representation for records, fields, and core builtins
- baseline execution path for `BEGIN`, input loop, and `END`
- CLI help/version/run-path behavior

Exit criteria:
- representative programs execute with expected stdout and exit status
- core field and record semantics are correct for covered cases
- CLI behavior matches the design contract

### P4: JIT Execution + Cache Layer

Objective:
- complete realtime JIT execution with safe cache reuse

In scope:
- execution state machine
- process-local memory cache and persistent disk cache
- cache key generation and validation
- fallback behavior for cache failures
- basic metrics for hit/miss and compile latency

Exit criteria:
- first-run compile executes successfully
- second-run cache hit reduces startup latency in a benchmark scenario
- invalidation triggers recompilation correctly
- cache failures never block execution

### P5: Compatibility and Hardening

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

### P6: Pre-Release Readiness

Objective:
- ship an initial public release candidate

In scope:
- CLI contract freeze and doc completion
- performance baseline and regression thresholds
- release packaging metadata and changelog process
- contributor/support workflow polish

Exit criteria:
- release checklist is complete
- smoke test matrix passes on declared environments
- documentation is internally consistent and accurate

## Immediate Next Tasks

Start here unless priorities change:

1. `T-001` create `src/`, `tests/`, `examples/`, and `scripts/`
2. `T-002` add `pyproject.toml` and package entrypoint
3. `T-003` add initial `src/quawk` placeholders
4. `T-004` add Python env bootstrap policy (`uv` + project `.venv`)
5. `T-006` add the phase-gate validator in Python
6. `T-007` wire required CI jobs
7. `T-043` write P1 tests as the initial `xfail` baseline
8. `T-009` define token and source-span models

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
| T-001 | P0 | P0 | Create `src/`, `tests/`, `examples/`, `scripts/` directories | none | Directories exist and are documented | todo |
| T-002 | P0 | P0 | Add `pyproject.toml` with package metadata and console entrypoint | T-001 | `quawk --help` entrypoint resolves in the local `.venv` | todo |
| T-003 | P0 | P0 | Add initial `src/quawk/__init__.py` and `src/quawk/cli.py` placeholders | T-002 | Placeholder package imports cleanly | todo |
| T-004 | P0 | P1 | Add `uv` bootstrap instructions for Python `3.14.x` and the project `.venv` | none | Clean checkout setup succeeds with documented `uv` commands | todo |
| T-005 | P0 | P1 | Add `uv`-based contributor command shortcuts or workflow notes | T-004 | Common contributor commands run cleanly from the documented `uv` environment | todo |
| T-006 | P0 | P0 | Add Python phase-gate validator (`scripts/check_phase_gate.py`) | none | Invalid manifests and gate violations fail with deterministic output | todo |
| T-007 | P0 | P1 | Add CI workflow for format/lint/type/test/phase-gate checks | T-002, T-006 | CI blocks merges on required failures | todo |
| T-008 | P0 | P1 | Add `CONTRIBUTING.md` workflow and review expectations | none | README links contributing guide and guide is coherent | done |
| T-043 | P1 | P0 | Author full P1 frontend tests as `xfail` baseline | T-002, T-006 | P1 tests committed with `xfail_reason=phase_bootstrap` | todo |
| T-009 | P1 | P0 | Define token types and source-span representation | T-003, T-043 | Token/span modules tested and stable | todo |
| T-010 | P1 | P0 | Implement lexer core with newline/separator handling | T-009 | Lexer fixtures pass for separator-sensitive inputs | todo |
| T-011 | P1 | P0 | Implement `REGEX` vs `/` context-sensitive lexing | T-010 | Dedicated ambiguity tests pass | todo |
| T-012 | P1 | P0 | Define AST node set for grammar in `docs/design.md` | T-009 | AST model covers planned grammar forms | todo |
| T-013 | P1 | P0 | Implement parser for top-level items and statements | T-012 | Parser accepts representative valid programs | todo |
| T-014 | P1 | P0 | Implement expression parser with implicit concatenation | T-013 | Precedence and concat tests pass | todo |
| T-015 | P1 | P1 | Add parser error recovery at statement boundaries | T-013 | Multi-error fixture tests produce stable error counts | todo |
| T-016 | P1 | P1 | Add parser golden tests for AST snapshots | T-012, T-014 | Golden outputs deterministic and reviewed | todo |
| T-017 | P1 | P1 | Add parser conformance fixtures mapped to grammar sections | T-013, T-014 | Coverage matrix shows each grammar area tested | todo |
| T-044 | P2 | P0 | Author full P2 semantic-analysis tests as `xfail` baseline | T-017 | P2 baseline committed with expected failures | todo |
| T-018 | P2 | P0 | Build symbol table/scoping infrastructure | T-012, T-044 | Scope tests pass for nested contexts/functions | todo |
| T-019 | P2 | P0 | Implement semantic checks for lvalues/assignment legality | T-018 | Invalid lvalue tests fail with expected error codes | todo |
| T-020 | P2 | P0 | Implement control-flow legality checks | T-018 | `break`/`continue`/`return` legality tests pass | todo |
| T-021 | P2 | P1 | Implement function declaration/definition checks | T-018 | Duplicate/conflicting definitions handled deterministically | todo |
| T-022 | P2 | P1 | Add semantic normalization pass for backend consumption | T-019, T-020, T-021 | Normalized IR consumed by backend prototype | todo |
| T-023 | P2 | P1 | Define semantic error code catalog | T-019, T-020, T-021 | Errors emitted with stable code and source span | todo |
| T-045 | P3 | P0 | Author full P3 backend/runtime tests as `xfail` baseline | T-023 | P3 baseline committed with expected failures | todo |
| T-024 | P3 | P0 | Define runtime value model for core AWK semantics | T-022, T-045 | Runtime model doc + representation checked in | todo |
| T-025 | P3 | P0 | Implement lowering from normalized IR to LLVM IR via `llvmlite` | T-022 | Core sample programs execute through JIT path | todo |
| T-026 | P3 | P0 | Implement runtime input loop (`BEGIN`, records, `END`) | T-024, T-025 | Record-processing fixtures pass | todo |
| T-027 | P3 | P1 | Implement core builtin subset required by compatibility suite | T-024, T-026 | Builtin fixture tests pass for selected subset | todo |
| T-028 | P3 | P1 | Add backend integration tests (stdout/stderr/exit status) | T-025, T-026 | Integration tests run in required CI jobs | todo |
| T-039 | P3 | P0 | Implement CLI contract behavior from `docs/design.md` | T-026 | Help/version/exit behaviors are stable and tested | todo |
| T-046 | P4 | P0 | Author full P4 JIT/cache tests as `xfail` baseline | T-028 | P4 baseline committed with expected failures | todo |
| T-029 | P4 | P0 | Implement execution state machine from `docs/design.md` | T-025, T-026, T-046 | End-to-end run path works with cache disabled | todo |
| T-030 | P4 | P0 | Implement cache key generation and metadata schema | T-029 | Key fields include required invalidation inputs | todo |
| T-031 | P4 | P0 | Implement process-local memory cache | T-030 | Repeated run in same process shows cache hits | todo |
| T-032 | P4 | P0 | Implement disk cache read/write with atomic write protocol | T-030 | Cross-process cache reuse tests pass | todo |
| T-033 | P4 | P1 | Implement cache invalidation and corruption fallback paths | T-032 | Corrupt/mismatch cases force safe recompilation | todo |
| T-034 | P4 | P1 | Add runtime/cache metrics and optional summary output | T-029, T-031, T-032 | Metrics exposed for hits/misses/compile time | todo |
| T-047 | P5 | P0 | Author full P5 compatibility tests as `xfail` baseline | T-034 | P5 baseline committed with expected failures | todo |
| T-035 | P5 | P0 | Implement differential test runner (`ota`, `gawk --posix`, `quawk`) | T-028, T-047 | Runner emits comparable normalized outputs | todo |
| T-036 | P5 | P0 | Seed compatibility corpus for parser/runtime core behaviors | T-035 | Core corpus executes and reports per-case status | todo |
| T-037 | P5 | P1 | Add divergence manifest and classification workflow | T-035 | Divergences tracked with explicit categories | todo |
| T-038 | P5 | P1 | Establish CI release gate for `posix-required` tests | T-036, T-037 | CI fails on disallowed status transitions | todo |
| T-048 | P6 | P0 | Author full P6 release-readiness tests as `xfail` baseline | T-038 | P6 baseline committed with expected failures | todo |
| T-040 | P6 | P1 | Add `SPEC.md` feature matrix (implemented/planned/out-of-scope) | T-036 | Feature matrix aligns with tests and docs | todo |
| T-041 | P6 | P1 | Add performance baseline doc and thresholds (`PERF.md`) | T-034 | Benchmarks recorded with repeatable method | todo |
| T-042 | P6 | P1 | Finalize release checklist and changelog workflow | T-039, T-040 | Checklist is complete and versioned | todo |

## Cross-Cutting Tracks

- documentation maintenance
- CI coverage and quality gates
- performance measurement and regression tracking
- risk tracking and decision log updates
- phase TDD discipline

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AWK semantic corner-case drift | High | Differential tests and explicit divergence classification |
| LLVM binding feature limits (`llvmlite`) | High | Keep backend abstraction narrow; add fallback only if blocked |
| Cache invalidation bugs | High | Strict key schema plus corruption/invalidation tests |
| Scope creep from extensions | Medium | POSIX-first gate and defer extensions until compatibility baseline |
| Python dependency drift | Medium | Pin dependency ranges and enforce CI |

## Maintenance Rules

- any accepted scope change must update both the roadmap text and the backlog in the same change
- new tasks must include phase, dependencies, and acceptance criteria
- completed tasks should reference the implementing commit or PR in follow-up notes
- phase implementation tasks should not move to `in_progress` until that phase's `xfail` baseline task is `done`
