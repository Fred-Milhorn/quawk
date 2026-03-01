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
| T-001 | P0 | P0 | Create `src/`, `tests/`, `examples/`, `scripts/` directories | none | Directories exist and are documented | todo |
| T-002 | P0 | P0 | Add initial `src/quawk.mlb` and `src/main.sml` placeholders | T-001 | `mlton` can evaluate source graph placeholder under Nix shell | todo |
| T-003 | P0 | P0 | Update `flake.nix` default package from docs-only to source package skeleton | T-002 | `nix build` produces expected package layout | todo |
| T-004 | P0 | P1 | Add base test package/check wiring to flake outputs | T-001 | `nix flake check` includes test check derivation | todo |
| T-005 | P0 | P1 | Add CI workflow spec for `fmt`, `build`, `flake check` | T-003, T-004 | CI config draft checked in and runnable | todo |
| T-006 | P0 | P2 | Add `CONTRIBUTING.md` with workflow and coding standards | none | README links contributing guide; guide is coherent | todo |
| T-051 | P0 | P0 | Pin QCheck and one-true-awk via Nix flake inputs | T-003 | `flake.lock` contains pinned `qcheck` and `oneTrueAwk` inputs | done |
| T-052 | P0 | P0 | Define simple test manifest contract and examples (`TEST_SPEC.md`) | T-004 | Spec is documented and referenced by testing docs | done |
| T-053 | P0 | P0 | Define CI gate policy document (`CI.md`) and required jobs | T-004, T-052 | CI policy doc defines required blocking jobs and phase gate checks | done |
| T-054 | P0 | P1 | Implement `scripts/check-phase-gate` for manifest + xfail validation | T-052, T-053 | Script fails invalid manifests and phase-gate violations | todo |
| T-049 | P0 | P0 | Integrate QCheck as default SML test framework and add sample test target | T-004 | QCheck-based sample test runs under `nix flake check` | todo |
| T-043 | P1 | P0 | Author full P1 parser/frontend tests and check in as `xfail` baseline | T-004, T-049, T-054 | P1 tests committed with `xfail` (`phase_bootstrap`) and baseline report | todo |
| T-007 | P1 | P0 | Define token types and source span representation | T-002, T-043 | Token/span modules compile and unit tests pass | todo |
| T-008 | P1 | P0 | Implement lexer core with newline/separator handling | T-007 | Lexer fixture tests pass for separator-sensitive inputs | todo |
| T-009 | P1 | P0 | Implement `REGEX` vs `/` context-sensitive lexing | T-008 | Dedicated ambiguity tests pass | todo |
| T-010 | P1 | P0 | Define AST node set for grammar in `GRAMMAR.md` | T-007 | AST module covers grammar forms and compiles | todo |
| T-011 | P1 | P0 | Implement parser for top-level items and statements | T-010 | Parser accepts representative valid programs | todo |
| T-012 | P1 | P0 | Implement expression parser with implicit concat | T-011 | Precedence/concat tests pass (including ambiguity edges) | todo |
| T-013 | P1 | P1 | Add parser error recovery at statement boundaries | T-011 | Multi-error fixture tests produce stable error count | todo |
| T-014 | P1 | P1 | Add parser golden tests for AST snapshots | T-010, T-012 | Golden updates deterministic and reviewed | todo |
| T-015 | P1 | P1 | Add parser conformance fixtures mapped to `GRAMMAR.md` sections | T-011, T-012 | Coverage matrix shows each grammar area tested | todo |
| T-044 | P2 | P0 | Author full P2 semantic-analysis tests and check in as `xfail` baseline | T-015 | P2 tests committed with `xfail` (`phase_bootstrap`) and baseline report | todo |
| T-016 | P2 | P0 | Build symbol table/scoping infrastructure | T-010, T-044 | Scope tests pass for nested contexts/functions | todo |
| T-017 | P2 | P0 | Implement semantic checks for lvalues/assignment legality | T-016 | Invalid lvalue tests fail with expected errors | todo |
| T-018 | P2 | P0 | Implement control-flow legality checks | T-016 | `break/continue/return` legality tests pass | todo |
| T-019 | P2 | P1 | Implement function declaration/definition checks | T-016 | Duplicate/conflicting definitions handled deterministically | todo |
| T-020 | P2 | P1 | Add semantic normalization pass for backend consumption | T-017, T-018, T-019 | Normalized form consumed by backend prototype | todo |
| T-021 | P2 | P1 | Define semantic error code catalog | T-017, T-018, T-019 | Errors emitted with stable code + source span | todo |
| T-045 | P3 | P0 | Author full P3 backend/runtime tests and check in as `xfail` baseline | T-021 | P3 tests committed with `xfail` (`phase_bootstrap`) and baseline report | todo |
| T-022 | P3 | P0 | Define runtime value model for core AWK semantics | T-020, T-045 | Runtime model doc + compile-time representation checked in | todo |
| T-023 | P3 | P0 | Implement minimal LLVM interop C shim API | T-003 | Shim compiles and links in Nix environment | todo |
| T-024 | P3 | P0 | Implement lowering from normalized IR to LLVM IR (core subset) | T-020, T-023 | Core sample programs execute through JIT path | todo |
| T-025 | P3 | P0 | Implement runtime input loop (`BEGIN`, records, `END`) | T-022, T-024 | Record-processing fixtures pass | todo |
| T-026 | P3 | P1 | Implement builtins subset required for core compatibility suite | T-022, T-025 | Builtin fixture tests pass for selected subset | todo |
| T-027 | P3 | P1 | Add backend integration tests (stdout/stderr/exit status) | T-024, T-025 | Integration tests run in `flake check` | todo |
| T-046 | P4 | P0 | Author full P4 JIT/cache tests and check in as `xfail` baseline | T-027 | P4 tests committed with `xfail` (`phase_bootstrap`) and baseline report | todo |
| T-028 | P4 | P0 | Implement execution state machine from `EXECUTION.md` | T-024, T-025, T-046 | End-to-end run path works without cache | todo |
| T-029 | P4 | P0 | Implement cache key generation and metadata schema | T-028 | Key fields include required invalidation inputs | todo |
| T-030 | P4 | P0 | Implement process-local memory cache | T-029 | Repeated run in same process shows cache hit behavior | todo |
| T-031 | P4 | P0 | Implement disk cache read/write with atomic write protocol | T-029 | Cross-process cache reuse tests pass | todo |
| T-032 | P4 | P1 | Implement cache invalidation and corruption fallback paths | T-031 | Corrupt/mismatch cases force safe recompilation | todo |
| T-033 | P4 | P1 | Add runtime/cache metrics and optional summary output | T-028, T-030, T-031 | Metrics exposed for hits/misses/compile time | todo |
| T-047 | P5 | P0 | Author full P5 compatibility/hardening tests and check in as `xfail` baseline | T-033 | P5 tests committed with `xfail` (`phase_bootstrap`) and baseline report | todo |
| T-034 | P5 | P0 | Implement differential test runner (`ota`, `gawk --posix`, `quawk`) | T-027, T-047 | Runner emits comparable normalized outputs | todo |
| T-035 | P5 | P0 | Seed compatibility corpus for parser/runtime core behaviors | T-034 | Core corpus executes and reports per-case status | todo |
| T-036 | P5 | P1 | Add divergence manifest and classification workflow | T-034 | Divergences tracked with explicit category | todo |
| T-037 | P5 | P1 | Establish release gating policy in CI for `posix-required` tests | T-035, T-036 | CI fails on disallowed status transitions | todo |
| T-038 | P5 | P2 | Expand compatibility corpus for regex/io/edge semantics | T-035 | Coverage report shows expanded scope | todo |
| T-048 | P6 | P0 | Author full P6 release-readiness tests and check in as `xfail` baseline | T-038 | P6 tests committed with `xfail` (`phase_bootstrap`) and baseline report | todo |
| T-039 | P6 | P0 | Define CLI contract and document in `CLI.md` | T-028, T-031, T-048 | CLI flags and exit codes stable and documented | todo |
| T-040 | P6 | P1 | Add `SPEC.md` feature matrix (implemented/planned/out-of-scope) | T-035 | Feature matrix aligns with tests and docs | todo |
| T-041 | P6 | P1 | Add performance baseline doc and thresholds (`PERF.md`) | T-033 | Benchmarks recorded with repeatable method | todo |
| T-042 | P6 | P1 | Finalize release checklist and changelog workflow | T-039, T-040 | Checklist is complete and versioned | todo |
| T-050 | P6 | P2 | Evaluate continued QCheck suitability and document any framework split decisions | T-041 | Decision note added to `TESTING.md` with rationale | todo |

## Immediate Next Tasks

Start here unless priorities are explicitly changed:

1. `T-001` directory skeleton
2. `T-002` initial `.mlb` and `main.sml`
3. `T-003` flake package transition from docs-only to source skeleton
4. `T-004` base test wiring in `flake check`
5. `T-054` implement phase gate checker script
6. `T-049` integrate QCheck and add sample test target
7. `T-043` write P1 tests as `xfail` baseline
8. `T-007` token/span definitions

## Maintenance Rules

- Any accepted scope change must update both `PLAN.md` and `TASKS.md` in the same change.
- New tasks should include phase, dependency links, and acceptance criteria.
- Completed tasks should reference the implementing commit/PR in a follow-up note.
- Phase implementation tasks should not move to `in_progress` until their phase `xfail` baseline task is `done`.
