# Design

This document is the technical reference for `quawk`: architecture, frontend strategy, execution model, and CLI contract.

## Overview

`quawk` is a POSIX-oriented AWK compiler and JIT runtime written in Python, using LLVM tooling.

High-level pipeline:

1. source normalization and lexing
2. parsing to AST
3. semantic validation and normalization
4. LLVM lowering and JIT materialization
5. execution

Current MVP note:
- the current execution path lowers to LLVM IR text and runs it through `lli`
- an in-process LLVM binding can be revisited later if it becomes worthwhile

Goals:
- match POSIX AWK behavior closely
- keep the implementation understandable and testable in Python
- deliver an MVP end-to-end executable path before broad feature coverage

## Implementation Strategy

Delivery is MVP-first, not subsystem-complete first.

That means the project should prefer:
- a tiny lexer, parser, lowering path, and runtime that can execute a very small supported program
- incremental growth of the supported AWK subset
- deferring broad parser coverage, detailed diagnostics, and optimization work until after the MVP path exists

Initial MVP target:
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
6. Functions and broader POSIX-oriented coverage
   Examples:
   `function f(x) { return x + 1 } BEGIN { print f(2) }`

Each increment should land only when the full CLI-to-IR-to-execution path works
for that increment's example programs.

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
- turn the lexer into a reusable scanner for identifiers, keywords, literals, punctuation, and separators rather than a recognizer specialized to the current MVP program
- introduce broader AST categories now, such as `Program`, `PatternAction`, `Action`, `Stmt`, and `Expr`, while implementing only the currently supported variants
- route the current MVP program through those broader interfaces so later grammar growth extends existing abstractions instead of replacing them
- keep current human-readable diagnostics, but have them originate from generic scanner and parser helpers rather than one-off code paths

Front-end pipeline:

1. source normalization: line tracking, newline tokens, comment handling
2. lexing: emit tokens with source spans and minimal semantic payloads
3. parsing: build AST from tokens using the concrete grammar in `docs/grammar.ebnf`
4. AST validation: enforce grammar-adjacent constraints and improve diagnostics
5. lowering prep: normalize AST shapes described in `docs/quawk.asdl` for semantic and codegen phases

Error handling and diagnostics:
- keep token spans on all AST nodes
- track source file, line, and column on every emitted token
- render lexer/parser errors as `file:line:column: error: ...` plus the source line and caret
- recover at statement boundaries (`;`, newline, `}`) to continue reporting errors
- prefer deterministic error messages over aggressive recovery heuristics

Milestone order:
1. MVP executable path for `BEGIN { print "literal" }`
2. refactor the frontend so the lexer, token model, source model, and parser shape match the intended long-term compiler structure
3. implement numeric print in `BEGIN` end to end
4. implement scalar variables and assignment in `BEGIN`
5. add record processing, fields, and bare actions
6. broaden control flow, functions, diagnostics, and conformance coverage as execution support grows

## Syntax and AST Specs

Concrete syntax lives in [grammar.ebnf](/Users/fred/dev/quawk/docs/grammar.ebnf).

Abstract syntax lives in [quawk.asdl](/Users/fred/dev/quawk/docs/quawk.asdl).

These files have distinct roles:
- `docs/grammar.ebnf` is the source of truth for tokens, precedence, separators, and concrete parsing rules
- `docs/quawk.asdl` is the source of truth for the long-term AST shape the parser lowers into
- this design document explains the implementation strategy that connects the two

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
5. `LowerToLLVM`
6. `Execute`

Initial supported MVP path:
- one `BEGIN` action
- one or more `print` statements
- string literals
- numeric literals
- additive numeric expressions
- scalar assignments in `BEGIN`
- scalar variable reads in expressions
- bare action record processing
- `$0` and `$1` field reads
- no function definitions required yet

Acceptance scenarios:
- inline `BEGIN { print "hello" }` compiles and executes
- inline `BEGIN { print 1 }` compiles and executes
- inline `BEGIN { print 1 + 2 }` compiles and executes
- inline `BEGIN { x = 1; print x }` compiles and executes
- inline `BEGIN { x = 1 + 2; print x }` compiles and executes
- inline `{ print $0 }` processes stdin records correctly
- inline `{ print $1 }` processes stdin records correctly
- `-f hello.awk` with the same program compiles and executes
- unsupported syntax fails with deterministic diagnostics
- expanding the supported subset does not break the earlier working MVP path

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
  -v var=value          Assign variable before program execution (repeatable).

Program selection:
  - If one or more -f options are given, program text comes only from those files.
  - Otherwise, the first non-option argument is the AWK program text.
  - Mixing -f with inline program text is an error.

Input files:
  - Remaining operands are input files processed in order.
  - If no input files are provided, read standard input.
  - Operand "-" means standard input.

Exit status:
  0  Success
  2  Usage, parse, semantic, or configuration error
  3  Runtime execution error
  4  Internal compiler/runtime failure
```

Goals:
- preserve familiar AWK invocation patterns
- keep POSIX-style options front and center
- keep the initial CLI contract small until real implementation pressure justifies expansion

Program source rules:
- if one or more `-f` options are present, concatenate those files in order
- otherwise, the first non-option argument is the AWK program text
- remaining arguments are input files or stdin if none are provided
- mixing `-f` with inline program text is an error

Repeated `-v` assignments apply in argument order.

Inspection rules:
- `--lex`, `--parse`, `--ir`, and `--asm` are mutually exclusive
- each inspection flag prints the selected stage output to stdout and exits without executing later stages
- inspection output is intended to be stable and human-readable for debugging and review
- `--lex` and `--parse` output includes source-position metadata for the current MVP nodes and tokens

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
- the executable MVP path currently supports only `BEGIN { print "literal" }`
- assembly inspection output is backend- and platform-dependent
- compatibility corpus is still in bootstrap phase
