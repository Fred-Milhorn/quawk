# Build and Repository Layout

This document defines how `quawk` should be built and how the repository should be organized.

## Build System Policy

`quawk` uses a Python-native build model:

1. Environment/toolchain layer: `pyenv` + Python `3.14.x`, project-local `venv`, optional `direnv`
2. Source/dependency layer: `pyproject.toml` with pinned development/test dependencies

Rationale:
- local contributor workflow should be simple and explicit
- package/test tooling should be standard Python and editor-friendly
- LLVM JIT integration is handled via `llvmlite`

## Toolchain Policy

Toolchains are not vendored in this repo.

Required:
- Python `3.14.x` (managed via `pyenv`)
- `pip` in project `venv`

Required Python package dependencies:
- runtime: `llvmlite` (as implementation progresses)
- testing: `pytest`, `hypothesis`

Optional:
- `direnv` for shell activation

## Output Directories

Local outputs:
- `.venv/` local virtual environment
- `.pytest_cache/` pytest cache
- `build/`, `dist/` package artifacts when built
- coverage/type/lint artifacts as configured by tools

These should be ignored by Git as needed.

## Vendoring Policy

Use `third_party/` only when source vendoring is unavoidable.

Do not vendor:
- Python interpreter toolchains
- LLVM distributions
- package manager caches

If vendoring is necessary:
- include upstream provenance and license text
- keep vendored code minimal and explicit

## Recommended Repository Structure

```text
.
├── pyproject.toml
├── README.md
├── BUILD.md
├── CI.md
├── PLAN.md
├── TASKS.md
├── CLI.md
├── TESTING.md
├── TEST_SPEC.md
├── EXECUTION.md
├── STANDARDS.md
├── GRAMMAR.md
├── src/
│   └── quawk/
│       ├── __init__.py
│       ├── cli.py
│       ├── frontend/
│       │   ├── lexer.py
│       │   ├── parser.py
│       │   └── ast.py
│       ├── sema/
│       ├── backend/
│       │   └── llvm/
│       └── runtime/
├── tests/
│   ├── parser/
│   ├── runtime/
│   ├── compat/
│   └── fixtures/
├── examples/
├── scripts/
└── third_party/    # only when source vendoring is required
```

## Build and Check Commands

Bootstrap:

```sh
pyenv install 3.14.0
pyenv local 3.14.0
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# once pyproject is in place:
# pip install -e .[dev]
```

Common commands (after dependency bootstrap):

```sh
# run tests
pytest

# run property tests (subset marker example)
pytest -m property

# run compatibility smoke tests
pytest tests/compat -m smoke
```

Formatting/lint/type-check commands are defined by CI policy in [CI.md](/Users/fred/dev/quawk/CI.md).

## Near-Term Implementation Plan

1. Add `src/quawk/` package skeleton and CLI entrypoint.
2. Add `tests/` skeleton aligned with [TESTING.md](/Users/fred/dev/quawk/TESTING.md).
3. Add `pyproject.toml` with runtime + dev/test dependencies.
4. Add Python-based phase-gate validator in `scripts/`.
5. Wire CI checks for format/lint/type/test/gate.

Track progress in:
- [PLAN.md](/Users/fred/dev/quawk/PLAN.md) for phase milestones
- [TASKS.md](/Users/fred/dev/quawk/TASKS.md) for task-level execution
