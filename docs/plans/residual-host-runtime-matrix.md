# Residual Host-Runtime Matrix

This matrix records the current representative public forms that still reach the
Python host runtime after `T-198`.

Target interpretation:

- the desired steady state for implemented AWK features is:
  - host semantic execution exists: `no`
  - public host fallback exists: `no`
  - public backend execution exists: `yes`
- rows in this matrix are transition debt relative to that target

Scope notes:

- these rows track representative residual forms, not every syntactic use of an
  operator family
- some narrower contexts inside these families already have claimed backend
  support
- this matrix is about the residual public boundary, not the full parser or
  host-runtime capability surface

Column meanings:

- `Host semantic execution exists today`
  The Python interpreter layer can execute the representative program.
- `Public host fallback exists today`
  Ordinary `quawk` can currently reach that Python interpreter path.
- `Public backend executes today`
  Ordinary `quawk` can keep the representative program on the compiled
  backend/runtime path instead.

| Family | Representative program | Reachable from ordinary `quawk` today | Host semantic execution exists today | Public host fallback exists today | Public backend executes today | `--ir` / `--asm` today | Claimed in `SPEC.md` today | Classification | Current direct evidence | Clean reference anchor today | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Match operators | `BEGIN { print ("abc" ~ /b/) }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete | parser coverage in `tests/test_p7_posix_core_frontend.py` | none identified | Regex-driven record selection is already claimed; binary `~` / `!~` operators are not |
| `in` | `BEGIN { a["x"] = 1; print ("x" in a) }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete | parser coverage in `tests/test_p7_posix_core_frontend.py` | none identified | Arrays and `for ... in` are claimed separately; the binary `in` operator remains outside the current claim |

Representative routing basis:

- for each row, the current representative program satisfies
  `requires_host_runtime_execution(program) == True`
- match-operator and `in` representatives also satisfy
  `requires_host_runtime_value_execution(program) == True`
- for each row, `supports_runtime_backend_subset(program) == False`
- for each row, `lower_to_llvm_ir(program)` currently raises the standard
  host-runtime-only backend error

Current classification result:

- no representative row in this matrix is currently classified as `AOT debt`
- no representative row is currently classified as `unclaimed but backend-ready`
- each current representative row is classified as
  `unclaimed and backend-incomplete`
- ordinary public execution no longer uses host fallback for these rows; they
  now fail clearly outside the current AOT-backed contract instead

That result means the current residual host-routed surface is still outside the
claimed AOT-backed contract, and the next decision is about public fallback
policy rather than about re-expanding claims immediately.

## T-211 Residual Narrowing Result

`P21` has now lifted logical-or and broader comparisons out of this residual
matrix:

- representative `||` programs now execute through the public backend/runtime
  path
- representative `<=`, `>`, `>=`, and `!=` programs now execute through the
  public backend/runtime path
- those forms therefore no longer belong in the residual host-runtime boundary
  inventory

The remaining representative residual rows are now:

- match operators
- `in`

## T-216 Residual Narrowing Result

`P22` has now lifted broader arithmetic out of this residual matrix:

- representative `-`, `*`, `/`, `%`, and `^` programs now execute through the
  public backend/runtime path
- those forms therefore no longer belong in the residual host-runtime boundary
  inventory

The remaining representative residual rows are now:

- match operators
- `in`

## T-220 Residual Narrowing Result

`P23` has now lifted ternary out of this residual matrix:

- representative pure ternary programs now execute through the public
  backend/runtime path
- those forms therefore no longer belong in the residual host-runtime boundary
  inventory

The remaining representative residual rows are now:

- match operators
- `in`
