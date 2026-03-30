# Compatibility Plan

This document defines the current `P11` compatibility plan for `quawk`.

The initial transition to pinned upstream references is complete. The next
stage is to grow the upstream compatibility suite deliberately, with a
POSIX-first stop condition that matches the public claims in [SPEC.md](../SPEC.md).

## Summary

Current compatibility stance:

- `compat_upstream` is the primary compatibility authority
- `compat_local` remains a fast supplemental regression suite
- One True Awk is the primary upstream source for core POSIX-style coverage
- gawk is a secondary source used to add fixture-backed POSIX coverage and to catch disagreements

Explicit non-goal:

- do not try to run every upstream test in either tree

That is the correct scope because:

- One True Awk's `testdir` includes broad historical regression, systematic
  feature tests, and timing tests; upstream's own
  [README.TESTS](/Users/fred/dev/quawk/third_party/onetrueawk/testdir/README.TESTS)
  describes roughly 60 `p.*`, 160 `t.*`, about 20 `T.*`, and timing-oriented
  `tt.*` files
- gawk's `test/` tree is much larger and includes substantial GNU-specific,
  shell-driven, platform-sensitive, and non-POSIX behavior
- `quawk` is still a POSIX-first implementation, not a GNU awk clone

## Goal

Grow the upstream compatibility suite until:

- every feature family currently marked `implemented` in [SPEC.md](../SPEC.md)
  has upstream coverage in the checked-in selection manifest
- active failures are fixed or explicitly classified
- the repo-owned local corpus is no longer the only compatibility evidence for
  any implemented POSIX family

The target is not exhaustive upstream ingestion. The target is an honest,
reviewable, POSIX-first compatibility contract.

## Local Workflow

Recommended local flow:

```sh
git submodule update --init --recursive
uv run python scripts/upstream_compat.py bootstrap
uv run pytest -m compat_upstream
uv run pytest -m compat_local
```

Expected behavior:

- `bootstrap` builds deterministic local reference binaries for One True Awk
  and gawk under ignored `build/` paths
- the compatibility harness resolves only those pinned binaries by default
- `compat_upstream` is the authoritative compatibility gate
- `compat_local` remains available as a faster repo-owned regression suite

## Selection Policy

The checked-in selection manifest at
`tests/upstream/selection.toml` is the source of truth for the upstream suite.

Manifest structure:

- `[[case]]` entries classify individual upstream tests as `run` or `skip`
- `[[coverage]]` entries map the currently implemented compatibility feature
  families to those upstream case selections

Every candidate upstream case must be one of:

- `run`
- `skip` with an explicit reason

Do not silently omit cases once a case family is under review.

### Source Priority

One True Awk is primary:

- first priority: `p.*`
- second priority: simple `t.*`
- third priority: selected `T.*` only when they cover an in-scope POSIX family
  that `p.*` and `t.*` do not cover well
- never use `tt.*` timing tests for compatibility gating

gawk is secondary:

- first priority: `.awk + .ok`
- second priority: `.awk + .in + .ok`
- third priority: selected `.sh` drivers only when they cover an in-scope
  POSIX family that direct fixtures cannot

### Default Exclusions

Skip by default:

- GNU-only behavior
- debugger or profiler features
- dynamic extension loading, namespaces, or `@load`
- MPFR or arbitrary-precision behavior
- locale-heavy or i18n-sensitive tests
- platform-specific shell or filesystem assumptions
- timing or performance tests
- anything already marked `out-of-scope` in [SPEC.md](../SPEC.md)

## Feature-Family Coverage Rule

Use [SPEC.md](../SPEC.md) as the coverage contract.

Feature families that must each gain upstream coverage:

- CLI basics: `-f`, `-F`, numeric `-v`, `--`, and `-` stdin operand
- pattern-action execution: `BEGIN`, record actions, `END`, expression
  patterns, range patterns, and default-print behavior
- regex-driven selection
- fields and field assignment
- scalars, arrays, `delete`, and `for ... in`
- control flow: `if`, `while`, `do ... while`, classic `for`, `break`,
  `continue`
- record control: `next`, `nextfile`, `exit`
- expressions and coercions
- user-defined functions
- builtin variables: `NR`, `FNR`, `NF`, `FILENAME`
- implemented builtins only: `length`, `split`, `substr`
- multi-file input processing

Selection rule per family:

- at least one One True Awk case must cover the family
- at least one gawk case should corroborate the family when a clean
  fixture-backed case exists
- if one suite has no reasonable in-scope case for a family, document that in
  the selection manifest and cover the family from the other suite

### Current Family Matrix

The current checked-in matrix is still a seed matrix. Several families are
anchored partly or entirely by `skip` entries so the inventory is explicit
before the later expansion tasks promote more of those anchors to runnable
coverage.

| Family | Current upstream anchors |
|---|---|
| `cli-basics` | `one-true-awk:T.-f-f`, `one-true-awk:T.argv`, `gawk:argarray`, `gawk:cmdlinefsbacknl` |
| `pattern-action-execution` | `one-true-awk:p.12`, `one-true-awk:p.23`, `gawk:assignnumfield2`, `gawk:range1` |
| `regex-selection` | `one-true-awk:p.12`, `one-true-awk:p.13` |
| `default-print-patterns` | `one-true-awk:p.23`, `gawk:range1` |
| `scalar-assignment` | `gawk:assignnumfield`, `gawk:assignnumfield2` |
| `associative-arrays` | `one-true-awk:t.a` |
| `fields` | `gawk:assignnumfield`, `one-true-awk:t.set0a`, `one-true-awk:t.NF`, `one-true-awk:T.split`, `gawk:splitvar` |
| `control-flow` | `one-true-awk:t.if`, `one-true-awk:t.do`, `one-true-awk:t.break` |
| `record-control` | `one-true-awk:t.next`, `one-true-awk:t.exit`, `one-true-awk:T.nextfile` |
| `expressions-and-coercions` | `one-true-awk:T.expr`, `one-true-awk:t.substr`, `gawk:getnr2tb` |
| `user-defined-functions` | `one-true-awk:t.fun`, `one-true-awk:T.func` |
| `builtin-variables` | `one-true-awk:p.4`, `one-true-awk:p.24`, `one-true-awk:t.NF`, `one-true-awk:T.argv`, `gawk:argarray`, `gawk:getnr2tb` |
| `implemented-builtins` | `one-true-awk:T.builtin`, `one-true-awk:T.split`, `gawk:splitvar`, `gawk:substr` |
| `multi-file-input-processing` | `one-true-awk:p.24`, `one-true-awk:T.nextfile`, `gawk:argarray` |

## Growth Order

Grow the suite in this order:

1. expand within the current adapters first
   - `onetrueawk-program-file`
   - `gawk-awk-ok`
   - `gawk-awk-in-ok`
2. add more One True Awk `p.*`
3. add gawk `.ok` and `.in/.ok` corroborating cases for the same families
4. fill remaining family gaps with selected One True Awk `t.*`
5. add selected One True Awk `T.*` and gawk `.sh` cases only when a claimed
   family still lacks upstream coverage

Do not start with shell-driver adapters unless a claimed in-scope feature
cannot be covered without them.

## Failure Policy

Not every compatibility failure should be fixed immediately, but every one
should be evaluated explicitly.

Keep two checked-in tracking layers:

1. machine-readable divergence metadata in `tests/upstream/divergences.toml`
2. reviewed notes in `docs/compatibility-evaluations.md`

Each divergence entry should record:

- suite name
- case ID
- classification
- decision
- short summary
- last verified upstream commit
- note reference in the companion doc

Allowed classifications:

- `posix-required-fix`
- `known-gap`
- `intentional-quawk-extension`
- `gnu-extension-out-of-scope`
- `platform-specific`
- `reference-disagreement`
- `wont-fix`

Gate policy:

- unclassified upstream failures fail
- unclassified reference disagreements fail
- stale divergence entries fail
- `posix-required-fix` remains blocking even when classified
- non-blocking failures are allowed only when they are documented in both the
  manifest and the companion notes doc

## CI Promotion

Current workflow:

- `.github/workflows/compat-upstream.yml`
- runs on pull requests, pushes to `main`, and manual `workflow_dispatch`
- builds the pinned references with the same repo-managed bootstrap used locally
- runs `uv run pytest -m compat_upstream`
- is intentionally optional at the branch-protection level for now

Promotion criteria:

- the workflow passes on the default branch for at least 10 consecutive runs
  without infrastructure-only flakes
- typical runtime on the default GitHub-hosted runner stays under 15 minutes
  for the active upstream slice
- the pinned One True Awk and gawk bootstrap remains deterministic on
  `ubuntu-latest`
- active non-fix upstream failures, if any, are classified in
  `tests/upstream/divergences.toml` and reviewed in
  `docs/compatibility-evaluations.md`
- maintainers explicitly add `compat-upstream` to required branch protection
  only after the criteria above are satisfied

## Definition Of Done

The upstream compatibility suite is done when all of the following are true:

- every feature family currently marked `implemented` in [SPEC.md](../SPEC.md)
  has upstream coverage in `tests/upstream/selection.toml`
- for every implemented family, at least one runnable upstream case exists;
  skipped cases are allowed only for harness reasons and must not be the only
  coverage for that family
- all in-scope, adapter-compatible One True Awk `p.*` cases are either runnable
  or explicitly skipped with a reviewed reason
- gawk coverage exists for each major implemented family where a clean
  `.ok` or `.in/.ok` fixture is available
- no runnable upstream case fails without either a fix or an evaluated
  divergence entry plus companion note
- no `posix-required-fix` entries remain for any feature still claimed as
  `implemented`
- the local corpus is no longer the only compatibility evidence for any
  implemented POSIX family

Not required for done:

- all One True Awk `t.*`
- all One True Awk `T.*`
- any `tt.*`
- all gawk tests
- GNU-extension parity

## Implementation Phases

### Phase 1: Foundation

Complete when:

- pinned upstream sources exist
- repo-managed local reference builds exist
- `compat_upstream` runs selected cases under `quawk`, One True Awk, and gawk
- evaluated divergence metadata and companion notes exist
- CI can run the upstream slice as an optional job

### Phase 2: Feature-Family Matrix

Complete when:

- `tests/upstream/selection.toml` is organized by implemented feature family
- each implemented family in [SPEC.md](../SPEC.md) is mapped to upstream cases
  or explicit `skip` decisions
- the One True Awk primary and gawk corroboration policy is reflected in the
  manifest

### Phase 3: Direct-File Coverage Expansion

Complete when:

- in-scope One True Awk `p.*` coverage is expanded broadly across implemented
  families
- gawk `.awk/.ok` and `.awk/.in/.ok` coverage corroborates those families where
  clean fixtures exist
- new failures are fixed or classified as they are added

### Phase 4: Gap Filling

Complete when:

- remaining family gaps are filled with selected One True Awk `t.*`
- shell-driver adapters are added only for still-uncovered in-scope families
- no implemented family lacks runnable upstream coverage from at least one suite

### Phase 5: Completion Audit

Complete when:

- the `Definition Of Done` above is satisfied
- the local corpus is clearly supplemental instead of authoritative
- the suite can stop expanding without creating compatibility blind spots
