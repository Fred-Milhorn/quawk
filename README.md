# quawk

"Quawk" is pronounced kwawk (/kwɔːk/), rhyming with words like "hawk" or "walk". 

A POSIX-oriented AWK compiler and JIT runtime written in Python, using LLVM tooling.

## Status

This repository is in active implementation.

Implemented now:
- consolidated project documentation
- lexer, parser, semantic checks, and LLVM-backed execution for the current subset
- phased implementation roadmap and backlog
- Python package/bootstrap scaffold with a working end-to-end `quawk` CLI path
- end-to-end execution for `BEGIN` programs with string/numeric print, scalar assignment, `if`/`while`, and AWK-style default-zero scalar reads
- mixed `BEGIN` / record / `END` execution, regex-filter record selection, and general `$n` field reads
- initial user-defined function execution and legality checks
- numeric `-v name=value` preassignment before execution
- example program scaffold

Implementation sequencing and upcoming work live in [docs/roadmap.md](docs/roadmap.md), which is the source of truth for current and next phases.

## Goals

- POSIX-first AWK behavior and compatibility
- an early end-to-end executable path for a tiny AWK subset
- incremental expansion driven by the working end-to-end path established in `P1`

## Non-Goals

- full GNU awk extension parity on first release
- a full ahead-of-time native compiler workflow
- compiled artifact caching in the initial implementation

## Quickstart

Toolchain baseline:
- `uv`
- Python `3.14.x`
- LLVM command-line tools on `PATH`:
  - `lli` for executing generated LLVM IR
  - `clang`, `llvm-as`, and `llvm-link` for the current record/input execution path
  - `llc` for `quawk --asm`

Bootstrap:

```sh
uv python install 3.14
uv venv --python 3.14 .venv
source .venv/bin/activate
```

Full setup and local command guidance live in [docs/getting-started.md](docs/getting-started.md).

The current runtime shells out to system LLVM binaries rather than bundling an LLVM distribution. On macOS, package-manager LLVM installs are often not on `PATH` by default, so make sure the directory containing these tools is exported before running `quawk`.

Pinned upstream compatibility references now live under `third_party/`. From a
fresh checkout, initialize them with `git submodule update --init --recursive`.
When working on the compatibility transition, build the local One True Awk and
gawk wrappers with `uv run python scripts/upstream_compat.py bootstrap`.

## Docs Map

- [CHANGELOG.md](CHANGELOG.md): user-visible release history
- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow, standards, and PR expectations
- [SPEC.md](SPEC.md): implemented/planned/out-of-scope feature matrix
- [docs/getting-started.md](docs/getting-started.md): local setup and first commands
- [docs/release-checklist.md](docs/release-checklist.md): versioned release workflow
- [docs/design.md](docs/design.md): architecture, execution, and CLI design
- [docs/grammar.ebnf](docs/grammar.ebnf): concrete syntax grammar
- [docs/current-ast.asdl](docs/current-ast.asdl): implemented parser AST schema
- [docs/quawk.asdl](docs/quawk.asdl): future normalized AST schema
- [docs/testing.md](docs/testing.md): test strategy, workflow, and future release gates
- [docs/roadmap.md](docs/roadmap.md): phased implementation plan and active backlog

## Compatibility Snapshot

| Component | Supported | Notes |
|---|---|---|
| OS | Linux, macOS | Local development targets today |
| Architecture | x86_64, aarch64 | As LLVM tooling is available locally |
| Python | 3.14.x | Managed by `uv` |
| LLVM tooling | system LLVM tools (`lli`, `clang`, `llvm-as`, `llvm-link`) plus `llc` for `--asm` | Required for the current LLVM-backed execution path |

## FAQ

Q: Is this a drop-in replacement for all AWK variants?  
A: Not yet. The target is POSIX behavior first; extension coverage is phased in.

Q: Does `quawk` cache compiled results?  
A: Not in the initial implementation plan. If startup cost matters later, caching can be revisited as a separate optimization track.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
