# Compatibility Plan

This document defines the current `P11` compatibility plan for `quawk`.

The initial transition to pinned upstream references is complete. The next
stage is to grow the upstream compatibility suite deliberately, with a
POSIX-first stop condition that matches the public claims in [SPEC.md](../SPEC.md).

## Summary

Current compatibility stance:

- `compat_reference` is the primary compatibility authority
- `compat_corpus` remains a fast supplemental regression suite
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
uv run quawk-upstream bootstrap
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
```

Expected behavior:

- `bootstrap` builds deterministic local reference binaries for One True Awk
  and gawk under ignored `build/` paths
- the compatibility harness resolves only those pinned binaries by default
- `compat_reference` is the authoritative compatibility gate
- `compat_corpus` remains available as a faster repo-owned regression suite

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

The current checked-in matrix now includes a broader runnable One True Awk
`p.*` direct-file subset plus a first small wave of runnable gawk
corroborating fixtures for fields, `exit` in function context, string-field
coercion, and `substr` coercion. It now also includes a small One True Awk
`t.*` direct-file expansion for arrays, user-defined functions, and substring
matching, plus focused runnable shell-driver-derived coverage for CLI basics
and multi-file `nextfile` behavior. It still relies on reviewed `skip` anchors
for gawk shell-driver cases and several richer direct-file families that still
expose real quawk gaps.

| Family | Current upstream anchors |
|---|---|
| `cli-basics` | `one-true-awk:T.-f-f`, `one-true-awk:T.argv`, `gawk:argarray`, `gawk:cmdlinefsbacknl` |
| `pattern-action-execution` | `one-true-awk:p.12`, `one-true-awk:p.23`, `gawk:assignnumfield2`, `gawk:range1` |
| `regex-selection` | `one-true-awk:p.12`, `one-true-awk:p.13` |
| `default-print-patterns` | `one-true-awk:p.9`, `one-true-awk:p.11`, `one-true-awk:p.21`, `one-true-awk:p.23`, `gawk:range1` |
| `scalar-assignment` | `one-true-awk:p.31`, `one-true-awk:p.33`, `gawk:assignnumfield`, `gawk:assignnumfield2` |
| `associative-arrays` | `one-true-awk:t.delete1`, `one-true-awk:t.a` |
| `fields` | `gawk:assignnumfield`, `gawk:strfieldnum`, `one-true-awk:p.10`, `one-true-awk:p.25`, `one-true-awk:p.39`, `one-true-awk:t.set0a`, `gawk:splitvar` |
| `control-flow` | `one-true-awk:p.39`, `one-true-awk:t.if`, `one-true-awk:t.do`, `one-true-awk:t.break` |
| `record-control` | `gawk:exit2`, `one-true-awk:t.next`, `one-true-awk:t.exit`, `one-true-awk:T.nextfile` |
| `expressions-and-coercions` | `gawk:numsubstr`, `gawk:strfieldnum`, `one-true-awk:p.20`, `one-true-awk:p.25`, `one-true-awk:p.37`, `gawk:getnr2tb`, `one-true-awk:t.substr` |
| `user-defined-functions` | `gawk:exit2`, `one-true-awk:t.fun`, `one-true-awk:T.func` |
| `builtin-variables` | `one-true-awk:p.28`, `one-true-awk:p.4`, `one-true-awk:p.24`, `one-true-awk:t.NF`, `one-true-awk:T.argv`, `gawk:argarray` |
| `implemented-builtins` | `gawk:numsubstr`, `one-true-awk:p.31`, `one-true-awk:p.33`, `one-true-awk:T.builtin`, `gawk:splitvar`, `gawk:substr` |
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

## T-147 Result

`T-147` is now complete.

What landed:

- promoted runnable One True Awk `t.*` direct-file coverage for:
  - associative arrays via `t.delete1`
  - user-defined functions via `t.fun`
  - substring-driven expressions via `t.substr`
- rewrote the remaining reviewed `t.*` skip reasons so they describe the actual
  current quawk gap instead of a generic “deferred” placeholder

What remains deferred to `T-148`:

- CLI basics, where the remaining anchors still depend on shell-driver or exact
  operand-order handling
- multi-file input processing, where the remaining anchors still depend on
  shell-driver or CLI-sensitive execution shape

## T-148 Result

`T-148` is now complete.

What landed:

- promoted focused runnable shell-driver-derived coverage for:
  - CLI basics via the multiple-`-f` subcase selected from `T.-f-f`
  - multi-file input processing via the first-record `nextfile` subcase
    selected from `T.nextfile`
- kept the remaining One True Awk and gawk shell-driver anchors as reviewed
  skips when the runnable subset no longer needs them

What remains for `T-149`:

- audit the done-line and stop criteria now that every implemented family has
  at least one runnable upstream anchor
- decide whether any remaining skipped corroborating anchors should be promoted
  or explicitly left as permanent reviewed skips

## T-149 Result

`T-149` is now complete.

What landed:

- added executable audit helpers and tests for the completion line:
  - every implemented feature family in the checked-in matrix has at least one
    runnable upstream anchor
  - no runnable upstream case is still classified as `posix-required-fix`
- confirmed the checked-in upstream divergence manifest remains empty, so there
  are no active blocking upstream fixes or stale classified failures
- closed the `P11` upstream-suite growth track: `compat_reference` is the
  compatibility authority, while `compat_corpus` remains supplemental regression
  coverage instead of the sole evidence for any implemented POSIX family

Stop condition after `T-149`:

- upstream-suite growth no longer needs backlog work just to avoid blind spots
- add more upstream cases only when:
  - a new `implemented` claim in [SPEC.md](../SPEC.md) needs coverage
  - a reviewed skipped corroborating anchor becomes clean and worth promoting
  - a new upstream failure needs classification or a fix

## Failure Policy

Not every compatibility failure should be fixed immediately, but every one
should be evaluated explicitly.

Keep two checked-in tracking layers:

1. machine-readable divergence metadata in `tests/upstream/divergences.toml`
2. reviewed notes in this document under `Evaluated Divergences`

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

Current reference workflow:

- `.github/workflows/compat-reference.yml`
- runs on pull requests, pushes to `main`, and manual `workflow_dispatch`
- builds the pinned references with the same repo-managed bootstrap used locally
- runs `uv run pytest -m compat_reference`
- is intentionally optional at the branch-protection level for now

Separate fast CI:

- `.github/workflows/ci-fast.yml`
- runs on pushes, pull requests, and manual `workflow_dispatch`
- covers the `core` pytest suite without bootstrapping pinned reference engines

Promotion criteria:

- the workflow passes on the default branch for at least 10 consecutive runs
  without infrastructure-only flakes
- typical runtime on the default GitHub-hosted runner stays under 15 minutes
  for the active upstream subset
- the pinned One True Awk and gawk bootstrap remains deterministic on
  `ubuntu-latest`
- active non-fix upstream failures, if any, are classified in
  `tests/upstream/divergences.toml` and reviewed in this document
- maintainers explicitly add the `compat-reference` workflow to required branch protection
  only after the criteria above are satisfied

## Evaluated Divergences

This section is the reviewed human-readable companion to
`tests/upstream/divergences.toml`.

Use it to explain why an executed upstream compatibility failure is currently
classified instead of fixed. Each active entry in the manifest must reference a
note marker in this document:

```md
<!-- upstream-divergence: example-note-id -->
## Example divergence family
```

Current state:

- no active evaluated upstream divergences are checked in

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
- `compat_reference` runs selected cases under `quawk`, One True Awk, and gawk
- evaluated divergence metadata and companion notes exist
- CI can run the upstream subset as an optional job

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

## P32 Corroboration Baseline

The remaining POSIX corroboration-only closeout scope is now explicit:

- field rebuild is already implemented, and only the reviewed `p.35` / `t.NF`
  anchors still need promotion or a narrower explicit rationale
- record-target `gsub` remains a narrower reviewed backend skip instead of a
  product gap
- `rand()` remains direct-test-only because the pinned references still
  disagree on deterministic seeded output

This is the final stop line for the implemented POSIX surface before the
remaining corroboration cleanup tasks in `P32`.
