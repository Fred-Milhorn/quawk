# SPEC

This document is the public feature matrix for `quawk`.

Status values:
- `implemented`: supported now and covered by the current docs/tests
- `partial`: available with explicit limits or narrower backend/inspection support
- `planned`: intended next work but not yet committed as supported behavior
- `out-of-scope`: not part of the intended first release contract

## CLI

| Area | Status | Notes |
|---|---|---|
| `quawk --help`, `-h`, `--version` | implemented | Stable user-facing help/version path. |
| Inline program text | implemented | `quawk 'BEGIN { print "hello" }'` |
| `-f progfile` | implemented | Repeatable and ordered. |
| `-F fs` | implemented | Field separator support is part of the public execution surface. |
| `-v name=value` | partial | Numeric scalar values only. String-valued `-v` is not supported yet. |
| `--lex` / `--parse` | implemented | Stable human-readable inspection output. |
| `--ir` / `--asm` | partial | Intended to cover the full AOT-backed execution surface, but some claimed language families are not lowered yet. Python-side semantic execution remains transition debt, not the target contract. |
| `--` operand separator | implemented | Needed when a program or input file operand begins with `-`. |
| `-` stdin operand | implemented | Reads standard input at that operand position. |

Evidence:
- `tests/test_cli.py`
- `docs/design.md`

## Language Surface

| Area | Status | Notes |
|---|---|---|
| Pattern-action programs | implemented | `BEGIN`, record actions, `END`, expression patterns, range patterns. |
| Regex-driven selection | implemented | Public execution and parser support are present. |
| Default-print pattern rules | implemented | Bare range/expression patterns print matching records. |
| Scalar variables and assignment | implemented | Includes assignment expressions and compound assignment parsing. |
| Associative arrays | implemented | Indexed read/write, delete, `length(array)`, `for ... in`. Quawk also documents a parenthesized `for ... in` iterable extension in the compatibility corpus. |
| Fields | implemented | `$0`, `$n`, dynamic field reads and assignment. |
| Control flow | implemented | `if`, `else`, `while`, `do ... while`, classic `for`, `break`, `continue`. Quawk also documents expression-list `for` loops as a compatibility-tracked extension. |
| Record control | implemented | `next`, `nextfile`, `exit`. |
| Expressions | implemented | Arithmetic, comparisons, equality, logical operators, ternary, match ops, `in`, concatenation, unary and postfix inc/dec. Compatibility-tracked broader admitted forms are recorded in `tests/corpus/divergences.toml`. |
| User-defined functions | implemented | Public execution and semantic checks are present. |
| POSIX-core grammar surface | implemented | Parser and semantic layer target the current `docs/quawk.ebnf` surface. |

Evidence:
- `tests/test_parser.py`
- `tests/test_p7_posix_core_frontend.py`
- `tests/test_p10_grammar_alignment.py`
- `docs/quawk.ebnf`

## Runtime and Builtins

| Area | Status | Notes |
|---|---|---|
| Mixed `BEGIN` / record / `END` sequencing | implemented | Includes empty-input behavior. |
| AWK-style unset scalar/array value rules | implemented | Numeric contexts read as `0`, string/print contexts read as `""`. |
| AWK string/number coercions | implemented | Includes string truthiness and concatenation behavior. |
| Builtin variables | implemented | `NR`, `FNR`, `NF`, `FILENAME` |
| Builtins | partial | Current shipped subset is `length`, `split`, and `substr`; broader POSIX builtin coverage is not claimed yet. |
| Multi-file input processing | implemented | Includes `FNR` reset and `FILENAME` updates. |

Evidence:
- `tests/test_p3_mixed_programs.py`
- `tests/test_p6_arrays.py`
- `tests/test_p8_runtime_baselines.py`
- `tests/test_jit.py`

## Backend and Inspection

| Area | Status | Notes |
|---|---|---|
| Reusable LLVM lowering for representative `BEGIN` programs | implemented | |
| Reusable LLVM lowering for representative record-driven programs | implemented | Mixed programs, regex filters, arrays, iteration, and selected builtins are covered. |
| Backend parity for representative completed POSIX-core programs | implemented | Covered by the `P9` parity suite. |
| Backend parity for every claimed execution path | partial | The intended product is backend execution for all claimed behavior, but some families still rely on temporary host-runtime execution. |
| Representative user-defined functions through `--ir` / `--asm` | implemented | The direct-BEGIN numeric function subset now supports inspection output. |
| Representative `nextfile`, `exit`, and scalar-string families through `--ir` / `--asm` | implemented | Inspection now works for the representative completed control and coercion families covered by the architecture audit. |

Evidence:
- `tests/test_p9_backend_parity.py`
- `tests/test_cli.py`
- `docs/design.md`

## Compatibility and Release

| Area | Status | Notes |
|---|---|---|
| Single-engine corpus coverage | implemented | File-backed corpus under `tests/corpus/` |
| Differential compatibility runner | implemented | `quawk`, pinned `one-true-awk`, and pinned `gawk --posix` |
| Divergence manifest workflow | implemented | Classified reference disagreements and intentional extensions live in `tests/corpus/divergences.toml`. |
| Required compatibility gate environment | implemented | Required pytest compatibility suites expect repo-managed One True Awk and gawk references built from the pinned upstream sources; missing engines are environment failures. |
| Release smoke baseline | implemented | `tests/test_p12_release_smoke.py` |
| Versioned release checklist | implemented | Checked in at `docs/release-checklist.md`. |
| Versioned changelog artifact | implemented | Checked in at `CHANGELOG.md`. |

Evidence:
- `tests/test_corpus.py`
- `tests/test_corpus_differential.py`
- `tests/test_p10_compat_baselines.py`
- `tests/test_p11_supported_compatibility_corpus.py`
- `tests/test_p12_release_smoke.py`
- `docs/release-checklist.md`
- `CHANGELOG.md`

## Toolchain and Platforms

| Area | Status | Notes |
|---|---|---|
| Python 3.14.x via `uv` | implemented | Current developer workflow baseline. |
| Linux and macOS local development targets | implemented | As documented in the README compatibility snapshot. |
| System LLVM tools on `PATH` | implemented | `lli`, `clang`, `llvm-as`, `llvm-link`, and `llc` for `--asm`. |
| Bundled LLVM toolchain | out-of-scope | Users supply system LLVM tooling. |
| Compiled artifact caching | out-of-scope | Explicit non-goal for the first release. |
| Full GNU awk extension parity | out-of-scope | POSIX-first scope for the first release. |

Primary references:
- `README.md`
- `docs/design.md`
- `docs/getting-started.md`
- `docs/testing.md`
- `docs/roadmap.md`
