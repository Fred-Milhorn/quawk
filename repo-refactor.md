# Repository Refactor

This document records the completed repository-layout refactor for `quawk`.

## Goal

Clean up the repo layout so user-facing product code stays distinct from
compatibility and corpus tooling.

Result:
- product/runtime/compiler code stays at the top level under `src/quawk/`
- compatibility and corpus tooling now live under `src/quawk/compat/`
- the singleton `scripts/upstream_compat.py` wrapper is gone
- package-owned entrypoints replace the old repo-root wrapper command

## Final State

- keep the product CLI in `src/quawk/cli.py`
- move compatibility and corpus tooling into `src/quawk/compat/`
- remove the singleton `scripts/upstream_compat.py` wrapper
- replace the wrapper with a package-owned entrypoint

Target structure:

```text
src/quawk/
├── cli.py
├── ...
└── compat/
    ├── __init__.py
    ├── corpus.py
    ├── upstream_compat.py
    ├── upstream_inventory.py
    ├── upstream_suite.py
    ├── upstream_divergence.py
    └── upstream_audit.py
```

Package-owned commands:
- `corpus`
- `quawk-upstream`
- `python -m quawk.compat.upstream_compat`

## Resulting Decisions

### 1. Dedicated compatibility namespace

`src/quawk/compat/` now holds:
- `corpus.py`
- `upstream_compat.py`
- `upstream_inventory.py`
- `upstream_suite.py`
- `upstream_divergence.py`
- `upstream_audit.py`

The top-level `quawk` package should remain focused on product/runtime/compiler
code.

### 2. Product CLI stays at top level

Leave `src/quawk/cli.py` where it is.

Intent:
- `quawk` remains the user-facing product command
- `quawk.compat.*` becomes internal and contributor-oriented tooling

### 3. Wrapper script removed

- `scripts/upstream_compat.py` was deleted
- `quawk-upstream = "quawk.compat.upstream_compat:main"` is the package-owned
  console script
- `python -m quawk.compat.upstream_compat` is also supported

### 4. `corpus` stays stable

- the existing `corpus` console script now resolves to
  `quawk.compat.corpus:main`
- the user-facing command name did not change

### 5. Imports and references moved together

- internal imports now use `quawk.compat.*`
- tests, docs, and workflow references were moved to the new namespace and
  command surfaces in the same refactor wave
- the temporary top-level compatibility wrappers used during the transition are
  gone

### 6. Docs and CI use package-owned commands

- contributor docs and CI now use `uv run quawk-upstream bootstrap`
- module-oriented documentation also accepts
  `uv run python -m quawk.compat.upstream_compat bootstrap`

## Verification Targets

Run focused compatibility-tooling coverage first:
- `tests/test_upstream_compat.py`
- `tests/test_corpus.py`
- `tests/test_corpus_differential.py`
- `tests/test_upstream_inventory.py`
- `tests/test_upstream_suite.py`
- `tests/test_upstream_divergence.py`
- `tests/test_upstream_audit.py`

Then run broader validation:
- `uv run pytest -q -m core`
- `uv run pytest -m compat_reference`

## Steady-State Assumptions

- top-level `quawk` remains the product namespace
- compatibility and corpus code should be grouped under `quawk.compat`
- the `corpus` command stays named `corpus`
- package-owned entrypoints are preferred over repo-root helper scripts for this
  tooling
