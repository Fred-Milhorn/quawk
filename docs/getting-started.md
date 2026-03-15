# Getting Started

This guide covers local setup and the first commands contributors should expect to use while `quawk` moves from design into implementation.

## Toolchain Baseline

Required:
- `uv`
- Python `3.14.x`

`quawk` uses a Python-native build model:

1. environment/toolchain layer: `uv` + Python `3.14.x` + project-local `.venv`
2. source/dependency layer: `pyproject.toml` with pinned development and test dependencies

Toolchains are not vendored in this repo.

## Bootstrap

Recommended bootstrap flow:

```sh
uv python install 3.14
uv venv --python 3.14 .venv
source .venv/bin/activate
```

Once `pyproject.toml` is present:

```sh
uv pip install -e .[dev]
```

## Common Commands

After dependency bootstrap:

```sh
pytest
pytest -m property
pytest tests/compat -m smoke
ruff format --check .
ruff check .
mypy src
python scripts/check_phase_gate.py
```

Not every command is runnable yet because the implementation scaffold is still being built. The command list here reflects the intended contributor workflow and CI gates.

## Local Outputs

These local outputs should be ignored by Git as needed:
- `.venv/`
- `.pytest_cache/`
- `build/`
- `dist/`
- coverage, type-check, and lint artifacts as configured by tools

## Repository Shape

Current state:
- docs-first repository with design, testing, and roadmap material
- implementation scaffold is planned but not yet committed

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
├── scripts/
└── third_party/    # only when source vendoring is required
```

Use `third_party/` only when source vendoring is unavoidable. Do not vendor Python toolchains, LLVM distributions, or package manager caches.

## Next Reads

- [design.md](design.md) for architecture, grammar, execution, and CLI design
- [testing.md](testing.md) for TDD, compatibility, and CI expectations
- [roadmap.md](roadmap.md) for phased implementation work and active tasks
