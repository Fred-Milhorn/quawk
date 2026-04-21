# quawk

"Quawk" is pronounced kwawk (/kwɔːk/), rhyming with words like "hawk" or "walk". 

A POSIX-oriented AWK compiler and JIT runtime written in Python, using LLVM tooling.

## Status

`quawk` is a best-effort POSIX-complete implementation of AWK.

What works today:
- inline programs and `-f` program files, plus `-F`, `-v`, `--`, and `-` stdin operands
- `BEGIN` / record / `END` programs, regex and range patterns, and default-print pattern rules
- scalar variables, associative arrays, `delete`, classic `for`, `for ... in`, and user-defined functions
- field reads and assignment, builtin variables, `getline`, and multi-file input processing
- control flow including `if`, `while`, `do ... while`, `break`, `continue`, `next`, `nextfile`, and `exit`
- the current claimed expression surface: arithmetic, comparisons, logical operators, match operators, `in`, concatenation, ternary, assignment expressions, and pre/post increment and decrement
- `print` / `printf`, separator and format builtin-variable control, and output redirection with `close()`
- the current POSIX builtin surface, including string, regex, numeric, system, and math builtins
- inspection modes: `--lex`, `--parse`, `--ir`, and `--asm`

Current limits:
- the project is still in active implementation
- full GNU awk extension parity is not a current goal
- some inspection and extension corners are still narrower than ordinary execution
- system LLVM tools are required locally; `quawk` does not bundle LLVM

Detailed implementation status and remaining work live in [SPEC.md](SPEC.md),
[docs/design.md](docs/design.md), and [docs/roadmap.md](docs/roadmap.md).

## Goals

- make a useful POSIX-oriented AWK implementation available behind a normal CLI
- keep behavior predictable and compatibility-driven
- support inspection and compiled execution through one coherent pipeline

## Non-Goals

- full GNU awk extension parity on first release
- bundling an LLVM toolchain
- compiled artifact caching in the initial implementation

## Quickstart

Toolchain baseline:
- `uv`
- Python `3.14.x`
- LLVM command-line tools on `PATH`:
  - `lli` for executing generated LLVM IR
- `clang`, `llvm-as`, and `llvm-link` for the current record/input execution path
- `llc` for `quawk --asm`

Install from a local clone:

```sh
git clone https://github.com/Fred-Milhorn/quawk.git
cd quawk
brew install llvm
uv python install 3.14
uv tool install --python 3.14 --editable .
uv tool update-shell
quawk --help
```

Full setup and local command guidance live in [docs/getting-started.md](docs/getting-started.md).

The current runtime shells out to system LLVM binaries rather than bundling an LLVM distribution. On macOS, package-manager LLVM installs are often not on `PATH` by default, so add the LLVM `bin/` directory to your login-shell config before using `quawk` after a fresh login. For a standard Apple Silicon Homebrew install:

```sh
echo 'export PATH="/opt/homebrew/opt/llvm/bin:$PATH"' >> ~/.zprofile
```

`uv tool update-shell` similarly updates your shell config so the `quawk`
executable remains on `PATH` after logout/login.

If you want the contributor/test setup instead of a user install, use:

```sh
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -e .[dev]
```

Pinned upstream compatibility references now live under `third_party/`. From a
fresh checkout, initialize them with `git submodule update --init --recursive`.
When working on the compatibility transition, build the local One True Awk and
gawk wrappers with `uv run quawk-upstream bootstrap`.
GitHub Actions now runs a fast `ci-fast` workflow on pushes and pull requests
for the `core` pytest suite, and keeps a separate reference-compatibility
workflow for the heavier `compat_reference` subset.

Useful commands:

```sh
uv run quawk --help
uv run quawk 'BEGIN { print "hello" }'
uv run quawk --parse 'BEGIN { print 1 + 2 }'
```

## Docs Map

- [CONTRIBUTING.md](CONTRIBUTING.md): contributor workflow, standards, and PR expectations
- [POSIX.md](POSIX.md): POSIX alignment status, remaining reviewed gaps, and historical closeout notes
- [SPEC.md](SPEC.md): implemented/planned/out-of-scope feature matrix
- [docs/getting-started.md](docs/getting-started.md): local setup and first commands
- [AGENTS.md](AGENTS.md): agent/operator workflow for `uv` commands and Git commit practice
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
