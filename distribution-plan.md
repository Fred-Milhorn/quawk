# Distribution Plan

This document records the current packaging and distribution plan for `quawk`.

It is intentionally planning-only. It does not imply that the work should be
implemented now.

## Summary

Package `quawk` in two parallel lanes:

1. PyPI as the canonical distribution
   Publish `quawk` as a Python CLI package.
2. A dedicated Homebrew tap as the convenience installer
   Ship a formula in an owned tap that installs the Python package into an
   isolated virtual environment and declares the LLVM dependency explicitly.

This fits the current repository state:
- `quawk` is already packaged as a Python project in `pyproject.toml`
- the CLI depends on external LLVM tools on `PATH`
- there is no standalone binary packaging pipeline today

## Packaging Model

### PyPI package

Treat PyPI as the source of truth for versioned releases.

Implementation shape:
- keep `quawk` as a normal Python package built from `pyproject.toml`
- add complete package metadata:
  - authors and maintainers
  - license expression
  - project URLs
  - classifiers
  - keywords
- keep `quawk` and `corpus` as console scripts
- keep package data for `runtime/*.c` and `runtime/*.h`
- document `uv tool install quawk` as the primary install path
- document `pipx install quawk` as a secondary fallback
- document runtime prerequisites explicitly:
  - Python `3.14`
  - system LLVM tools: `lli`, `clang`, `llvm-as`, `llvm-link`, `llc`

Release artifacts:
- publish an sdist and wheel to PyPI
- do not claim self-contained execution from the wheel
- treat the wheel as a Python CLI package that shells out to system LLVM

### Homebrew tap

Use a custom tap, not `homebrew-core`.

Implementation shape:
- create a tap repo such as `Fred-Milhorn/homebrew-quawk`
- add a formula that:
  - depends on `python@3.14`
  - depends on `llvm`
  - installs `quawk` from the published PyPI artifact into a virtualenv
- wrap the executable so LLVM tools are discoverable
- prefer prepending Homebrew LLVM's `bin` directory in the wrapper so users do
  not need to edit `PATH`
- pin the formula to the released PyPI artifact URL and SHA256, not to a moving
  Git checkout

User-facing install target:

```sh
brew install Fred-Milhorn/quawk/quawk
```

### Explicit non-goal for this phase

Do not plan a standalone native binary or bundled executable distribution in
this phase.

Reasons:
- Python is still the compiler and orchestration layer
- runtime behavior still depends on external LLVM tools
- a true standalone artifact would require bundling or replacing the LLVM
  toolchain contract

If needed later, treat standalone distribution as a separate product phase.

## Required Changes Before Release Packaging

### Package and release metadata

Update the package surface so it is publishable:
- make `pyproject.toml` release-grade
- ensure one authoritative version source exists and matches the release
  checklist
- add build commands to the release process:
  - `python -m build`
  - package smoke install in a clean environment
- add install instructions for PyPI and Homebrew to `README.md`

### Documentation contract

Align public docs around actual install paths:
- `README.md`
  - install with `uv tool install`
  - install with the Homebrew tap
  - LLVM prerequisite guidance per platform
- `docs/getting-started.md`
  - separate contributor bootstrap from end-user installation
- `docs/release-checklist.md`
  - add package build, PyPI upload, and tap update steps
- optionally add `docs/install.md` if contributor setup and user install should
  be separated cleanly

### CI and release automation

Add release validation for packaging:
- build sdist and wheel on release candidates or tags
- smoke-test installation from built artifacts
- verify `quawk --help` and one tiny program run after install
- run packaging smoke coverage on Linux and macOS at minimum

Recommended release flow:
1. cut tag
2. build sdist and wheel
3. upload to PyPI
4. update the Homebrew tap formula to the new PyPI artifact URL and SHA
5. publish GitHub release notes

## Test Plan

Before calling packaging complete, require these checks.

### Package integrity

- `python -m build` succeeds
- the wheel contains the Python package and runtime C/header assets
- `uv tool install --from dist/*.whl quawk` works in a clean environment

### Installed CLI behavior

- `quawk --help` works after install
- a tiny `BEGIN { print 1 }` program runs
- failure mode is clear when LLVM tools are missing

### Homebrew install behavior

- the formula installs cleanly on macOS
- formula-installed `quawk --help` works
- formula-installed `quawk 'BEGIN { print 1 }'` works without manual LLVM path
  edits
- uninstall is clean

### Regression coverage

- keep the existing non-compat and upstream compatibility suites as release
  gates
- add one packaging smoke test for each install path:
  - PyPI-style install smoke
  - Homebrew formula smoke

## Assumptions and Defaults

- canonical distribution: PyPI
- convenience installer: custom Homebrew tap
- primary user install command: `uv tool install quawk`
- secondary fallback install command: `pipx install quawk`
- Homebrew strategy: install the Python package in a virtualenv, not a bespoke
  binary bundle
- LLVM remains an external system dependency
- standalone native binary distribution is out of scope for this plan
