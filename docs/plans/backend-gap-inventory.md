# Backend Gap Inventory

This document records the AWK forms that still sit outside Quawk's compiled
backend/runtime contract.

The implementation follow-up plan for closing these gaps lives in
[execution-completeness-plan.md](execution-completeness-plan.md).

The intended execution model remains:

- Python lexes, parses, normalizes, lowers to LLVM IR, and orchestrates LLVM
  tools.
- The backend/runtime executes the AWK program.
- Ordinary public execution does not keep Python-side semantic fallback for
  forms outside the current contract; unsupported programs fail clearly instead.

This inventory is meant to make the remaining gaps explicit enough to bridge
them deliberately.

## How To Read This Inventory

Public execution currently accepts a program only if it fits one of two
compiled routes:

1. the narrow direct-function backend subset
2. the broader runtime-backed backend subset

If a program fits neither route, `ensure_public_execution_supported()` rejects
it for ordinary execution and `lower_to_llvm_ir()` rejects it for `--ir` and
`--asm`.

The sections below describe the gaps route by route.

Closed from this inventory:

- runtime-backed imperative function bodies were closed in T-267
- multi-subscript array access was closed in T-268

## Route 1: Direct-Function Backend Subset

This route exists only for programs that:

- define one or more user functions, and
- normalize to direct `BEGIN`-only execution

It is intentionally narrow. It supports only:

- numeric literals and scalar names
- calls to other user-defined functions with matching arity
- arithmetic `+`, `-`, `*`, `/`, `%`, `^`
- comparisons `<`, `<=`, `>`, `>=`, `==`, `!=`
- `&&` and `||`
- pure ternary expressions
- scalar assignment
- blocks, `if`, and `while`
- `print` with exactly one argument
- `return value` inside functions

### Unsupported Direct-Function Forms

These forms parse today but do not fit the direct-function route:

- Any record-driven or `END` execution shape.
  Example: `{ print $0 }`, `END { print x }`, `/re/ { print }`.
  Why blocked: this route requires `normalize_program_for_lowering(program)`
  to produce direct `BEGIN` statements only.

- String-valued computation beyond printing a literal string.
  Example: `function f() { return "x" } BEGIN { print f() }`.
  Why blocked: function expressions in this route admit numeric literals, names,
  ternaries over pure expressions, and local function calls only.

- Field access and field assignment.
  Example: `BEGIN { print $1 }`, `BEGIN { $2 = 9 }`.
  Why blocked: field expressions and field lvalues are not part of the direct
  subset.

- Array reads, writes, deletes, and membership tests.
  Example: `BEGIN { a["x"] = 1 }`, `BEGIN { print a["x"] }`, `BEGIN { delete a["x"] }`.
  Why blocked: array lvalues and array index expressions are outside the
  direct subset.

- Builtins and `getline`.
  Example: `BEGIN { print length("x") }`, `BEGIN { n = split("a b", a) }`,
  `BEGIN { getline x }`.
  Why blocked: only user-defined function calls are admitted.

- Concatenation, regex operators, and `in`.
  Example: `BEGIN { print "a" "b" }`, `BEGIN { print $0 ~ /x/ }`,
  `BEGIN { print "x" in a }`.
  Why blocked: only the direct subset's arithmetic, comparison, and logical
  operators are admitted.

- Assignment expressions, increment and decrement expressions, and compound
  assignment.
  Example: `BEGIN { print (x = 1) }`, `BEGIN { ++x }`, `BEGIN { x += 1 }`.
  Why blocked: the direct subset only accepts plain assignment statements to a
  scalar name.

- `do ... while`, `for`, `for ... in`, `break`, and `continue`.
  Example: `BEGIN { for (i = 0; i < 3; i++) print i }`.
  Why blocked: the only loop form in this route is `while`.

- `printf`, expression statements, `next`, `nextfile`, `exit`, and `delete`.
  Example: `BEGIN { printf "%d\n", 1 }`, `BEGIN { next }`.
  Why blocked: these statements are rejected explicitly by direct lowering.

- Function bodies without a final return, empty function bodies, and early
  returns before the last statement.
  Example: `function f(x) { if (x) return 1; print x }`.
  Why blocked: each function body must be non-empty, end in `return`, and may
  not contain earlier `return` statements.

### Bridge Priorities For This Route

The direct-function route is best treated as a temporary narrow lane, not the
long-term execution model for richer functions.

The main bridge work here is:

- move richer user-defined function bodies onto the runtime-backed route
- reduce or retire direct-only function restrictions once the runtime-backed
  lowering can cover the same programs

## Route 2: Runtime-Backed Backend Subset

This is the main compiled execution path for public `quawk` execution. It
already covers the current claimed surface, including record-driven programs,
patterns, arrays, `printf`, `getline`, `next`, `nextfile`, `exit`, and the
current builtin set.

Its gaps are narrower than the direct-function route, but they still matter.

### Unsupported Or Restricted Runtime-Backed Forms

- `for (k in ...)` over anything other than a plain array name.
  Example: `for (k in expr()) print k`.
  Current restriction: the iterable must be `NameExpr(name=array_name)` and the
  name must be known as an array.

- `expr in array` where the right-hand side is not a plain array name.
  Example: `print key in get_array()`.
  Current restriction: the right-hand side must be `NameExpr(name=array_name)`.

- Ternary expressions whose branches have side effects.
  Example: `print cond ? x++ : y++`, `print cond ? sub(/a/, "b", s) : t`.
  Current restriction: both branches of a ternary must be side-effect free.

- `printf` with a non-literal format string.
  Example: `fmt = "%d\n"; printf fmt, x`.
  Current restriction: the first `printf` argument must be a
  `StringLiteralExpr`.

- `printf` where the format string and argument list do not line up exactly.
  Example: `printf "%d %d\n", x`.
  Current restriction: the counted conversion specifiers must equal the number
  of provided value arguments.

- `printf` specifiers outside the currently typed lowering contract.
  Example: `%s` fed from a value the backend cannot lower as a string, or a
  numeric specifier fed from a value the backend cannot lower as numeric.
  Current restriction:
  - `%s` arguments must fit the supported string-expression subset
  - all other specifiers must fit the supported numeric-expression subset

- `split()` with a non-name target.
  Example: `split($0, a[i])`, `split($0, $1)`.
  Current restriction: the second argument must be a plain `NameExpr`.

- `sub()` and `gsub()` with a third argument that is not a supported lvalue.
  Example: `sub(/a/, "b", expr())`.
  Current restriction: the optional target must lower to one of:
  - scalar variable
  - field lvalue
  - one-subscript array element

- Builtins outside the currently admitted runtime subset.
  The runtime-backed subset currently admits only the checked-in builtin set:
  `atan2`, `close`, `cos`, `exp`, `gsub`, `index`, `int`, `length`, `log`,
  `match`, `rand`, `sin`, `split`, `sqrt`, `srand`, `sprintf`, `sub`,
  `substr`, `system`, `tolower`, and `toupper`.
  Anything outside that set remains unsupported until explicit lowering and
  runtime support are added.

- Top-level items outside `PatternAction` and `FunctionDef`.
  Why blocked: the runtime-backed route only reasons about those two top-level
  item families.

### Important Nuance About Expression Statements

The runtime-backed route accepts expression statements only when the expression
itself already fits the supported lowering subset.

That means apparently simple forms can still fail if they rely on an unsupported
sub-expression shape.

Examples:

- `x = y = 1` may work only if the nested assignment shape stays within the
  admitted assignment-expression rules.
- `foo()` fails unless `foo` is a supported user-defined function or admitted
  builtin.
- `sub(/a/, "b", expr())` fails if `expr()` does not lower to a supported
  string target for the builtin's third argument.

### Bridge Priorities For This Route

The main remaining bridge work for the runtime-backed route is concentrated in
these buckets:

1. Tighten the plain-array requirements for `for (k in ...)` and `expr in
   array` so non-name array-like expressions do not stay parse-only.

2. Relax builtin-call shape restrictions where the runtime already has enough
   machinery.
   The immediate examples are dynamic `printf` formats, broader `split()`
   targets, and broader `sub()` / `gsub()` targets.

3. Add full short-circuit lowering for side-effectful ternary branches.
   The current pure-branch restriction is a correctness-preserving subset, not
   the intended final AWK surface.

## Cross-Cutting Public Contract

The important user-facing rule is simple:

- if a form is supported, it runs through the compiled backend/runtime path
- if a form is not yet supported, public execution fails clearly
- unsupported forms are not supposed to fall back to Python-side AWK semantics

That is why this inventory matters. It is the concrete list of grammar-valid
forms that still need backend/runtime work before the public contract can widen
again.
