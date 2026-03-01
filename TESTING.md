# AWK Compatibility Testing Strategy

This document defines how `quawk` will validate behavior against existing AWK implementations while targeting POSIX semantics.

## Objectives

- Catch parser/runtime regressions early.
- Make compatibility decisions explicit and reproducible.
- Prioritize POSIX-conformant behavior over implementation-specific quirks.

## TDD Workflow Policy

Implementation follows strict phase-based TDD:

1. Before a phase starts, author that phase's full planned test set.
2. Mark the new tests as `xfail` (expected fail) while functionality is unimplemented.
3. Implement features by burning down phase `xfail` tests to `pass`.
4. Do not close a phase with unresolved phase `xfail` tests.

Allowed exception:
- a test may remain `xfail` only if reclassified as `known-gap` with explicit documentation and linked tracking item.

Metadata contract:
- test case manifests must follow [TEST_SPEC.md](/Users/fred/dev/quawk/TEST_SPEC.md)

## Test Framework Baseline

Default SML test framework:
- QCheck: <https://github.com/league/qcheck>

Framework policy:
- Use QCheck for unit/property tests in frontend, semantic, and runtime layers.
- Keep compatibility/differential harness orchestration separate from QCheck where external process control is required.
- If QCheck cannot cover a scenario (for example integration-level process orchestration), use a thin custom harness with the same `pass`/`xfail`/`fail` reporting model.

## Reference Implementations

Primary reference:
- `one-true-awk` (historical/canonical AWK baseline)

Secondary reference:
- `gawk --posix` (broadly deployed implementation with strong diagnostics)

Decision rule:
- If `one-true-awk` and `gawk --posix` agree, `quawk` should match.
- If they differ, classify by POSIX spec text before deciding expected behavior.

## Test Corpus Structure

Organize tests into behavior-focused suites:

- `parser/`: grammar acceptance/rejection, precedence, regex-vs-division, concatenation.
- `runtime/records_fields/`: `NR`, `FNR`, `NF`, field splitting, record separators.
- `runtime/types_coercions/`: numeric/string conversions, comparison semantics.
- `runtime/control_flow/`: loops, `break`, `continue`, `next`, `exit`, `return`.
- `runtime/functions/`: builtins and user-defined function behavior.
- `runtime/regex/`: match semantics, regex literals, edge escaping cases.
- `io/`: file input behavior and print/printf formatting.
- `errors/`: syntax and runtime diagnostics (message stability policy defined separately).

Each test should include:
- AWK program text
- input fixture(s)
- expected stdout
- expected stderr class (exact text optional)
- expected exit status
- tags: `posix-required`, `unspecified`, `extension`, `known-gap`

## Oracle Execution Model

For each compatibility test:

1. Run under `one-true-awk`.
2. Run under `gawk --posix`.
3. Run under `quawk`.
4. Compare normalized outputs and exit codes.

Normalize before comparison:
- line endings (`\r\n` vs `\n`)
- trailing whitespace policy (choose strict or trimmed once, then enforce)
- locale/timezone-sensitive values using fixed test environment

## Divergence Classification

When references disagree, classify once and record in a manifest:

- `POSIX-specified`: expected behavior must follow POSIX text.
- `implementation-defined`: choose one behavior and document it.
- `unspecified/undefined`: allow multiple outcomes; avoid overfitting.
- `extension`: behavior outside current scope; mark as `known-gap`.

Policy:
- Never silently “pick one.” Every persistent divergence needs an explicit classification entry.

## Pass/Fail Policy

Test statuses:

- `pass`: `quawk` matches expected result.
- `xfail`: expected failure; must include reason metadata.
- `xfail` reason `phase_bootstrap`: temporary, pre-implementation state for a planned phase.
- `xfail` reason `known_gap`: accepted gap with linked tracking item.
- `fail`: regression or unresolved incompatibility.

Release gate recommendation:
- No failing `posix-required` tests.
- No remaining `xfail` tests with reason `phase_bootstrap` in a completed phase.
- `xfail` with reason `known_gap` allowed only when explicitly tagged and documented.
- CI gate requirements are defined in [CI.md](/Users/fred/dev/quawk/CI.md).

## Milestones

1. Bootstrap parser-focused compatibility suite.
2. Add core POSIX runtime behavior tests.
3. Add differential runner against both references.
4. Enforce pass/xfail policy in CI.
5. Reduce `known-gap` inventory each milestone.

## Operational Notes

- Pin reference interpreter versions in CI for reproducibility.
- Rebaseline intentionally only via reviewed change to expected results.
- Keep small, focused tests; prefer one behavior assertion per test case.
