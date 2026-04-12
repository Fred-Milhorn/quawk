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

Current closure:

- runtime-backed imperative function bodies are now implemented and no longer
  belong in the remaining gap matrix
- multi-subscript array access is now implemented and no longer belongs in the
  remaining gap matrix
- side-effectful ternary lowering is now implemented and no longer belongs in
  the remaining gap matrix
- the remaining bucket is dynamic `printf` / builtin-shape cleanup

## Closed Bucket 1: User-Defined Function Completeness

Closed in T-267:

- runtime-backed user-defined functions now accept imperative bodies on the
  compiled backend/runtime path
- richer user-defined functions no longer need to stay on the narrow
  direct-function lane
- direct tests now pin the lowered imperative-function path

## Closed Bucket 2: Multi-Subscript Array Completeness

Closed in T-268:

- runtime-backed lowering now encodes multi-subscript array access with the
  runtime `SUBSEP` separator
- reads, writes, deletes, and string-valued array lvalues now accept composite
  keys on the compiled backend/runtime path
- direct tests now pin the representative composite-array programs

## Closed Bucket 3: Side-Effectful Ternary Completeness

Closed in T-269:

- runtime-backed ternary lowering now uses explicit control flow when a branch
  may mutate runtime-visible state
- only the selected branch executes, so increment, assignment, and builtin
  side effects no longer leak across the ternary split
- direct tests now pin the representative side-effectful ternary programs

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

2. Dynamic `printf` and residual builtin-shape cleanup
   This closes the remaining grammar-valid builtin-call restrictions.

3. Final grammar-to-backend audit
   Re-run the inventory and confirm that the grammar contract and compiled
   execution contract now match for the admitted language.
