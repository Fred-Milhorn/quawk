# Execution Completeness Matrix

This matrix records the representative grammar-valid, semantically admitted
backend gaps that remain after the host-fallback cleanup and the expression
widening waves.

Target interpretation:

- the desired steady state is:
  - parses today: `yes`
  - frontend semantic validation passes today: `yes`
  - public backend execution exists today: `yes`
  - `--ir` / `--asm` works today: `yes`
- any row still present in this matrix is execution-completeness debt
- these rows should fail clearly today rather than fall back to Python-side AWK
  semantics

Column meanings:

- `Public execute today`
  Whether ordinary `quawk` execution succeeds through the compiled
  backend/runtime path for the representative program.
- `Inspection today`
  Whether `lower_to_llvm_ir()` and therefore `--ir` / `--asm` succeed for the
  representative program today.
- `Current blocker`
  The specific current narrowing that keeps the representative program outside
  the compiled contract.

| Bucket | Representative program | Parses today | Frontend semantic validation passes today | Public execute today | Inspection today | Public host fallback exists today | Current blocker | Direct baseline coverage today | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Dynamic `printf` format | `BEGIN { fmt = "%d %d\n"; printf fmt, 1, 2 }` | yes | yes | no | no | no | Runtime-backed `printf` still requires a literal format string as its first argument. | yes | Public execution currently raises `public execution does not support programs outside the compiled backend/runtime subset`; inspection raises `host-runtime-only operations are not supported by the LLVM-backed backend`. |

Current exclusions:

- semantically invalid forms are not part of this matrix; this baseline tracks
  only grammar-valid forms that the frontend already admits
- rows are representative buckets, not an exhaustive list of every blocked
  syntax permutation inside each bucket
- no row in this matrix currently keeps public Python host fallback alive

## T-267 Narrowing Result

`T-267` removes runtime-backed imperative function bodies from this matrix:

- the representative imperative function program now executes through the
  compiled backend/runtime path
- the same program now lowers cleanly for `--ir` and `--asm`
- the remaining row in this matrix is now dynamic `printf` formats

## T-268 Narrowing Result

`T-268` removes multi-subscript array access from this matrix:

- the representative composite-array program now executes through the compiled
  backend/runtime path
- the same program now lowers cleanly for `--ir` and `--asm`
- the remaining row in this matrix is now dynamic `printf` formats

## T-269 Narrowing Result

`T-269` removes side-effectful ternary branches from this matrix:

- the representative side-effectful ternary program now executes through the
  compiled backend/runtime path
- the same program now lowers cleanly for `--ir` and `--asm`
- the remaining row in this matrix is now dynamic `printf` formats

## T-266 Baseline Result

`T-266` pins the current baseline for the remaining execution-completeness
buckets:

- the representative gap buckets are now recorded in this checked-in matrix
- ordinary public execution fails clearly for each remaining representative row
  rather than falling back to Python-side AWK semantics
- `lower_to_llvm_ir()` also fails clearly for the same remaining rows, so `--ir`
  and `--asm` stay aligned with ordinary execution
- direct tests now pin those remaining failure modes before the next
  implementation wave continues
