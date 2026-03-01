# quawk

POSIX-oriented AWK compiler and JIT runtime written in Standard ML (MLton) with an LLVM-based backend.

## Status

This repository is currently in active design/prototyping.

- Implemented now:
  - language and parsing docs
  - execution and caching strategy docs
- Planned next:
  - lexer/parser implementation
  - LLVM IR generation and JIT execution
  - conformance and integration tests

## Goals

- POSIX-first AWK behavior and compatibility.
- Realtime parse + JIT for interactive and short-lived workloads.
- Optional compiled artifact caching for fast repeated execution.

## Non-Goals (Current Scope)

- Full GNU awk extension parity on day one.
- A full ahead-of-time native compiler workflow.
- Cross-target portable cache artifacts as a default path.

## Quickstart

Prerequisites:

- MLton: `TODO_VERSION`
- LLVM toolchain: `TODO_VERSION`
- Platform(s): `TODO_PLATFORMS`

Build:

```sh
# TODO: add build command once project layout is in place
```

Run (example):

```sh
# TODO: add executable command
# Example AWK program:
# BEGIN { print "hello, world" }
```

## Execution Model

`quawk` is designed to compile and execute AWK programs in realtime:

1. Parse and validate source.
2. Lower to IR and JIT-compile.
3. Execute immediately.
4. Optionally cache compiled artifacts for future runs.

Caching is planned as:

- in-memory cache (within process)
- disk cache (across process invocations)
- strict key-based invalidation for correctness

See [EXECUTION.md](/Users/fred/dev/quawk/EXECUTION.md) for detailed behavior.

## Language Support

Target language baseline:

- POSIX AWK core language
- pattern-action programs
- function definitions
- standard expression/operator behavior, including implicit concatenation

Grammar and disambiguation details:

- [GRAMMAR.md](/Users/fred/dev/quawk/GRAMMAR.md)

Current limitations:

- `TODO: list unsupported POSIX corners and extension gaps`

## Architecture Overview

High-level frontend/backend plan:

1. Source normalization and lexing.
2. Parsing to AST.
3. Semantic validation.
4. LLVM lowering and JIT materialization.
5. Execution and cache store.

Strategy details:

- [STRATEGY.md](/Users/fred/dev/quawk/STRATEGY.md)
- [EXECUTION.md](/Users/fred/dev/quawk/EXECUTION.md)

## Conformance and Testing

Test strategy (planned):

- parser unit tests (grammar and disambiguation edge cases)
- semantic/runtime behavioral tests
- compatibility checks against reference AWK implementations

Run tests:

```sh
# TODO: add test command(s)
```

## Repository Layout

```text
.
├── GRAMMAR.md      # EBNF + disambiguation rules
├── STRATEGY.md     # High-level parser/front-end strategy
├── EXECUTION.md    # Realtime execution + JIT caching strategy
└── README.md       # Project entrypoint for users/contributors
```

## Compatibility Matrix

| Component | Supported | Notes |
|---|---|---|
| OS | `TODO` | |
| Architecture | `TODO` | |
| MLton | `TODO` | |
| LLVM | `TODO` | |

## FAQ

Q: Is this a drop-in replacement for all AWK variants?  
A: Not yet. The target is POSIX behavior first; extension coverage is phased in over time.

Q: Does `quawk` cache compiled results?  
A: Planned yes, with strict invalidation keyed by source and toolchain/runtime configuration.

## Contributing

Contributions are welcome. Please open an issue describing:

- use case
- expected behavior
- POSIX reference (if applicable)

`TODO: add coding standards, review workflow, and CI expectations`

## License

`TODO: choose and add license file (for example MIT, Apache-2.0, or BSD-2-Clause)`
