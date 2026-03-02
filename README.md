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

Prerequisite:

- Nix package manager (`nix` command available)

If your local Nix config does not enable flakes by default, prefix commands with:

```sh
nix --extra-experimental-features 'nix-command flakes' ...
```

Enter the reproducible development shell:

```sh
nix --extra-experimental-features 'nix-command flakes' develop
```

Build:

```sh
nix --extra-experimental-features 'nix-command flakes' build
```

Run (example):

```sh
# Runtime executable is not implemented yet.
# Current default package builds and installs project documentation artifacts.
```

Format Nix files:

```sh
nix --extra-experimental-features 'nix-command flakes' fmt
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

- [BUILD.md](/Users/fred/dev/quawk/BUILD.md)
- [STANDARDS.md](/Users/fred/dev/quawk/STANDARDS.md)
- [PLAN.md](/Users/fred/dev/quawk/PLAN.md)
- [TASKS.md](/Users/fred/dev/quawk/TASKS.md)
- [CLI.md](/Users/fred/dev/quawk/CLI.md)
- [CI.md](/Users/fred/dev/quawk/CI.md)
- [STRATEGY.md](/Users/fred/dev/quawk/STRATEGY.md)
- [EXECUTION.md](/Users/fred/dev/quawk/EXECUTION.md)

## Conformance and Testing

Test strategy (planned):

- parser unit tests (grammar and disambiguation edge cases)
- semantic/runtime behavioral tests
- compatibility checks against reference AWK implementations
- differential testing against `one-true-awk` and `gawk --posix`
- SML test framework baseline: QCheck
- phase-based TDD: tests are authored first and start as `xfail` before implementation

Compatibility strategy details:

- [TESTING.md](/Users/fred/dev/quawk/TESTING.md)
- [TEST_SPEC.md](/Users/fred/dev/quawk/TEST_SPEC.md)
- [CI.md](/Users/fred/dev/quawk/CI.md)
- QCheck (SML testing library): <https://github.com/league/qcheck>
- huml-sml (HUML parser for SML): <https://github.com/Fred-Milhorn/huml-sml>
- Millet (SML language server, optional DX tool): <https://github.com/azdavis/millet>
- Phase-gate validator: SML tool (`scripts/check-phase-gate`) using `huml-sml`.

Run tests:

```sh
nix --extra-experimental-features 'nix-command flakes' flake check
```

## Repository Layout

```text
.
├── flake.nix       # Reproducible toolchain and outputs
├── flake.lock      # Pinned nixpkgs and transitive inputs
├── .gitignore
├── GRAMMAR.md      # EBNF + disambiguation rules
├── BUILD.md        # Build system and repository layout policy
├── STANDARDS.md    # Coding standards and style rules
├── PLAN.md         # Phased implementation roadmap
├── TASKS.md        # Execution backlog mapped to phases
├── CLI.md          # CLI contract and option behavior
├── CI.md           # Required CI gate policy
├── STRATEGY.md     # High-level parser/front-end strategy
├── EXECUTION.md    # Realtime execution + JIT caching strategy
├── TESTING.md      # Reference-oracle testing strategy
├── TEST_SPEC.md    # Simple test manifest contract
└── README.md       # Project entrypoint for users/contributors
```

## Compatibility Matrix

| Component | Supported | Notes |
|---|---|---|
| OS | Linux, macOS | Declared by flake target systems |
| Architecture | x86_64, aarch64 | Declared by flake target systems |
| MLton | Pinned via `flake.lock` (`nixpkgs` input) | Use `nix develop` |
| LLVM | Pinned via `flake.lock` (`nixpkgs` input) | Use `nix develop` |

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

BSD 3-Clause. See [LICENSE](/Users/fred/dev/quawk/LICENSE).
