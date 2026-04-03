# quawk

"Quawk" is pronounced kwawk (/kwɔːk/), rhyming with words like "hawk" or "walk". 

A POSIX-oriented AWK compiler and JIT runtime written in Python, using LLVM tooling.

## Status

This repository is in active implementation.

Implemented now:
- consolidated project documentation
- a working `quawk` CLI with lexer, parser, semantic checks, and public execution for the current POSIX-first surface
- phased implementation roadmap and backlog
- ordered repeatable `-f`, `-F`, numeric `-v`, `--`, and `-` stdin operand handling
- mixed `BEGIN` / record / `END` execution, regex and range patterns, and default-print pattern rules
- scalar variables, associative arrays, `delete`, classic `for`, and `for ... in`
- field reads and assignment, builtin variables, and multi-file input processing
- control flow including `if`, `while`, `do ... while`, `break`, `continue`, `next`, `nextfile`, and `exit`
- user-defined functions plus the current builtin subset: `length`, `split`, and `substr`
- differential compatibility coverage against pinned `one-true-awk` and `gawk --posix`, with the upstream suite now the primary compatibility authority

Implementation sequencing and upcoming work live in [docs/roadmap.md](docs/roadmap.md), which is the source of truth for current and next phases.

## Goals

- POSIX-first AWK behavior and compatibility
- an early end-to-end executable path for a tiny AWK subset
- incremental expansion driven by the working end-to-end path established in `P1`, now followed by compatibility hardening and explicit remaining POSIX gap closure

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
GitHub Actions now runs a fast `ci-fast` workflow on pushes and pull requests
for the non-compatibility pytest suite, and keeps a separate `compat-upstream`
workflow for the heavier upstream compatibility subset.

## Docs Map

- [CHANGELOG.md](CHANGELOG.md): user-visible release history
- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow, standards, and PR expectations
- [SPEC.md](SPEC.md): implemented/planned/out-of-scope feature matrix
- [docs/getting-started.md](docs/getting-started.md): local setup and first commands
- [docs/release-checklist.md](docs/release-checklist.md): versioned release workflow
- [docs/design.md](docs/design.md): architecture, execution, and CLI design
- [docs/quawk.ebnf](docs/quawk.ebnf): concrete syntax grammar
- [docs/quawk.asdl](docs/quawk.asdl): implemented AST schema
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
