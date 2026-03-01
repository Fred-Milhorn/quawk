# AWK Grammar (EBNF + Disambiguation Rules)

This document gives a practical grammar shape for an AWK compiler, plus the two key context-sensitive rules:

1. implicit string concatenation (`concat_expr`)
2. regular-expression literals (`REGEX`) vs division (`/`)

It is intentionally grammar-focused. Parser architecture is described separately in `STRATEGY.md`.

## 1) EBNF Grammar

Notes:
- `NEWLINE` below means one physical line break token.
- `sep` is statement separation (semicolon or one/more newlines).
- Expression precedence is encoded by nonterminal layering.
- `concat_expr` uses adjacency, so pure CFG is supplemented by the disambiguation rules in Section 2.

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

## 2) Disambiguation Rules

## 2.1 `concat_expr` (implicit concatenation)

AWK concatenation has no explicit token. Treat it as a synthetic binary operator (`CONCAT`) with precedence:

- lower than `+ - * / % ^` and unary operators
- higher than comparisons/match/logical operators (`< <= == != > >= ~ !~ && ||`)

Recommended parser rule (Pratt style):

1. Parse `add_expr` normally.
2. While the next token can start a primary/unary expression **without an intervening separator that ends expressions**, insert synthetic `CONCAT` and parse another `add_expr`.

`can_start_concat_rhs` is true for tokens that can begin an expression atom, e.g.:

- `IDENT`, `NUMBER`, `STRING`, `REGEX`
- `"("`
- `"$"`
- unary starters: `"+"`, `"-"`, `"!"`, `"++"`, `"--"`

`concat_blockers` (do not concatenate across these):

- `";"`, `","`, `")"`, `"]"`, `"}"`
- control separators such as `NEWLINE` when grammar position requires statement termination
- binary operators that already continue the current expression (`+`, `-`, `*`, `/`, `%`, `^`, comparisons, `~`, `!~`, `&&`, `||`, `?`, `:`)

Examples:

- `print a b c` parses as `print ((a CONCAT b) CONCAT c)`
- `x = (a+1) "z"` parses as `x = ((a+1) CONCAT "z")`
- `a / b c` parses as `(a / b) CONCAT c`

## 2.2 `REGEX` token vs `/` operator

`/` is context-sensitive:

- In operand position: `/.../` begins a `REGEX` literal.
- In operator position: `/` is division.

Use lexer state `expect_operand : bool`:

1. Initialize `expect_operand = true` at expression start.
2. If `expect_operand` is true and current char is `/`, lex a regexp literal until its closing unescaped `/` (respect escapes and bracket classes).
3. Otherwise lex `/` as division operator.

Update `expect_operand` after each token:

- Set `expect_operand = true` after:
  - prefix operators (`+ - ! ++ --`)
  - opening delimiters (`(`, `[`, `{`)
  - separators/operators that require a following operand (`=`, `+=`, `?`, `:`, `,`, `~`, `!~`, `&&`, `||`, etc.)
- Set `expect_operand = false` after:
  - literals (`NUMBER`, `STRING`, `REGEX`)
  - identifiers/lvalues
  - closing delimiters (`)`, `]`)
  - postfix operators (`++`, `--`)

Regex lexical details:

- `/` inside a character class `[...]` does not terminate the regex.
- `\/` is an escaped slash, not a terminator.
- Preserve raw regex text in token payload for later lowering to runtime regex compilation.

Examples:

- `$0 ~ /foo.*/` -> `REGEX("/foo.*/")`
- `x = a / b` -> division token
- `x = (/ab+/ ~ $0)` -> `REGEX("/ab+/")` due to operand context after `(`

## Implementation Note

This grammar and rule split is normal for AWK: syntax is mostly context-free, but tokenization and one precedence layer (`CONCAT`) are context-sensitive and should be specified as semantic disambiguation rules.
