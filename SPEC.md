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
| `-v` numeric scalar preassignment | implemented | Numeric scalar preassignment is part of the current AOT-backed contract. |
| `-v` string scalar preassignment | implemented | String-valued `-v` is part of the current claimed CLI surface. |
| `--lex` / `--parse` | implemented | Stable human-readable inspection output. |
| `--ir` / `--asm` | partial | Supported for every currently claimed AOT-backed family. Broader frontend-admitted but not yet claimed POSIX forms can still fail inspection until the `P14` completion work lands. |
| `--` operand separator | implemented | Needed when a program or input file operand begins with `-`. |
| `-` stdin operand | implemented | Reads standard input at that operand position. |

Evidence:
- `tests/test_cli.py`
- `docs/design.md`

## Language Surface

| Area | Status | Notes |
|---|---|---|
| Pattern-action programs | implemented | `BEGIN`, record actions, `END`, range patterns, and expression-pattern/default-print behavior within the currently claimed expression subset. |
| Regex-driven selection | implemented | Public execution and parser support are present. |
| Default-print pattern rules | implemented | Bare range/expression patterns print matching records within the currently claimed expression subset. |
| Scalar variables and assignment | implemented | Plain scalar assignment and assignment expressions are part of the current AOT-backed contract. Broader compound-assignment parsing exists, but full backended execution for those forms is not yet claimed. |
| Associative arrays | implemented | Indexed read/write, delete, `length(array)`, `for ... in`. Quawk also documents a parenthesized `for ... in` iterable extension in the compatibility corpus. |
| Fields | implemented | `$0`, `$n`, dynamic field reads and assignment. |
| Control flow | implemented | `if`, `else`, `while`, `do ... while`, classic `for`, `break`, `continue` within the currently claimed expression subset. Quawk also documents expression-list `for` loops as a compatibility-tracked extension. |
| Record control | implemented | `next`, `nextfile`, `exit`. |
| Expressions | partial | The currently claimed AOT-backed subset includes `+`, `<`, `==`, `&&`, concatenation, unary `+`/`-`/`!`, pre/post increment and decrement, and plain assignment expressions. Broader arithmetic, comparison, logical-or, ternary, match, and `in` forms remain outside the current claimed AOT contract and are tracked for `P14`. |
| User-defined functions | implemented | Public execution and semantic checks are present. |
| POSIX-core grammar surface | implemented | Parser and semantic layer target the current `docs/quawk.ebnf` surface. |

Evidence:
- `tests/test_parser.py`
- `tests/test_p7_posix_core_frontend.py`
- `tests/test_p10_grammar_alignment.py`
- `docs/quawk.ebnf`

## Runtime and Output

| Area | Status | Notes |
|---|---|---|
| Mixed `BEGIN` / record / `END` sequencing | implemented | Includes empty-input behavior. |
| AWK-style unset scalar/array value rules | implemented | Numeric contexts read as `0`, string/print contexts read as `""`. |
| AWK string/number coercions | implemented | Includes string truthiness and concatenation behavior. |
| Single-argument `print expr` | implemented | Standard one-argument `print` is part of the current claimed output surface. |
| Bare `print` / implicit `$0` | implemented | Bare `print` now follows POSIX `$0` defaulting, including the empty-record case in `BEGIN`/`END`. |
| Multi-argument `print` | implemented | Explicit `print a, b, c` now joins arguments with `OFS`. |
| `OFS` / `ORS` driven print behavior | implemented | Output-field and output-record separator behavior is part of the current claimed surface. |
| `printf` basic execution | implemented | Literal-format `printf` is part of the current claimed AOT-backed surface. |
| Full POSIX `printf` parity | partial | Reviewed formatting and expression-combination gaps remain. |
| Output redirection and pipe output | implemented | `print` / `printf` now support `>`, `>>`, `|`, and `close()` for the current claimed literal-format output surface. |
| Multi-file input processing | implemented | Includes `FNR` reset and `FILENAME` updates. |

## Builtin Variables and Builtins

| Area | Status | Notes |
|---|---|---|
| Core builtin variables | implemented | `NR`, `FNR`, `NF`, and `FILENAME` are part of the current claimed surface. |
| Output separator builtin variables | implemented | `OFS` and `ORS` now affect `print` output as in POSIX AWK. |
| Formatting builtin variables | implemented | `OFMT` and `CONVFMT` now affect numeric print formatting and ordinary numeric-to-string coercion. |
| Remaining POSIX builtin variables | implemented | `ARGC`, `ARGV`, `ENVIRON`, and `SUBSEP` are now part of the current claimed surface; `RSTART` and `RLENGTH` update through `match()`. |
| Current builtin subset | implemented | `atan2`, `close`, `cos`, `exp`, `gsub`, `index`, `int`, `length`, `log`, `match`, `rand`, `sin`, `split`, `sqrt`, `srand`, `sprintf`, `sub`, `substr`, `system`, `tolower`, and `toupper` are part of the current claimed surface. |
| POSIX string and regex builtins | implemented | `index`, `match`, `sub`, `gsub`, `sprintf`, `tolower`, and `toupper` now have direct execution coverage; upstream corroboration includes runnable `sprintf` coverage, while one record-target `gsub` case remains a narrower reviewed backend skip. |
| POSIX numeric and system builtins | implemented | `int`, `rand`, `srand`, `system`, `atan2`, `cos`, `sin`, `exp`, `log`, and `sqrt` now have direct execution coverage across host and backend/runtime paths. The upstream subset includes a runnable `system()` anchor; `rand()` remains direct-test-only for now because the pinned references disagree on deterministic seeded output. |
| `getline` | implemented | The current claimed forms are bare `getline`, `getline var`, `getline < file`, and `getline var < file`. |

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
| Backend parity for every claimed execution path | implemented | The checked-in architecture audit and focused CLI/JIT parity tests now require every currently claimed execution family to stay on the compiled backend/runtime path. |
| Backend parity for broader frontend-admitted POSIX forms | partial | Frontend-admitted but unclaimed POSIX forms such as `-`, `*`, `/`, `%`, `^`, `<=`, `>`, `>=`, `!=`, `||`, ternary, match operators, and `in` are still outside the current AOT-backed contract. |
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
