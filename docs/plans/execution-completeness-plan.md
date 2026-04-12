# Execution Completeness Plan

This plan closes the remaining split between Quawk's grammar contract and its
compiled execution contract.

The corrective rule is strict:

- if a form is admitted by `docs/quawk.ebnf` and accepted by the frontend
  semantics, it should execute end-to-end through the LLVM backend/runtime path
- Python should lex, parse, normalize, lower, and orchestrate LLVM tools, not
  implement AWK semantics for residual forms
- parseable-but-not-lowerable forms are execution-completeness debt, not an
  acceptable steady state

The detailed inventory of residual backend gaps lives in
[backend-gap-inventory.md](backend-gap-inventory.md). This document turns that
inventory into the next implementation wave.

The checked-in representative baseline for those gaps lives in
[execution-completeness-matrix.md](execution-completeness-matrix.md).

## Phase Goal

Eliminate the remaining grammar/backend split by closing the current
grammar-valid, semantically valid forms that still do not lower cleanly through
the compiled backend/runtime path.

Success means:

- ordinary public execution succeeds for the remaining admitted forms
- `--ir` and `--asm` succeed for the same representative programs
- the direct-function subset no longer serves as a long-term escape hatch for
  richer function bodies
- new frontend widening is not accepted unless end-to-end lowering lands in the
  same wave

## Bucket 1: User-Defined Function Completeness

Current gap:

- runtime-backed user-defined functions only admit blocks, `if`, `return`, and
  `exit`
- richer function bodies still get trapped by the narrow direct-function lane or
  are rejected entirely

Representative programs to support:

```awk
function bump(x) { y = x + 1; return y }
BEGIN { print bump(2) }
```

```awk
function climb(x) {
    while (x < 3)
        x++
    print x
    return x
}
BEGIN { print climb(1) }
```

```awk
function walk(a,    k, n) {
    n = 0
    for (k in a)
        n += a[k]
    return n
}
BEGIN { a["x"] = 1; a["y"] = 2; print walk(a) }
```

Implementation direction:

- widen runtime-backed function lowering to admit assignment, loops, print,
  delete, `break`, `continue`, and expression statements where AWK semantics
  allow them
- collapse or retire the direct-function-only lowering route once the
  runtime-backed route can carry the same programs
- keep function-local scope and return semantics pinned by direct tests

## Bucket 2: Multi-Subscript Array Completeness

Current gap:

- runtime-backed lowering only handles one logical subscript per array access
- reads, writes, and deletes reject `extra_indexes`

Representative programs to support:

```awk
BEGIN { a[1, 2] = 3; print a[1, 2] }
```

```awk
BEGIN { a["x", "y"] = 1; delete a["x", "y"]; print a["x", "y"] }
```

```awk
BEGIN {
    a[1, 2] = 3
    a[4, 5] = 6
    for (k in a)
        print k
}
```

Implementation direction:

- define the runtime key-encoding path for multi-subscript array access and
  deletion
- keep iteration semantics aligned with AWK's composite-key behavior
- make sure `sub()` / `gsub()` and any other array-element lvalue paths inherit
  the same support once multi-subscript lvalues are legal

## Bucket 3: Side-Effectful Ternary Completeness

Current gap:

- ternary branches are currently restricted to side-effect-free expressions

Representative programs to support:

```awk
BEGIN { x = 0; print (1 ? ++x : 0); print x }
```

```awk
BEGIN { s = "aba"; print (1 ? sub(/a/, "b", s) : 0); print s }
```

```awk
BEGIN { i = 1; print (i < 2 ? (x = 3) : (x = 4)); print x }
```

Implementation direction:

- lower ternary through explicit control flow and temporary storage rather than
  assuming both branches are pure
- preserve AWK short-circuit behavior so only the selected branch executes
- extend `--ir` tests to pin the control-flow shape for these cases

## Bucket 4: Remaining Grammar-Valid Builtin Shape Restrictions

Current gap:

- some grammar-valid builtin call forms still rely on a narrower lowering shape
  than AWK permits

Representative programs to support:

```awk
BEGIN { fmt = "%d %d\n"; printf fmt, 1, 2 }
```

```awk
BEGIN { fmt = "%s:%d\n"; printf fmt, "x", 3 }
```

Implementation direction:

- make `printf` lower from dynamic format expressions rather than requiring a
  literal format string
- keep argument typing, coercion, and arity checks aligned with AWK semantics
- fold any remaining semantically valid builtin-call shape restrictions into the
  same wave instead of letting them survive as parse-only gaps

## Bucket 5: Contract Enforcement

Current gap:

- the process allowed parser widening to outrun backend execution widening

Required guardrails:

- add representative backend-execution tests for every remaining gap bucket
  before implementation lands
- keep `docs/quawk.ebnf`, `docs/design.md`, and the backend gap inventory
  aligned in the same change whenever the contract widens
- treat any new parseable-but-not-executable form as a regression

## Recommended Order

1. Baseline and guardrails
   Add representative failing tests and a checked-in execution-completeness
   matrix for the remaining buckets.

2. User-defined function completeness
   This is the largest semantic gap and removes the need to preserve the narrow
   direct-function lane as a special case.

3. Multi-subscript arrays
   This is the largest remaining data-model gap in runtime lowering.

4. Side-effectful ternary lowering
   This is self-contained once branch-capable runtime lowering is already in
   good shape.

5. Dynamic `printf` and residual builtin-shape cleanup
   This closes the remaining grammar-valid builtin-call restrictions.

6. Final grammar-to-backend audit
   Re-run the inventory and confirm that the grammar contract and compiled
   execution contract now match for the admitted language.
