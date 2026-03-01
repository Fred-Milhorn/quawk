# Build and Repository Layout

This document defines how `quawk` should be built and how the repository should be organized.

## Build System Policy

`quawk` uses a two-layer build model:

1. Outer build/toolchain layer: Nix flake (`flake.nix`, `flake.lock`)
2. Inner source/dependency layer: MLton project graph (`.mlb`)

Rationale:
- Nix pins toolchains and system dependencies for reproducibility.
- ML Basis files keep SML module dependencies explicit and maintainable.

## Toolchain Policy

Toolchains are **not vendored** in this repo.

- MLton, LLVM, clang, and related build tools come from Nix inputs.
- Versions are pinned by `flake.lock`.
- Do not add these toolchains under `vendor/` or `third_party/`.

## Output Directories

Nix-managed outputs:
- built artifacts go to `/nix/store`
- local convenience symlink is `result` (ignored by Git)

Optional local non-Nix outputs:
- use `build/` for ad hoc local artifacts (also ignored by Git)

## Vendoring Policy

Use a source-vendoring directory only when necessary for copied source dependencies:

- preferred name: `third_party/`
- include upstream provenance and license text for each dependency
- keep vendored code minimal and explicit

Do not vendor:
- compilers
- linkers
- LLVM distributions
- package-manager outputs

## Recommended Repository Structure

```text
.
├── flake.nix
├── flake.lock
├── BUILD.md
├── CI.md
├── README.md
├── LICENSE
├── GRAMMAR.md
├── TEST_SPEC.md
├── STRATEGY.md
├── EXECUTION.md
├── TESTING.md
├── src/
│   ├── quawk.mlb
│   ├── main.sml
│   ├── common/
│   ├── frontend/
│   │   ├── lexer/
│   │   ├── parser/
│   │   └── ast/
│   ├── sema/
│   ├── backend/
│   │   ├── llvm/
│   │   └── cshim/
│   └── runtime/
│       ├── awk/
│       └── c/
├── tests/
│   ├── parser/
│   ├── runtime/
│   ├── compat/
│   └── fixtures/
├── examples/
├── scripts/
└── third_party/    # only when source vendoring is required
```

## Build and Check Commands

If flakes are not globally enabled, prefix commands with:

```sh
nix --extra-experimental-features 'nix-command flakes' ...
```

Common commands:

```sh
# enter reproducible development shell
nix --extra-experimental-features 'nix-command flakes' develop

# build default package
nix --extra-experimental-features 'nix-command flakes' build

# run flake checks
nix --extra-experimental-features 'nix-command flakes' flake check

# format Nix files
nix --extra-experimental-features 'nix-command flakes' fmt
```

## Near-Term Implementation Plan

1. Add `src/` with initial `quawk.mlb` and `main.sml`.
2. Add `tests/` skeleton aligned with `TESTING.md`.
3. Update `flake.nix` default package from docs-only to binary package.
4. Keep `quawk-docs` as a secondary package output.

Track implementation progress in:
- `PLAN.md` for phased milestones and exit criteria
- `TASKS.md` for task-level execution details
