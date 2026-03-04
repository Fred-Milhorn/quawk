# quawk Implementation Plan

This document is the phased implementation roadmap for `quawk`.

It is execution-oriented:
- each phase has explicit scope
- each phase has concrete deliverables
- each phase has verifiable exit criteria

## Planning Assumptions

- Language target is POSIX-oriented AWK first.
- Implementation language is Python (minimum `3.14.x`).
- Developer workflow baseline is `pyenv` + project `venv` + optional `direnv`.
- LLVM-backed JIT uses `llvmlite`.
- Reference behavior is checked against `one-true-awk` and `gawk --posix`.
- Phase delivery uses TDD: tests are written first and initially marked `xfail`.
- `pytest` is the default test framework.
- `hypothesis` is the default property-testing framework.
- Phase-gate metadata validation is implemented in Python.

## Phase Overview

| Phase | Name | Primary Outcome |
|---|---|---|
| P0 | Python Bootstrap and Tooling | Package skeleton, env bootstrap, CI basics |
| P1 | Frontend Parsing Core | Lexer/parser and AST for POSIX-core grammar |
| P2 | Semantic Analysis Core | Deterministic semantic checks + normalized IR |
| P3 | LLVM Lowering + Runtime Core | First runnable `quawk` execution path |
| P4 | JIT Execution + Cache Layer | Memory/disk cache with safe fallback |
| P5 | Compatibility and Hardening | Differential compatibility gates and regression control |
| P6 | Pre-Release Readiness | Documentation completion, perf baseline, release checklist |

## Phase Entry Gate (TDD)

This gate applies to every phase before implementation starts:

1. Author full planned tests for the phase scope.
2. Register tests in the runner with `xfail` status (`phase_bootstrap` reason).
3. Capture baseline report showing expected failures.
4. Start implementation only after baseline is checked in.

Phase completion rule:
- a phase cannot close with remaining `xfail` tests tagged `phase_bootstrap`
- intentional residual `xfail` must be reclassified to `known_gap` with explicit tracking

## P0: Python Bootstrap and Tooling

Objective:
- establish Python project scaffolding and enforce reproducible local workflow.

In scope:
- create `src/`, `tests/`, `examples/`, `scripts/` skeleton
- add initial Python package (`src/quawk`) and CLI entrypoint placeholder
- add `pyproject.toml` and dev/test dependency policy
- add CI-ready baseline checks and Python phase-gate validator

Deliverables:
- initial runnable placeholder CLI (`quawk --help`)
- repository structure aligned with `BUILD.md`
- CI policy and commands aligned with `CI.md`

Exit criteria:
- bootstrap flow works from clean checkout using Python-native instructions
- CI required jobs pass on default branch target platforms
- phase-gate validation is executable in CI

## P1: Frontend Parsing Core

Objective:
- parse POSIX AWK core programs into stable AST.

In scope:
- token model and source-span tracking
- context-sensitive lexer for `REGEX` vs `/`
- parser for program/function/pattern-action/statements/expressions
- implicit concatenation handling in expression parsing
- parser diagnostics and statement-boundary error recovery

Deliverables:
- frontend modules (`lexer`, `parser`, `ast`)
- parser test suite for valid/invalid grammar samples
- golden AST snapshots for representative inputs

Exit criteria:
- grammar forms in `GRAMMAR.md` are parsed or rejected correctly
- regex-vs-division and concat ambiguity tests pass
- diagnostics include stable source spans and error classes

## P2: Semantic Analysis Core

Objective:
- validate parsed AST and normalize into semantically checked IR.

In scope:
- symbol tables and scope management
- function declaration/definition checks
- lvalue and assignment validity rules
- control-flow legality checks
- normalization pass for backend-ready forms

Deliverables:
- semantic analysis modules with deterministic error codes
- semantic unit tests and fixture-driven failures
- normalized intermediate form contract

Exit criteria:
- planned invalid programs fail with deterministic diagnostics
- semantically valid programs become stable backend inputs
- backend does not depend on parser-only assumptions

## P3: LLVM Lowering + Runtime Core

Objective:
- execute core AWK programs through LLVM-generated machine code.

In scope:
- normalized IR to LLVM IR lowering (`llvmlite`)
- runtime representation for records, fields, and core builtins
- baseline execution path for `BEGIN` / input loop / `END`
- CLI run path and help/version contract implementation

Deliverables:
- backend lowering modules and runtime core modules
- integration tests for core runtime behaviors
- deterministic end-to-end execution for representative programs

Exit criteria:
- representative programs execute with expected stdout/exit status
- core field/record semantics are correct for covered cases
- CLI behavior matches `CLI.md` for help/version/exit semantics

## P4: JIT Execution + Cache Layer

Objective:
- complete realtime JIT execution path with safe cache reuse.

In scope:
- end-to-end execution state machine from `EXECUTION.md`
- process-local memory cache and persistent disk cache
- cache key generation and validation
- fallback behavior for all cache failures
- basic metrics for hit/miss/compile latency

Deliverables:
- executable runtime with cache controls
- cache metadata/artifact management implementation
- cache behavior tests (miss/hit/invalidate/corruption)

Exit criteria:
- first-run compile executes successfully
- second-run cache hit reduces startup latency in benchmark scenario
- invalidation conditions trigger recompilation correctly
- cache failures never block execution

## P5: Compatibility and Hardening

Objective:
- maximize POSIX compatibility and reduce behavioral gaps.

In scope:
- differential runner against `one-true-awk` and `gawk --posix`
- divergence classification workflow per `TESTING.md`
- expansion of parser/runtime/regex/io compatibility corpus
- regression triage and targeted fixes

Deliverables:
- compatibility test harness and reporting
- tracked divergence manifest with justifications
- reduced `known_gap` inventory

Exit criteria:
- no failing `posix-required` tests in release test set
- known divergences are documented and tagged
- hardening pass shows no high-severity regressions

## P6: Pre-Release Readiness

Objective:
- ship an initial public release candidate.

In scope:
- CLI contract freeze and doc completion
- performance baseline and regression thresholds
- release packaging metadata and changelog process
- contributor/support workflow polish

Deliverables:
- release-candidate artifacts
- completed user and contributor docs
- versioned release checklist

Exit criteria:
- release checklist is complete
- smoke test matrix passes on declared environments
- documentation is internally consistent and accurate

## Cross-Cutting Tracks

These run across phases:
- documentation maintenance (`README`, `BUILD`, `PLAN`, `TASKS`, specs)
- CI coverage and quality gates
- performance measurement and regression tracking
- risk tracking and decision log updates
- phase TDD discipline (`xfail` baseline before code, burn-down to pass)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AWK semantic corner-case drift | High | Differential tests + explicit divergence classification |
| LLVM binding feature limits (`llvmlite`) | High | Keep backend abstraction narrow; add fallback path only if blocked |
| Cache invalidation bugs | High | Strict key schema + corruption/invalidation tests |
| Scope creep from extensions | Medium | POSIX-first gate; defer extensions until compatibility baseline |
| Python dependency drift | Medium | Pin dependency ranges and enforce CI |

## Reporting Cadence

- Update `TASKS.md` status fields as work progresses.
- Report phase progress against entry/exit criteria.
- Track known gaps with explicit test metadata and linked task IDs.
