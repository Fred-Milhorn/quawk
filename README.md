# quawk

POSIX-oriented AWK compiler and JIT runtime written in Python, using LLVM tooling.

## Status

This repository is in active design/prototyping.

Implemented now:
- consolidated project documentation
- language, execution, CLI, and testing design
- phased implementation roadmap and backlog
- Python package/bootstrap scaffold with a working MVP `quawk` CLI path
- end-to-end MVP execution for `BEGIN { print "literal" }`
- example program and CI workflow scaffold

Planned next:
- incremental language and runtime expansion from that MVP
- compatibility and differential test harness after the executable core exists

## Goals

- POSIX-first AWK behavior and compatibility
- an early end-to-end executable path for a tiny AWK subset
- incremental expansion driven by the working MVP path

## Non-Goals

- full GNU awk extension parity on first release
- a full ahead-of-time native compiler workflow
- compiled artifact caching in the initial implementation

## Quickstart

Toolchain baseline:
- `uv`
- Python `3.14.x`

Bootstrap:

```sh
uv python install 3.14
uv venv --python 3.14 .venv
source .venv/bin/activate
```

Full setup and local command guidance live in [docs/getting-started.md](docs/getting-started.md).

## Docs Map

- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow, standards, and PR expectations
- [docs/getting-started.md](docs/getting-started.md): local setup and first commands
- [docs/design.md](docs/design.md): architecture, grammar, execution, and CLI design
- [docs/testing.md](docs/testing.md): test strategy, workflow, and CI gates
- [docs/roadmap.md](docs/roadmap.md): phased implementation plan and active backlog

## Compatibility Snapshot

| Component | Supported | Notes |
|---|---|---|
| OS | Linux, macOS | CI matrix expands over time |
| Architecture | x86_64, aarch64 | As available in CI provider |
| Python | 3.14.x | Managed by `uv` |
| LLVM tooling | system LLVM tools (`lli`, `clang`, `llvm-as`) | Used for the current MVP JIT path |

## FAQ

Q: Is this a drop-in replacement for all AWK variants?  
A: Not yet. The target is POSIX behavior first; extension coverage is phased in.

Q: Does `quawk` cache compiled results?  
A: Not in the initial implementation plan. If startup cost matters later, caching can be revisited as a separate optimization track.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
