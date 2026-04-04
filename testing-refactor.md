# Testing Refactor Plan

This document records a proposed cleanup of `quawk`'s testing entrypoints,
pytest markers, and compatibility-suite naming.

It is planning-only. It does not imply that the changes should be implemented
now.

## Goal

Make the test surfaces easier to understand and easier to run by:
- replacing negative or misleading names
- reducing overlap between local compatibility targets
- clarifying which commands are primary test gates versus manual harness tools

## Current Problems

### `not compat` is a poor name

The current fast CI/default command is:

```sh
uv run pytest -q -m "not compat"
```

That name describes the suite only by exclusion.

What it actually does:
- runs the core repo test suite
- includes lexer, parser, semantic, runtime, backend, CLI, audit, doc, smoke,
  and helper-module tests
- excludes only the compatibility suites

This should be renamed to a positive name.

### `compat_upstream` is misleading

One True Awk and gawk are not upstream dependencies of `quawk`.

They are:
- reference implementations
- comparison oracles
- pinned external compatibility targets

So `compat_upstream` should be renamed to something that reflects that role.

### Local compatibility surfaces overlap

There are currently three local corpus-related surfaces:
- single-engine local corpus execution
- local differential baseline cases
- local differential supported cases

The two local differential pytest files are structurally the same test with
different case selectors. That overlap should be reduced.

### Smoke selection is inconsistent

The repo currently uses both:
- the file path `tests/test_p12_release_smoke.py`
- the marker `smoke`

This should be standardized to one documented release-smoke entrypoint.

## Proposed Naming

### Pytest markers

Keep:
- `compat` as the umbrella compatibility marker
- `smoke` if smoke tests remain a marker-based surface

Rename:
- `compat_upstream` -> `compat_reference`
- `compat_local` -> `compat_corpus`

Add:
- `core` for the default fast repo test surface

Intent:
- `core` means the main fast validation suite
- `compat_reference` means differential tests against reference engines
- `compat_corpus` means repo-owned supplemental compatibility corpus coverage

## Proposed Test Surfaces

Primary commands:

```sh
uv run pytest -q -m core
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
uv run pytest -m compat
uv run pytest -q
```

Optional release-smoke command, if smoke remains marker-based:

```sh
uv run pytest -q -m smoke
```

Meaning:
- `core`: default fast suite for branch pushes and local iteration
- `compat_reference`: heavy reference-engine differential gate
- `compat_corpus`: supplemental repo-owned compatibility regression gate
- `compat`: umbrella compatibility run
- full `pytest`: everything

## Corpus and Compatibility Cleanup

### Keep single-engine corpus coverage separate

Keep the single-engine corpus execution test as a distinct surface.

Reason:
- it checks repo-owned expected `quawk` behavior directly
- it is not the same as the differential compatibility suites

### Merge the two local differential corpus pytest files

Replace the current split between:
- local baseline differential corpus coverage
- supported local differential corpus coverage

with one shared local differential compatibility surface.

The merged test should:
- use one selector or parametrization strategy
- keep case-grouping semantics visible in IDs or tags
- avoid maintaining two near-identical pytest entrypoints

### Demote `corpus` CLI to a harness tool

Keep the `corpus` console command, but document it as a manual harness and case
inspection tool, not as a primary test gate.

Examples:
- `corpus --list`
- `corpus demo_case`
- `corpus --differential demo_case`

## CI and Docs Changes

### CI

Update CI commands to use the new marker names:
- `ci-fast`: `uv run pytest -q -m core`
- reference compatibility workflow: `uv run pytest -m compat_reference`

### Docs

Update:
- `docs/testing.md` as the primary narrative source of truth
- `pyproject.toml` marker declarations
- `README.md` only where top-level test commands are mentioned
- `docs/compatibility.md` where suite names are referenced
- `docs/release-checklist.md` if smoke-entrypoint wording changes

## Assumptions and Defaults

- `core` is the replacement for the current `not compat` selection
- `compat_reference` is the replacement for `compat_upstream`
- `compat_corpus` is the replacement for `compat_local`
- `compat` remains the umbrella marker
- the `corpus` CLI stays available, but is documented as tooling rather than a
  first-class test gate
- single-engine corpus coverage remains separate from differential corpus
  coverage
- the two local differential corpus pytest files should be merged
