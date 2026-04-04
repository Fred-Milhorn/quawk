# Repository Refactor Plan

This document records a proposed repository-layout refactor for `quawk`.

It is planning-only. It does not imply that the refactor should be implemented
now.

## Goal

Clean up the repo layout so user-facing product code stays distinct from
compatibility and corpus tooling.

Current concern:
- `scripts/upstream_compat.py` is the only file in `scripts/`
- it is only a thin wrapper over package code in `src/quawk/upstream_compat.py`
- the upstream and corpus modules in `src/quawk/` are legitimate package code,
  but they are flat in the top-level namespace rather than grouped under a
  dedicated compatibility area

## Proposed End State

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

## Implementation Plan

### 1. Create a dedicated compatibility namespace

Add `src/quawk/compat/` and move these modules under it:
- `corpus.py`
- `upstream_compat.py`
- `upstream_inventory.py`
- `upstream_suite.py`
- `upstream_divergence.py`
- `upstream_audit.py`

The top-level `quawk` package should remain focused on product/runtime/compiler
code.

### 2. Keep the product CLI at top level

Leave `src/quawk/cli.py` where it is.

Intent:
- `quawk` remains the user-facing product command
- `quawk.compat.*` becomes internal and contributor-oriented tooling

### 3. Replace the `scripts/` wrapper

Delete `scripts/upstream_compat.py`.

Replace it with a package-owned entrypoint:
- add a console script in `pyproject.toml`, for example:
  - `quawk-upstream = "quawk.compat.upstream_compat:main"`
- optionally also support:
  - `python -m quawk.compat.upstream_compat`

This removes the special-case wrapper file and makes the command shape match the
rest of the package.

### 4. Keep the `corpus` command stable

Keep the existing `corpus` console script, but repoint it to:
- `quawk.compat.corpus:main`

Do not rename the user-facing command unless docs and workflows are being
cleaned up in the same change.

### 5. Update imports in one pass

Change internal imports to `quawk.compat.*`.

Change test imports the same way.

Do not leave compatibility shims unless a temporary migration period is
deliberately needed.

### 6. Update docs and CI references

Replace:

```sh
uv run python scripts/upstream_compat.py bootstrap
```

with either:

```sh
uv run quawk-upstream bootstrap
```

or:

```sh
uv run python -m quawk.compat.upstream_compat bootstrap
```

Update these references together:
- `README.md`
- `docs/getting-started.md`
- `docs/compatibility.md`
- `.github/workflows/compat-upstream.yml`

### 7. Verify in focused layers

Run focused compatibility-tooling coverage first:
- `tests/test_upstream_compat.py`
- `tests/test_corpus.py`
- `tests/test_corpus_differential.py`
- `tests/test_upstream_inventory.py`
- `tests/test_upstream_suite.py`
- `tests/test_upstream_divergence.py`
- `tests/test_upstream_audit.py`

Then run broader validation:
- `uv run pytest -q -m "not compat"`
- `uv run pytest -m compat_upstream`

## Assumptions and Defaults

- top-level `quawk` remains the product namespace
- compatibility and corpus code should be grouped under `quawk.compat`
- the `corpus` command stays named `corpus`
- the standalone `scripts/` wrapper should be removed rather than expanded
- package-owned entrypoints are preferred over repo-root helper scripts for this
  tooling
