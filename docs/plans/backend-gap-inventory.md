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

Public execution currently accepts a program only if it fits the reusable
compiled backend/runtime route.

If a program falls outside that route, `ensure_public_execution_supported()`
rejects it for ordinary execution and `lower_to_llvm_ir()` rejects it for
`--ir` and `--asm`.

The earlier narrow direct-function lane is retired and no longer belongs in the
active gap inventory.

Closed from this inventory:

- runtime-backed imperative function bodies were closed in T-267
- imperative function bodies that rely on concatenation or postfix increment
  now route through the runtime-backed backend path and no longer belong in
  the remaining gap inventory
- multi-subscript array access was closed in T-268
- side-effectful ternary branches were closed in T-269
- dynamic `printf` formats were closed in T-270
- the contract-enforcement audit was closed in T-271

## Runtime-Backed Backend Subset

This is the main compiled execution path for public `quawk` execution. It
already covers the current claimed surface, including record-driven programs,
patterns, arrays, `printf`, `getline`, `next`, `nextfile`, `exit`, and the
current builtin set.

Its remaining gaps are narrower than the earlier inventory phases, but they
still matter.

### Unsupported Or Restricted Runtime-Backed Forms

- `for (k in ...)` over anything other than a plain array name.
  Example: `for (k in expr()) print k`.
  Current restriction: the iterable must be `NameExpr(name=array_name)` and the
  name must be known as an array.

- `expr in array` where the right-hand side is not a plain array name.
  Example: `print key in get_array()`.
  Current restriction: the right-hand side must be `NameExpr(name=array_name)`.

- Dynamic `printf` formats are now supported through runtime formatting, so
  the old literal-format restriction no longer belongs in this inventory.

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
   The immediate examples are broader `split()` targets and broader `sub()` /
   `gsub()` targets.

## Cross-Cutting Public Contract

The important user-facing rule is simple:

- if a form is supported, it runs through the compiled backend/runtime path
- if a form is not yet supported, public execution fails clearly
- unsupported forms are not supposed to fall back to Python-side AWK semantics

That is why this inventory matters. It is the concrete list of grammar-valid
forms that still need backend/runtime work before the public contract can widen
again.
