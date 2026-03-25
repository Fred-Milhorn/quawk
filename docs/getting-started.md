# Getting Started

This guide covers local setup and the first commands contributors should expect to use while `quawk` continues active implementation.

## Toolchain Baseline

Required:
- `uv`
- Python `3.14.x`
- LLVM command-line tools on `PATH`:
  - `lli` for executing generated LLVM IR
  - `clang`, `llvm-as`, and `llvm-link` for the current record/input execution path
  - `llc` for `quawk --asm`

`quawk` uses a Python-native build model:

1. environment/toolchain layer: `uv` + Python `3.14.x` + project-local `.venv`
2. source/dependency layer: `pyproject.toml` with pinned development and test dependencies

Toolchains are not vendored in this repo.

`quawk` shells out to system LLVM binaries. If your LLVM install is not on `PATH` by default, export the directory containing these tools before running the CLI or test suite.

## Bootstrap

Recommended bootstrap flow:

```sh
uv python install 3.14
uv venv --python 3.14 .venv
source .venv/bin/activate
```

Install the project and development dependencies:

```sh
uv pip install -e .[dev]
```

## Common Commands

After dependency bootstrap:

```sh
quawk --help
pytest
yapf --diff --recursive src tests
ruff check .
mypy src
```

The commands above should run from a clean scaffold checkout after `uv pip install -e .[dev]`.

## Local Outputs

These local outputs should be ignored by Git as needed:
- `.venv/`
- `.pytest_cache/`
- `build/`
- `dist/`
- coverage, type-check, and lint artifacts as configured by tools

## Repository Shape

Current state:
- committed `src/quawk` package with a working CLI, parser, semantic checks, and execution backends
- documentation, conformance fixtures, and corpus tests alongside the implementation
- `examples/` is present for manual inspection and smoke programs
- compatibility coverage is still growing; the roadmap remains the source of truth for next increments

Target implementation layout:

```text
.
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── docs/
├── src/
│   └── quawk/
├── tests/
├── examples/
└── third_party/    # only when source vendoring is required
```

Use `third_party/` only when source vendoring is unavoidable. Do not vendor Python toolchains, LLVM distributions, or package manager caches.

## Next Reads

- [design.md](design.md) for architecture, grammar, execution, and CLI design
- [testing.md](testing.md) for TDD, compatibility, and CI expectations
- [roadmap.md](roadmap.md) for phased implementation work and active tasks
