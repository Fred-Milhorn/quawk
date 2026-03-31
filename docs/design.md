# Design

This document is the technical reference for `quawk`: architecture, frontend strategy, execution model, and CLI contract.

## Overview

`quawk` is a POSIX-oriented AWK compiler and runtime written in Python, using LLVM tooling.

High-level pipeline:

1. source normalization and lexing
2. parsing to AST
3. semantic validation and normalization
4. LLVM lowering and program/runtime materialization
5. execution

Execution-path direction:
- the target runtime architecture is AOT-oriented, even when the near-term driver still uses LLVM tools directly
- the compiler should emit reusable program IR that can later be linked into an executable
- a small runtime support library should own streaming input, field access, regex matching, and output helpers

Goals:
- match POSIX AWK behavior closely
- keep the implementation understandable and testable in Python
- deliver an end-to-end executable path before broad feature coverage

## Implementation Strategy

Delivery starts with a single end-to-end path, not subsystem-complete first.

That means the project should prefer:
- a tiny lexer, parser, lowering path, and runtime that can execute a very small supported program
- incremental growth of the supported AWK subset
- deferring broad parser coverage, detailed diagnostics, and optimization work until after the initial `P1` path exists

Initial `P1` target:
- inline program or `-f` file input
- a single `BEGIN` action
- `print` with a string literal
- correct stdout and exit status

Example initial success case:

```sh
quawk 'BEGIN { print "hello" }'
```

Expansion should happen by adding one coherent capability at a time, for example:
- numeric literals and arithmetic
- simple expressions and assignments
- pattern-action without functions
- records and fields
- builtins and control flow
- functions and broader POSIX coverage

Planned implementation increments:

1. Literal string print in `BEGIN` (current MVP)
   Example:
   `BEGIN { print "hello" }`
2. Numeric print in `BEGIN`
   Examples:
   `BEGIN { print 1 }`
   `BEGIN { print 1 + 2 }`
3. Scalar variables and assignment in `BEGIN`
   Examples:
   `BEGIN { x = 1; print x }`
   `BEGIN { x = 1 + 2; print x }`
4. Record loop with bare action, `$0`, and simple fields
   Examples:
   `{ print $0 }`
   `{ print $1 }`
5. Comparisons and control flow over the supported expression subset
   Examples:
   `BEGIN { if (1 < 2) print 3 }`
   `BEGIN { while (x < 3) x = x + 1 }`
6. Mixed `BEGIN` / record / `END` execution and general fields
   Examples:
   `BEGIN { print "start" } { print $2 } END { print "done" }`
7. Regexes and broader expression surface
   Examples:
   `/foo/ { print $0 }`
8. Functions and scope
   Examples:
   `function f(x) { return x + 1 } BEGIN { print f(2) }`
9. Arrays, iteration, builtins, and initial nominal functional completion
   Examples:
   `BEGIN { a["x"] = 1; print a["x"] }`
   `BEGIN { for (k in a) print k }`
10. POSIX-core syntax and AST completion
11. POSIX-core runtime semantics, builtins, and builtin variables
12. Backend parity and inspection completion for the supported POSIX-core surface
13. Compatibility convergence and release hardening

Each increment should land only when the full CLI-to-IR-to-execution path works
for that increment's example programs.

Architecture rule for record-driven programs:
- do not lower one LLVM module per concrete input stream
- do not materialize all records in Python before lowering
- compile reusable `BEGIN`, per-record, and `END` code paths once, then stream records through them

## Frontend Strategy

Recommended parser architecture:
- context-sensitive lexer for tokenization decisions
- hand-written parser for syntax
- recursive descent for statements
- precedence-driven parsing for expressions

Agreed refactor direction before the next language increment:
- generalize the frontend architecture now, without materially expanding the accepted syntax yet
- replace the concatenated-source model with a source manager and cursor over real source files
- preserve repeated `-f` inputs as distinct physical sources instead of flattening them into one backing string
- move token representation away from string-backed token kinds toward general token categories plus spans
- use a hybrid token model: `kind`, `span`, and cached text or payload only where it improves diagnostics or debugging
- turn the lexer into a reusable scanner for identifiers, keywords, literals, punctuation, and separators rather than a recognizer specialized to the initial `P1` program
- introduce broader AST categories now, such as `Program`, `PatternAction`, `Action`, `Stmt`, and `Expr`, while implementing only the currently supported variants
- route the initial `P1` program through those broader interfaces so later grammar growth extends existing abstractions instead of replacing them
- keep current human-readable diagnostics, but have them originate from generic scanner and parser helpers rather than one-off code paths

Front-end pipeline:

1. source normalization: line tracking, newline tokens, comment handling
2. lexing: emit tokens with source spans and minimal semantic payloads
3. parsing: build AST from tokens using the concrete grammar in `docs/quawk.ebnf`
4. AST validation: enforce grammar-adjacent constraints and improve diagnostics
5. lowering prep: normalize from the implemented AST in `docs/quawk.asdl` toward the backend-oriented shapes needed by lowering

Error handling and diagnostics:
- keep token spans on all AST nodes
- track source file, line, and column on every emitted token
- render lexer/parser errors as `file:line:column: error: ...` plus the source line and caret
- prefer deterministic parser error messages over recovery heuristics

Milestone order:
1. Initial end-to-end path for `BEGIN { print "literal" }`
2. refactor the frontend so the lexer, token model, source model, and parser shape match the intended long-term compiler structure
3. implement numeric print in `BEGIN` end to end
4. implement scalar variables and assignment in `BEGIN`
5. add record processing, fields, and bare actions
6. implement mixed `BEGIN` / record / `END` execution and general field access
7. add regex-driven patterns and broaden the expression surface
8. implement functions, scope, and legality checks
9. reach initial nominal functional completion by covering the major POSIX AWK construct families
10. complete the remaining POSIX-core syntax and AST surface
11. complete POSIX-core runtime semantics, builtins, and builtin variables
12. reach backend parity and inspection coverage for the supported POSIX-core surface
13. converge on compatibility and release quality

## Syntax and AST Specs

Concrete syntax lives in [quawk.ebnf](/Users/fred/dev/quawk/docs/quawk.ebnf).

Implemented AST lives in [quawk.asdl](/Users/fred/dev/quawk/docs/quawk.asdl).

These files have distinct roles:
- `docs/quawk.ebnf` is the source of truth for tokens, precedence, separators, and concrete parsing rules
- `docs/quawk.asdl` is the source of truth for the implemented AST shape
- this design document explains how the concrete grammar, implemented AST, public execution, and backend support fit together

## Execution Model

Scope:
- runtime execution path
- failure behavior
- incremental delivery expectations

Out of scope:
- concrete Python module APIs
- low-level LLVM JIT wiring details
- persistent optimization mechanisms such as compiled artifact caching

Runtime state machine for the initial implementation:

1. `LoadInput`
2. `NormalizeSource`
3. `LexSupportedSubset`
4. `ParseSupportedSubset`
5. `LowerReusableProgramIR`
6. `LinkRuntimeSupport`
7. `Execute`

Target runtime architecture:
- compiler-generated IR is reusable across input runs for the same AWK program
- record-driven execution uses three logical phases:
  - `quawk_begin(rt, state)`
  - `quawk_record(rt, state)`
  - `quawk_end(rt, state)`
- scalar program state lives in compiler-defined program state, not in Python-owned per-run specialization data
- the runtime support layer is responsible for:
  - streaming input records
  - field splitting and `$0` / `$n` access
  - regex matching against the current record
  - string and numeric output helpers
- Python should orchestrate compilation and process invocation, not implement record iteration or regex filtering for the public execution path

AOT-oriented design goals:
- the same generated program IR should work for `lli`-driven execution now and executable generation later
- `--ir` and `--asm` should describe the reusable compiled program, not a concrete run specialized to one input stream
- input size should not cause IR size to scale with record count

Current implementation model:
- the parser and semantic layers target the current `docs/quawk.ebnf` surface rather than an older execution-only subset
- public execution is broader than backend inspection support: some programs execute through the reusable LLVM/runtime path, while others still fall back to the Python host runtime
- `--ir` and `--asm` describe only the backend-lowered surface; they are not promised for every program that public `quawk` execution can run today

Current public execution surface:
- mixed `BEGIN` / record / `END` programs, regex patterns, range patterns, and default-print pattern rules
- scalar and associative-array execution with AWK-style unset-value behavior and string/number coercions
- `print` and `printf`
- field reads, dynamic field assignment, and builtin variables such as `NR`, `FNR`, `NF`, and `FILENAME`
- `if` / `else`, `while`, `do ... while`, classic `for` with expression-list init/update, `for ... in`, `break`, `continue`, `next`, `nextfile`, and `exit`
- assignment expressions, unary and postfix increment/decrement, and implicit concatenation
- user-defined functions and returns
- the current builtin subset, including `length`, `split`, and `substr`
- `-F` field-separator support and numeric `-v` preassignment

Current backend and inspection surface:
- the reusable LLVM/runtime path covers representative record-driven and richer `BEGIN` programs, including arrays, classic `for`, `for ... in`, `printf`, `length`, `split`, `substr`, regex/range selection, and `next`
- backend parity is intentionally narrower than public execution: programs that still require the host runtime do not have guaranteed `--ir` or `--asm` support

Current architectural caveat:
- the preferred public path is the reusable program/runtime split above, not Python-side whole-input materialization
- the host runtime remains the fallback for the language families not yet lowered through LLVM, notably user-defined functions, `exit`, `nextfile`, and richer scalar-string execution paths such as concatenation through scalar reads
- compatibility work should drive whether the remaining host-runtime fallback families are lowered further or explicitly scoped

Acceptance scenarios:
- inline `BEGIN { print "hello" }` compiles and executes
- inline `BEGIN { print 1 }` compiles and executes
- inline `BEGIN { print 1 + 2 }` compiles and executes
- inline `BEGIN { x = 1; print x }` compiles and executes
- inline `BEGIN { x = 1 + 2; print x }` compiles and executes
- inline `BEGIN { if (1 < 2) print 3 }` compiles and executes
- inline `BEGIN { x = 0; while (x < 3) { print x; x = x + 1 } }` compiles and executes
- inline `function f(x) { return x + 1 } BEGIN { print f(2) }` executes correctly
- inline `BEGIN { a["x"] = 1; delete a["x"]; print a["x"] }` executes correctly
- inline `BEGIN { a["x"] = 1; for (k in a) print k }` executes correctly
- inline `BEGIN { for (i = 0, j = 5; i < 3; i++, --j) print i }` executes correctly
- inline `BEGIN { print length("hello") }` executes correctly
- inline `BEGIN { print substr("hello", 2, 3) }` executes correctly
- inline `BEGIN { n = split("a b", a); print n; print a[1] }` executes correctly
- inline `BEGIN { x = "12"; print x + 1; print x "a" }` executes correctly
- inline `{ print $0 }` processes stdin records correctly
- inline `{ print $1 }` processes stdin records correctly
- inline `{ i = 2; $i = 9; print $0 }` updates the selected field and record text correctly
- inline `/start/,/stop/` executes with the default print action over the selected record range
- inline `/stop/ { nextfile } { print $0 }` skips the remainder of the current file correctly
- inline `{ print NR; print FNR; print NF }` updates builtin variables per record
- `-f hello.awk` with the same program compiles and executes
- unsupported syntax fails with deterministic diagnostics
- expanding the supported subset does not break the earlier working `P1` path
- record-driven execution remains bounded in memory with respect to input size

## Command Line Interface

Canonical usage:

```text
Usage:
  quawk [options] -f progfile ... [--] [file ...]
  quawk [options] 'program' [--] [file ...]
  quawk -h | --help
  quawk --version

Help and version:
  -h, --help            Print usage and option summary.
  --version             Print user-facing version.

Inspection and stop-after options:
  --lex                 Print tokens for the input program and exit.
  --parse               Print the parsed AST and exit.
  --ir                  Print the generated LLVM IR and exit.
  --asm                 Print the generated assembly and exit.

POSIX-style options:
  -F fs                 Set input field separator FS.
  -f progfile           Read AWK program source from file (repeatable, in order).
  -v var=value          Assign a numeric scalar before program execution (repeatable).

Program selection:
  - If one or more -f options are given, program text comes only from those files.
  - Once -f is present, positional operands are input files rather than inline program text.
  - Otherwise, the first non-option argument is the AWK program text.
  - Use -- to stop option parsing before a program operand or file operand that begins with -.

Input files:
  - Remaining operands are input files processed in order.
  - If no input files are provided, read standard input.
  - Operand "-" means standard input.

Exit status:
  0  Success
  2  Usage, parse, semantic, or configuration error
  4  Runtime, compiler, or internal failure
```

Semantic diagnostic codes:
- semantic errors include stable public codes in `error[SEMxxx]` format
- current semantic catalog:
  - `SEM001` duplicate function definition
  - `SEM002` function parameter conflicts with function name
  - `SEM003` duplicate function parameter name
  - `SEM004` `break` outside a loop
  - `SEM005` `continue` outside a loop
  - `SEM006` `next` outside a record action
  - `SEM007` `nextfile` outside a record action
  - `SEM008` assignment to a function name
  - `SEM009` `return` outside a function
  - `SEM010` call to an undefined function
  - `SEM011` invalid builtin call or builtin arity
  - `SEM012` increment/decrement on a non-assignable expression
  - `SEM013` invalid `for ... in` iterable

Goals:
- preserve familiar AWK invocation patterns
- keep POSIX-style options front and center

## Future Work

### Native Executable Emission

`quawk` should eventually gain a direct native executable output mode so users
can compile an AWK program into a runnable binary instead of only executing it
immediately or inspecting LLVM artifacts.

Chosen product contract:

- add `--exe PATH` as the executable-emission CLI flag
- produce a reusable native executable, not a baked one-shot invocation
- generated executables accept runtime `-F`, numeric `-v`, `--`, and positional
  input files
- executable emission supports only the current backend-lowered surface

Compiler usage:

```sh
quawk --exe PATH -f prog.awk
quawk --exe PATH 'BEGIN { print "hello" }'
```

Generated executable usage:

```sh
PATH [-F fs] [-v name=value ...] [--] [file ...]
```

Rules:

- `--exe` is mutually exclusive with `--lex`, `--parse`, `--ir`, and `--asm`
- compile-time `-F`, `-v`, and input-file operands are rejected in `--exe`
  mode
- generated executables do not re-expose inspection flags
- runtime `-v` remains numeric-only in the current subset

Implementation direction:

- reuse the existing LLVM lowering and reusable execution-module pipeline
- add a native-link path that assembles IR and invokes `clang`
- keep the current `quawk_main()`-based flow for JIT execution and inspection
- add a separate native executable entrypoint with `main(int argc, char **argv)`

Runtime argument handling:

- parse generated-executable arguments in the C runtime support layer, not in
  generated LLVM IR
- extract runtime file operands, optional `-F`, and numeric `-v` assignments
- let generated code map runtime `-v` assignments into compiled program-state
  slots using the known variable-index map

Support boundary:

- programs supported by the LLVM-backed execution and inspection path are
  eligible for `--exe`
- host-runtime-only programs fail with a clear user-facing error
- normal `quawk` execution behavior remains unchanged

Required coverage:

- CLI help includes `--exe`
- `--exe` is mutually exclusive with `--lex`, `--parse`, `--ir`, and `--asm`
- compile and run a simple `BEGIN` executable
- compile and run a record-driven executable with runtime file operands
- generated executable honors runtime `-F`
- generated executable honors runtime numeric `-v`
- generated executable honors `--` and `-` stdin operand behavior
- `quawk --exe` rejects compile-time `-F`, `-v`, and input-file operands
- `quawk --exe` rejects host-runtime-only programs with a clear error
- missing `clang`, `llvm-as`, or `llvm-link` failures are surfaced cleanly
- keep the initial CLI contract small until real implementation pressure justifies expansion

Program source rules:
- if one or more `-f` options are present, those files define the AWK program in order
- otherwise, the first non-option argument is the AWK program text
- remaining arguments are input files or stdin if none are provided
- when `-f` is used, the first positional operand is treated as an input file, not inline program text

Repeated `-v` assignments apply in argument order. In the current executable subset,
`-v` supports numeric scalar values only.

Unset scalar reads use AWK-style defaults in the current runtime subset:
- numeric contexts read as `0`
- string/print contexts read as `""`

Missing associative-array elements follow the same value-cell rules:
- numeric contexts read as `0`
- string/print contexts read as `""`

Inspection rules:
- `--lex`, `--parse`, `--ir`, and `--asm` are mutually exclusive
- each inspection flag prints the selected stage output to stdout and exits without executing later stages
- for record-driven programs, `--ir` and `--asm` should show reusable program artifacts, not input-specialized output
- inspection output is intended to be stable and human-readable for debugging and review
- `--lex` and `--parse` output includes source-position metadata for the currently supported nodes and tokens

Examples:

```sh
quawk 'BEGIN { print "hello" }'
quawk --lex 'BEGIN { print "hello" }'
quawk --parse 'BEGIN { print "hello" }'
quawk --ir 'BEGIN { print "hello" }'
quawk --asm 'BEGIN { print "hello" }'
quawk -f script.awk input.txt
quawk -F: -v limit=10 -f script.awk data.txt
```

## Compatibility Direction

Target baseline:
- POSIX AWK core language
- pattern-action programs
- function definitions
- standard expression and operator behavior, including implicit concatenation

Current limitations:
- string-valued `-v` assignments are not supported yet
- `--ir` and `--asm` only cover programs that fit the current backend-lowered surface; public execution is broader
- assembly inspection output is backend- and platform-dependent
- the repo-owned compatibility corpus is now supplemental to the upstream compatibility gate, and broader POSIX hardening is still ongoing
