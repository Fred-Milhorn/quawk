# quawk Implementation Tasks

This document is the execution backlog for `PLAN.md`.

Status values:
- `todo`
- `in_progress`
- `blocked`
- `done`

Priority values:
- `P0` (highest)
- `P1`
- `P2`

## Task Table

| ID | Phase | Priority | Task | Depends On | Acceptance | Status |
|---|---|---|---|---|---|---|
| T-000 | P0 | P0 | Rebaseline docs to Python/llvmlite implementation plan | none | Core docs reflect Python 3.14 + `pyenv`/`venv`/`direnv` workflow | done |
| T-001 | P0 | P0 | Create `src/`, `tests/`, `examples/`, `scripts/` directories | none | Directories exist and are documented | todo |
| T-002 | P0 | P0 | Add `pyproject.toml` with package metadata and console entrypoint | T-001 | `quawk --help` entrypoint resolves in local venv | todo |
| T-003 | P0 | P0 | Add initial `src/quawk/__init__.py` and `src/quawk/cli.py` placeholders | T-002 | Placeholder package imports cleanly | todo |
| T-004 | P0 | P1 | Add `.python-version` and bootstrap instructions for `pyenv` + `venv` | none | Clean checkout setup succeeds with documented commands | todo |
| T-005 | P0 | P1 | Add optional `.envrc` template for automatic venv activation | T-004 | `direnv allow` activates expected environment | todo |
| T-006 | P0 | P0 | Add Python phase-gate validator (`scripts/check_phase_gate.py`) | none | Invalid manifests and gate violations fail with deterministic output | todo |
| T-007 | P0 | P1 | Add CI workflow for format/lint/type/test/phase-gate checks | T-002, T-006 | CI blocks merges on required failures | todo |
| T-008 | P0 | P1 | Add `CONTRIBUTING.md` workflow and review expectations | none | README links contributing guide and guide is coherent | todo |
| T-043 | P1 | P0 | Author full P1 frontend tests as `xfail` baseline | T-002, T-006 | P1 tests committed with `xfail_reason=phase_bootstrap` | todo |
| T-009 | P1 | P0 | Define token types and source-span representation | T-003, T-043 | Token/span modules tested and stable | todo |
| T-010 | P1 | P0 | Implement lexer core with newline/separator handling | T-009 | Lexer fixtures pass for separator-sensitive inputs | todo |
| T-011 | P1 | P0 | Implement `REGEX` vs `/` context-sensitive lexing | T-010 | Dedicated ambiguity tests pass | todo |
| T-012 | P1 | P0 | Define AST node set for grammar in `GRAMMAR.md` | T-009 | AST model covers planned grammar forms | todo |
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
| T-039 | P3 | P0 | Implement CLI contract behavior from `CLI.md` | T-026 | Help/version/exit behaviors are stable and tested | todo |
| T-046 | P4 | P0 | Author full P4 JIT/cache tests as `xfail` baseline | T-028 | P4 baseline committed with expected failures | todo |
| T-029 | P4 | P0 | Implement execution state machine from `EXECUTION.md` | T-025, T-026, T-046 | End-to-end run path works with cache disabled | todo |
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

## Immediate Next Tasks

Start here unless priorities change:

1. `T-001` directory skeleton
2. `T-002` `pyproject.toml` and package entrypoint
3. `T-003` initial `src/quawk` placeholders
4. `T-004` Python env bootstrap policy (`pyenv` + `venv`)
5. `T-006` phase-gate validator in Python
6. `T-007` CI required jobs wiring
7. `T-043` write P1 tests as `xfail` baseline
8. `T-009` token/span definitions

## Maintenance Rules

- Any accepted scope change must update both `PLAN.md` and `TASKS.md` in the same change.
- New tasks must include phase, dependencies, and acceptance criteria.
- Completed tasks should reference implementing commit/PR in follow-up notes.
- Phase implementation tasks should not move to `in_progress` until that phase `xfail` baseline task is `done`.
