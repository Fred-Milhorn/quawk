# Getting Started

This guide covers local setup both for people who want to run `quawk` from a
local clone and for contributors who want the full development toolchain.

## Toolchain Baseline

Required:
- `uv`
- Python `3.14.x`
- LLVM command-line tools on `PATH`:
  - `lli` for executing generated LLVM IR
  - `clang`, `llvm-as`, and `llvm-link` for the current record/input execution path
  - `llc` for `quawk --asm`

Needed for pinned upstream compatibility references:
- `make`
- a working C toolchain
- a POSIX shell environment capable of running gawk's `configure`

`quawk` uses a Python-native build model:

1. environment/toolchain layer: `uv` + Python `3.14.x` + project-local `.venv`
2. source/dependency layer: `pyproject.toml` with pinned development and test dependencies

Toolchains are not vendored in this repo.

`quawk` shells out to system LLVM binaries. If your LLVM install is not on `PATH` by default, export the directory containing these tools before running the CLI or test suite.

## Install `quawk` From A Local Clone

For a local user install on macOS:

```sh
git clone https://github.com/Fred-Milhorn/quawk.git
cd quawk
brew install llvm
uv python install 3.14
uv tool install --python 3.14 --editable .
uv tool update-shell
quawk --help
quawk 'BEGIN { print "hello" }'
```

This installs the `quawk` console script as a user-facing tool, instead of into
a repo-local virtualenv.

You also need the LLVM binaries on your login-shell `PATH`. For a standard Apple
Silicon Homebrew install:

```sh
echo 'export PATH="/opt/homebrew/opt/llvm/bin:$PATH"' >> ~/.zprofile
```

If your Homebrew prefix is different, add the matching LLVM `bin/` directory
instead.

`uv tool update-shell` updates your shell config so the `quawk` executable
itself remains on `PATH` after logout/login.

## Contributor Bootstrap

If you want the editable development environment instead of only the installed
CLI:

```sh
uv python install 3.14
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -e .[dev]
```

Initialize the pinned upstream compatibility sources:

```sh
git submodule update --init --recursive
```

Build the local One True Awk and gawk compatibility references when working on
the upstream compatibility transition:

```sh
uv run quawk-upstream bootstrap
uv run pytest -m compat_reference
```

GitHub Actions runs the fast `core` pytest suite in
`.github/workflows/ci-fast.yml` and the heavier reference differential command
in `.github/workflows/compat-reference.yml`.

## Common Commands

After dependency bootstrap:

```sh
uv run quawk --help
uv run pytest
uv run yapf --diff --recursive src tests
uv run ruff check .
uv run mypy src
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
- pinned upstream compatibility source trees under `third_party/`
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
└── third_party/    # pinned upstream source trees when required by compatibility work
```

Use `third_party/` only for pinned upstream sources that are part of the
compatibility workflow. Do not vendor Python toolchains, LLVM distributions, or
package manager caches.

## Next Reads

- [design.md](design.md) for architecture, grammar, execution, and CLI design
- [testing.md](testing.md) for TDD, compatibility, and CI expectations
- [roadmap.md](roadmap.md) for phased implementation work and active tasks
