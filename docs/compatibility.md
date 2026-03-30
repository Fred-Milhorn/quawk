# Compatibility Plan

This document is the implementation plan for the next `P11` compatibility
transition. The current repo-owned corpus remains useful, but it is no longer
the primary compatibility authority. The primary compatibility signal should
come from pinned upstream suites for One True Awk and gawk.

## Goal

Move `quawk` compatibility work from:

- a hand-authored local corpus
- a differential runner that treats host `awk` as `one-true-awk`

to:

- pinned upstream source trees under `third_party/`
- repo-managed local builds of One True Awk and gawk
- compatibility runs derived from the respective upstream test suites
- explicit evaluation of failures that are not immediate fix targets

## End State

The target steady state is:

- `third_party/onetrueawk` and `third_party/gawk` are pinned submodules
- one repo-managed bootstrap command builds local reference binaries into ignored paths under `build/`
- required compatibility runs do not depend on whatever `awk` is on `PATH`
- the upstream-suite-derived compatibility surface is the primary compatibility gate
- the current repo-owned corpus remains as a fast supplemental regression suite
- every observed compatibility failure is either fixed or explicitly evaluated in checked-in metadata and companion docs

## Local Workflow

Local compatibility should not require a global install of One True Awk.
Developers should only need the native build toolchain required to build the
upstream sources.

Recommended local flow:

```sh
git submodule update --init --recursive
uv run python scripts/upstream_compat.py bootstrap
uv run pytest -m compat_upstream
```

Expected behavior:

- `bootstrap` builds deterministic local reference binaries for One True Awk and gawk under ignored `build/` paths
- the compatibility harness resolves only those pinned binaries by default
- optional override env vars may exist for debugging or CI, but the normal local path is repo-managed and deterministic

## Design

### 1. Reframe the local corpus

Keep the checked-in `tests/corpus/` suite, but change its role:

- it is a supplemental fast regression and smoke suite
- it is not the primary compatibility authority
- it should stop making repo-wide compatibility claims on its own

The corpus remains useful for:

- small end-to-end regressions
- feature-oriented fixtures that are easy to review in-repo
- quick local iteration before running the slower upstream-suite-derived coverage

### 2. Pin upstream sources

Track the upstream projects directly in the repo:

- `third_party/onetrueawk`
- `third_party/gawk`

Policy:

- pin explicit commits through Git submodules
- do not rely on host package-manager versions for required compatibility behavior
- treat the pinned upstream commits as part of the compatibility contract

### 3. Build repo-managed reference binaries

Add one repo-owned bootstrap/build entrypoint, implemented as a small checked-in
Python or shell harness, that:

- initializes expected build directories under ignored `build/` paths
- builds One True Awk from the pinned source tree
- builds gawk from the pinned source tree
- exposes stable wrapper or symlink paths such as `build/upstream/bin/one-true-awk` and `build/upstream/bin/gawk`
- validates that the expected binaries exist before compatibility tests run

Reference-engine resolution rules:

- never use host `awk` as a stand-in for One True Awk
- never treat a package-manager `gawk` as the required reference by default
- fail clearly when the repo-managed reference binaries have not been bootstrapped

### 4. Add an upstream suite inventory layer

The upstream suites are broader than the initial `quawk` compatibility target,
so the repo needs an explicit checked-in inventory of what is run and what is
currently skipped.

Add machine-readable suite inventory metadata that records, for each upstream
case:

- suite name
- upstream case ID
- status: `run` or `skip`
- reason for a skip
- adapter type or harness shape
- tags such as `posix`, `gnu-extension`, `platform-specific`, or `unsupported-input-shape`

Selection policy:

- start with portable, POSIX-relevant cases from both upstream suites
- skip cases that are clearly GNU-extension-only, debugger-only, locale-heavy, dynamic-extension-driven, platform-specific, or otherwise outside the first compatibility target
- keep skipped cases explicit and reviewable rather than silently ignoring them

### 5. Run upstream-suite-derived compatibility checks

Add a compatibility harness that:

- discovers the repo-classified upstream cases from the pinned source trees
- executes the selected cases under `quawk`
- executes the same cases under the pinned One True Awk and gawk binaries
- normalizes outputs conservatively for deterministic comparison
- reports missing references, reference disagreement, `quawk` mismatches, and stale divergence entries clearly

Required pytest surfaces should split into:

- `compat_upstream`
  - upstream-suite-derived compatibility gate
- `compat_local`
  - current small repo-owned corpus

An umbrella `compat` marker may still include both, but the primary gate should
move to `compat_upstream`.

### 6. Evaluate failures explicitly

Not every compatibility failure should be fixed immediately, but every one
should be evaluated explicitly.

Keep two checked-in tracking layers:

1. Machine-readable divergence metadata for executed upstream cases
2. Human-readable compatibility notes for the active divergence families

Each divergence entry should record:

- suite name
- case ID
- classification
- decision
- short summary
- last verified upstream commit

Required classifications:

- `posix-required-fix`
- `known-gap`
- `intentional-quawk-extension`
- `gnu-extension-out-of-scope`
- `platform-specific`
- `reference-disagreement`
- `wont-fix`

Gate policy:

- unclassified failures fail the required suite
- stale divergence entries fail the required suite
- `posix-required-fix` remains a hard failure
- the other classes are allowed only after explicit evaluation and documentation

### 7. Promote CI in phases

The upstream-suite workflow should not become a required CI gate in a single
step.

Promotion sequence:

1. land the submodules, bootstrap command, and local harness
2. add an optional CI job that builds the references and runs the selected upstream compatibility slice
3. stabilize runtime, flake profile, and divergence workflow
4. promote the upstream compatibility job to required

During the transition:

- keep the local corpus green
- keep the upstream gate authoritative once promoted
- do not regress back to host `awk` aliasing for convenience

## Acceptance Criteria

This transition is complete when:

- `quawk` compatibility no longer depends on host `awk`
- One True Awk and gawk are both built from pinned upstream sources in normal local workflow
- upstream-suite-derived compatibility runs exist for both upstream projects
- the local corpus is clearly documented as supplemental rather than authoritative
- executed compatibility failures are either fixed or explicitly evaluated in checked-in metadata and docs
- CI can run the pinned upstream compatibility workflow end to end

## Implementation Phases

### Phase 1: Policy reset and reproducible references

Complete when:

- docs stop referring to host `awk` as `one-true-awk`
- the role of the local corpus is explicitly reduced to supplemental coverage
- pinned upstream submodules and repo-managed bootstrap expectations are documented

### Phase 2: Upstream suite ingestion

Complete when:

- pinned upstream trees are discoverable from the repo
- the repo has a checked-in inventory of selected and skipped upstream cases
- the initial portable, POSIX-relevant execution slice is defined for both upstream suites

### Phase 3: Upstream compatibility execution and divergence evaluation

Complete when:

- selected upstream cases run under `quawk`, One True Awk, and gawk
- failures are reported through the checked-in divergence workflow
- stale or unclassified divergence states fail visibly

### Phase 4: CI promotion

Complete when:

- the upstream compatibility workflow runs in CI
- the job is promoted from optional to required once stable
- the local corpus remains available as a fast supplemental suite
