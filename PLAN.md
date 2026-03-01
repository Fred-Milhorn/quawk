# quawk Implementation Plan

This document is the phased implementation roadmap for `quawk`.

It is execution-oriented:
- each phase has explicit scope
- each phase has concrete deliverables
- each phase has exit criteria that can be verified

## Planning Assumptions

- Language target is POSIX-oriented AWK first.
- Build/toolchain is Nix-first and reproducible.
- Execution model is realtime parse + JIT with optional caching.
- Reference behavior is checked against `one-true-awk` and `gawk --posix`.
- Phase delivery uses TDD: tests are written first and initially marked `xfail`.
- QCheck is the default SML framework for unit/property testing.

## Phase Overview

| Phase | Name | Primary Outcome |
|---|---|---|
| P0 | Repository and Build Bootstrap | Source tree, build wiring, basic CI checks |
| P1 | Frontend Parsing Core | Lexer/parser and AST construction for core language |
| P2 | Semantic Analysis Core | Name/type/semantic checks with deterministic diagnostics |
| P3 | LLVM Lowering + Runtime Core | Executable core runtime and LLVM codegen pipeline |
| P4 | JIT Execution + Cache Layer | Realtime execution path with memory/disk cache |
| P5 | Compatibility and Hardening | Differential compatibility tests, regressions, stabilization |
| P6 | Pre-Release Readiness | Packaging, docs completion, release criteria |

## Phase Entry Gate (TDD)

This gate applies to every phase before implementation starts:

1. Author full planned tests for the phase scope.
2. Register tests in the runner with `xfail` status (`phase_bootstrap` reason).
3. Capture baseline report showing expected failures.
4. Start implementation only after the baseline is checked in.

Phase completion rule:
- A phase cannot close with remaining `xfail` tests tagged `phase_bootstrap`.
- Any intentional residual `xfail` must be reclassified to `known_gap` with explicit tracking.

## P0: Repository and Build Bootstrap

Objective:
- establish project scaffolding and enforce reproducible build flow.

In scope:
- create `src/`, `tests/`, `examples/`, `scripts/` skeleton
- add initial `.mlb` and placeholder `main.sml`
- wire Nix package/check targets for source build placeholders
- add CI-ready `flake check` baseline

Deliverables:
- initial buildable placeholder binary target
- repo structure aligned with `BUILD.md`
- CI recipe for formatting and flake checks

Exit criteria:
- `nix flake check` passes on main target platform
- `nix build` produces a package containing expected artifacts
- tree structure matches documented layout

## P1: Frontend Parsing Core

Objective:
- parse POSIX AWK core programs into stable AST.

In scope:
- token model and source-span tracking
- context-sensitive lexer for `REGEX` vs `/`
- parser for program/function/pattern-action/statements/expressions
- implicit concatenation handling in expression parsing
- parser diagnostics and error recovery at statement boundaries

Deliverables:
- frontend modules (`lexer`, `parser`, `ast`)
- parser test suite for valid/invalid grammar samples
- golden AST snapshots for representative inputs

Exit criteria:
- all grammar forms in `GRAMMAR.md` are parsed or rejected correctly
- targeted edge tests for regex-vs-division and concat ambiguity pass
- parser diagnostics include stable source spans and error classes

## P2: Semantic Analysis Core

Objective:
- validate parsed AST and normalize into semantically checked IR.

In scope:
- symbol tables and scope management
- function declaration/definition checks
- lvalue and assignment validity rules
- control-flow statement legality checks
- normalization pass for codegen-ready forms

Deliverables:
- semantic pass modules with deterministic error codes
- sema unit tests and fixture-driven failures
- normalized intermediate form documentation

Exit criteria:
- sema catches planned invalid programs with deterministic diagnostics
- sema-accepted programs are stable inputs to backend
- no parser-only assumptions leak into backend

## P3: LLVM Lowering + Runtime Core

Objective:
- execute core AWK programs through LLVM-generated machine code.

In scope:
- AST/sema IR to LLVM IR lowering
- runtime representation for records, fields, and core builtins
- LLVM interop boundary via SML + C shim
- baseline executable path for `BEGIN`/main input loop/`END`

Deliverables:
- backend lowering modules and runtime core modules
- integration tests for core runtime behaviors
- deterministic build/link pipeline under Nix toolchain

Exit criteria:
- representative AWK programs execute with expected stdout/exit status
- core field/record semantics are correct for covered cases
- codegen pipeline is stable under repeated runs

## P4: JIT Execution + Cache Layer

Objective:
- complete realtime JIT execution path with safe cache reuse.

In scope:
- end-to-end execution state machine from `EXECUTION.md`
- memory cache and disk cache implementations
- cache key generation and validation
- fallback behavior for all cache failures
- basic metrics for hit/miss/compile latency

Deliverables:
- executable runtime with optional cache flags
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
- reduced `known-gap` inventory

Exit criteria:
- no failing `posix-required` tests in release test set
- all known divergences are explicitly documented and tagged
- stability pass shows no high-severity regressions

## P6: Pre-Release Readiness

Objective:
- ship an initial public release candidate.

In scope:
- CLI contract freeze and doc completion
- performance baseline and regression thresholds
- release packaging metadata and changelog process
- contributor and support workflow polish

Deliverables:
- release-candidate build artifacts
- completed user and contributor docs
- versioned release checklist

Exit criteria:
- release checklist items are all complete
- smoke test matrix passes on declared supported environments
- documentation is internally consistent and accurate

## Cross-Cutting Tracks

These run across phases:
- Documentation maintenance (`README`, `BUILD`, `PLAN`, `TASKS`, specs)
- CI coverage and quality gates
- Performance measurement and regressions
- Risk tracking and decision log updates
- Phase TDD discipline (`xfail` baseline before code, burn-down to pass)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AWK semantic corner-case drift | High | Differential tests + explicit divergence classification |
| LLVM interop complexity in SML | High | Keep narrow C shim API and integration tests early |
| Cache invalidation bugs | High | Strict key schema + corruption/invalidation tests |
| Scope creep from extensions | Medium | POSIX-first gate; extension work only after compatibility baseline |
| Toolchain drift | Medium | Pin via `flake.lock`, enforce CI checks |

## Reporting Cadence

- Weekly: phase progress summary and blocked tasks.
- Milestone boundary: exit-criteria check report.
- Any scope change: update this document and `TASKS.md` in same change.
