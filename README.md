# quawk

POSIX-oriented AWK compiler and JIT runtime written in Python, using LLVM via `llvmlite`.

## Status

This repository is in active design/prototyping.

Implemented now:
- language, execution, CLI, and testing strategy documents
- phased implementation roadmap and backlog

Planned next:
- Python package/bootstrap scaffold
- lexer/parser implementation
- semantic analysis, LLVM lowering, and JIT execution
- compatibility and differential test harness

## Goals

- POSIX-first AWK behavior and compatibility.
- Realtime parse + JIT for interactive and short-lived workloads.
- Optional compiled artifact caching for fast repeated execution.

## Non-Goals (Current Scope)

- Full GNU awk extension parity on first release.
- A full ahead-of-time native compiler workflow.
- Cross-target portable cache artifacts as a default path.

## Quickstart

Required local toolchain baseline:
- `pyenv`
- Python `3.14.x`
- `venv`
- `direnv`

Recommended bootstrap flow:

```sh
# Pick a concrete patch version in the 3.14 line.
pyenv install 3.14.0
pyenv local 3.14.0

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
# Package bootstrap lands in P0 tasks (pyproject + dev deps).
# Once present:
# pip install -e .[dev]
```

If using `direnv`, add and allow:

```sh
echo 'source .venv/bin/activate' > .envrc
direnv allow
```

## Execution Model

`quawk` compiles and executes AWK programs in realtime:

1. Parse and validate source.
2. Lower to IR and JIT compile.
3. Execute immediately.
4. Optionally cache compiled artifacts for future runs.

Caching is planned as:
- in-memory cache (within process)
- disk cache (across process invocations)
- strict key-based invalidation for correctness

See [EXECUTION.md](/Users/fred/dev/quawk/EXECUTION.md) for detailed behavior.

## Language Support

Target baseline:
- POSIX AWK core language
- pattern-action programs
- function definitions
- standard expression/operator behavior, including implicit concatenation

Grammar and disambiguation details:
- [GRAMMAR.md](/Users/fred/dev/quawk/GRAMMAR.md)

Current limitations:
- runtime executable is not implemented yet
- compatibility corpus is still in bootstrap phase

## Architecture Overview

High-level pipeline:

1. Source normalization and lexing.
2. Parsing to AST.
3. Semantic validation and normalization.
4. LLVM lowering and JIT materialization (`llvmlite`).
5. Execution and cache store.

Core project documents:
- [BUILD.md](/Users/fred/dev/quawk/BUILD.md)
- [STANDARDS.md](/Users/fred/dev/quawk/STANDARDS.md)
- [PLAN.md](/Users/fred/dev/quawk/PLAN.md)
- [TASKS.md](/Users/fred/dev/quawk/TASKS.md)
- [CLI.md](/Users/fred/dev/quawk/CLI.md)
- [CI.md](/Users/fred/dev/quawk/CI.md)
- [STRATEGY.md](/Users/fred/dev/quawk/STRATEGY.md)
- [EXECUTION.md](/Users/fred/dev/quawk/EXECUTION.md)
- [TESTING.md](/Users/fred/dev/quawk/TESTING.md)
- [TEST_SPEC.md](/Users/fred/dev/quawk/TEST_SPEC.md)

## Conformance and Testing

Test strategy baseline:
- `pytest` for unit/integration tests
- `hypothesis` for property testing
- differential testing against `one-true-awk` and `gawk --posix`
- strict phase-based TDD (`xfail` bootstrap -> burn down to `pass`)

See:
- [TESTING.md](/Users/fred/dev/quawk/TESTING.md)
- [TEST_SPEC.md](/Users/fred/dev/quawk/TEST_SPEC.md)
- [CI.md](/Users/fred/dev/quawk/CI.md)

## Repository Layout

Target structure during implementation:

```text
.
├── pyproject.toml
├── README.md
├── BUILD.md
├── PLAN.md
├── TASKS.md
├── CLI.md
├── CI.md
├── TESTING.md
├── TEST_SPEC.md
├── EXECUTION.md
├── STANDARDS.md
├── GRAMMAR.md
├── src/
├── tests/
├── examples/
└── scripts/
```

## Compatibility Matrix

| Component | Supported | Notes |
|---|---|---|
| OS | Linux, macOS | CI matrix expands over time |
| Architecture | x86_64, aarch64 | As available in CI provider |
| Python | 3.14.x | Managed by `pyenv` |
| LLVM binding | `llvmlite` | Used for JIT path |

## FAQ

Q: Is this a drop-in replacement for all AWK variants?  
A: Not yet. The target is POSIX behavior first; extension coverage is phased in.

Q: Does `quawk` cache compiled results?  
A: Planned yes, with strict invalidation keyed by source and runtime/toolchain configuration.

## Contributing

Contributions are welcome. Please open an issue with:
- use case
- expected behavior
- POSIX reference (if applicable)

Contributor workflow details are tracked in `TASKS.md` and will be finalized with initial implementation bootstrap.

## License

BSD 3-Clause. See [LICENSE](/Users/fred/dev/quawk/LICENSE).
