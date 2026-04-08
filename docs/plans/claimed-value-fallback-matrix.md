# Claimed Value-Fallback Matrix

This matrix records the representative currently claimed public cases used to
close and track the remaining host-assisted value-semantics debt after
`T-202`.

Target interpretation:

- the desired steady state for claimed AWK behavior is:
  - host semantic execution exists: `no`
  - public host fallback exists: `no`
  - public backend execution exists: `yes`
- rows in this matrix are narrower than the old residual unclaimed-expression
  boundary from `P19`
- these rows remain product debt because they are already part of the claimed
  public surface
- after `T-206`, every representative row in this matrix is now closed and kept
  on the backend/runtime path

Column meanings:

- `Public host fallback exists today`
  Ordinary public `quawk` execution currently reaches the host evaluator for
  this representative claimed case.
- `Current routing trigger`
  The current code path that causes that host-assisted execution.
- `Representative direct behavior coverage today`
  Whether the repo already has a direct behavior regression for the case, even
  if there is not yet a focused routing regression.

| Family | Representative program | Extra public inputs | Claimed in `SPEC.md` today | Public host fallback exists today | Current routing trigger | Representative direct behavior coverage today | Likely remaining issue |
|---|---|---|---|---|---|---|---|
| Unset scalar string-context read | `BEGIN { print x }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes | Closed in `T-205`; the representative empty-string string-context view of an unset scalar is now handled on the backend/runtime path. |
| Unset scalar propagation through assignment | `BEGIN { y = x; print y }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes | Closed in `T-205`; the unset scalar string view now survives the checked-in assignment and print flow on the backend/runtime path. |
| Mixed unset-scalar string and numeric views | `BEGIN { print x; print x + 1 }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes | Closed in `T-205`; the backend/runtime path now carries the representative string `""` and numeric `0` views for the same unset scalar. |
| Plain scalar-name read after assignment | `BEGIN { x = 1; print x }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes | Closed in `T-205`; a plain scalar-name print after simple assignment no longer stays host-assisted by default. |
| String `-v` plus user-defined functions | `function f(y) { return y + 1 } BEGIN { print x; print f(1) }` | `-v x=hello` | yes | no | `supports_direct_function_backend_subset(program) == True` plus linked string preassignment setup keep public execution on the backend/runtime path | yes | Closed in `T-206`; the direct function backend now preserves the representative nonnumeric string preassignment for plain scalar prints while keeping the supported function call on the backend. |

Current exclusions:

- `-v x=hello 'BEGIN { print x }'` is not part of this remaining matrix; the
  current public path already keeps that case on the backend.
- `-v x=12 'BEGIN { print x + 1; print x "a" }'` is also not part of this
  remaining matrix; it is already covered by the scalar-string backend path.
- no representative row in this matrix now requires public host fallback.
