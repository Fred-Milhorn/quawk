# Design

This document is the technical reference for `quawk`: architecture, frontend strategy, language grammar, execution model, and CLI contract.

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

## Frontend Strategy

Recommended parser architecture:
- context-sensitive lexer for tokenization decisions
- hand-written parser for syntax
- recursive descent for statements
- precedence-driven parsing for expressions

Front-end pipeline:

1. source normalization: line tracking, newline tokens, comment handling
2. lexing: emit tokens with source spans and minimal semantic payloads
3. parsing: build AST from tokens using the grammar below
4. AST validation: enforce grammar-adjacent constraints and improve diagnostics
5. lowering prep: normalize AST shapes expected by semantic and codegen phases

Error handling and diagnostics:
- keep token spans on all AST nodes
- recover at statement boundaries (`;`, newline, `}`) to continue reporting errors
- prefer deterministic error messages over aggressive recovery heuristics

Milestone order:
1. MVP executable path for `BEGIN { print "literal" }`
2. extend expressions and statements needed for the next runnable increment
3. add records, fields, and pattern-action execution
4. broaden diagnostics and recovery only after execution coverage exists
5. expand conformance testing as supported behavior grows

## AWK Grammar

Notes:
- `NEWLINE` means one physical line break token
- `sep` is statement separation (semicolon or one/more newlines)
- expression precedence is encoded by nonterminal layering
- `concat_expr` uses adjacency, so pure CFG is supplemented by the disambiguation rules below

```ebnf
program             ::= item*

item                ::= function_def
                      | pattern_action

function_def        ::= "function" IDENT "(" param_list? ")" action
param_list          ::= IDENT ("," IDENT)*

pattern_action      ::= pattern_range action?
                      | pattern action?
                      | action

pattern_range       ::= pattern "," pattern
pattern             ::= "BEGIN"
                      | "END"
                      | expr

action              ::= "{" stmt_list? "}"
stmt_list           ::= stmt (sep stmt)* sep?
sep                 ::= ";" | NEWLINE+

stmt                ::= action
                      | "if" "(" expr ")" stmt ("else" stmt)?
                      | "while" "(" expr ")" stmt
                      | "do" stmt "while" "(" expr ")"
                      | "for" "(" for_init? ";" expr? ";" for_update? ")" stmt
                      | "for" "(" IDENT "in" expr ")" stmt
                      | "break"
                      | "continue"
                      | "next"
                      | "nextfile"
                      | "exit" expr?
                      | "return" expr?
                      | "delete" lvalue ("[" subscript_list "]")?
                      | simple_stmt

for_init            ::= expr_list
for_update          ::= expr_list
expr_list           ::= expr ("," expr)*

simple_stmt         ::= expr

subscript_list      ::= expr ("," expr)*
lvalue              ::= IDENT
                      | IDENT "[" subscript_list "]"
                      | "$" expr

expr                ::= assign_expr

assign_expr         ::= conditional_expr
                      | lvalue assign_op assign_expr
assign_op           ::= "=" | "+=" | "-=" | "*=" | "/=" | "%=" | "^="

conditional_expr    ::= or_expr ("?" expr ":" conditional_expr)?

or_expr             ::= and_expr ("||" and_expr)*
and_expr            ::= match_expr ("&&" match_expr)*
match_expr          ::= in_expr (("~" | "!~") in_expr)*
in_expr             ::= concat_expr ("in" concat_expr)?

concat_expr         ::= add_expr (CONCAT add_expr)*
                       (* CONCAT is implicit; inserted by parser/lexer rule. *)

add_expr            ::= mul_expr (("+" | "-") mul_expr)*
mul_expr            ::= pow_expr (("*" | "/" | "%") pow_expr)*
pow_expr            ::= unary_expr ("^" pow_expr)?

unary_expr          ::= ("+" | "-" | "!" | "++" | "--") unary_expr
                      | postfix_expr

postfix_expr        ::= primary ("++" | "--")?

primary             ::= NUMBER
                      | STRING
                      | REGEX
                      | lvalue
                      | func_call
                      | "(" expr ")"

func_call           ::= IDENT "(" arg_list? ")"
arg_list            ::= expr ("," expr)*
```

## Disambiguation Rules

### Implicit Concatenation

AWK concatenation has no explicit token. Treat it as a synthetic binary operator (`CONCAT`) with precedence:
- lower than `+ - * / % ^` and unary operators
- higher than comparisons, match operators, and logical operators

Recommended parser rule:

1. parse `add_expr` normally
2. while the next token can start a primary or unary expression without an intervening separator that ends expressions, insert synthetic `CONCAT` and parse another `add_expr`

`can_start_concat_rhs` is true for:
- `IDENT`, `NUMBER`, `STRING`, `REGEX`
- `(`
- `$`
- unary starters `+`, `-`, `!`, `++`, `--`

`concat_blockers`:
- `;`, `,`, `)`, `]`, `}`
- `NEWLINE` when grammar position requires statement termination
- binary operators that already continue the current expression

Examples:
- `print a b c` parses as `print ((a CONCAT b) CONCAT c)`
- `x = (a+1) "z"` parses as `x = ((a+1) CONCAT "z")`
- `a / b c` parses as `(a / b) CONCAT c`

### `REGEX` Token vs `/` Operator

`/` is context-sensitive:
- in operand position: `/.../` begins a `REGEX` literal
- in operator position: `/` is division

Use lexer state `expect_operand : bool`:

1. initialize `expect_operand = true` at expression start
2. if `expect_operand` is true and current char is `/`, lex a regexp literal until its closing unescaped `/`
3. otherwise lex `/` as division operator

Set `expect_operand = true` after:
- prefix operators
- opening delimiters
- separators and operators that require a following operand

Set `expect_operand = false` after:
- literals
- identifiers and lvalues
- closing delimiters
- postfix operators

Regex lexical details:
- `/` inside a character class `[...]` does not terminate the regex
- `\/` is an escaped slash, not a terminator
- preserve raw regex text in token payload for later lowering

Examples:
- `$0 ~ /foo.*/` produces a `REGEX`
- `x = a / b` uses division
- `x = (/ab+/ ~ $0)` uses `REGEX` due to operand context after `(`

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
- no record-processing loop required yet
- no function definitions required yet

Acceptance scenarios:
- inline `BEGIN { print "hello" }` compiles and executes
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

Examples:

```sh
quawk 'BEGIN { print "hello" }'
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
- runtime executable is not implemented yet
- compatibility corpus is still in bootstrap phase
