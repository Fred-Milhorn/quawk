# Claimed Value-Fallback Matrix

This matrix records the representative currently claimed public cases that
still rely on host-assisted value semantics after `T-202`.

Target interpretation:

- the desired steady state for claimed AWK behavior is:
  - host semantic execution exists: `no`
  - public host fallback exists: `no`
  - public backend execution exists: `yes`
- rows in this matrix are narrower than the old residual unclaimed-expression
  boundary from `P19`
- these rows remain product debt because they are already part of the claimed
  public surface

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
| Unset scalar string-context read | `BEGIN { print x }` | none | yes | yes | `requires_host_runtime_value_execution(program) == True` | yes | The current backend path still treats a plain scalar-name print too numerically; the empty-string string-context view of an unset scalar is not yet trusted there. |
| Unset scalar propagation through assignment | `BEGIN { y = x; print y }` | none | yes | yes | `requires_host_runtime_value_execution(program) == True` | no | The remaining debt is not just the initial read of `x`; it is also preserving the unset scalar's string view through a later scalar assignment and print flow. |
| Mixed unset-scalar string and numeric views | `BEGIN { print x; print x + 1 }` | none | yes | yes | `requires_host_runtime_value_execution(program) == True` | yes | One claimed program still needs both AWK views of the same unset scalar: string `""` in a plain print and numeric `0` in arithmetic. The current backend path is not yet the trusted execution path for that combination. |
| Plain scalar-name read after assignment | `BEGIN { x = 1; print x }` | none | yes | yes | `requires_host_runtime_value_execution(program) == True` | yes | This row is narrower route-conservative debt: the value-runtime predicate still treats the plain scalar-name print path as host-assisted even when a simple numeric assignment already exists in the program. |
| String `-v` plus user-defined functions | `function f(y) { return y + 1 } BEGIN { print x; print f(1) }` | `-v x=hello` | yes | yes | `initial_variables_require_string_runtime(initial_variables) == True` and `has_function_definitions(program) == True` | no | The remaining special-case route is the combination of string-valued preassignment plus the direct function subset, not string `-v` by itself. |

Current exclusions:

- `-v x=hello 'BEGIN { print x }'` is not part of this remaining matrix; the
  current public path already keeps that case on the backend.
- `-v x=12 'BEGIN { print x + 1; print x "a" }'` is also not part of this
  remaining matrix; it is already covered by the scalar-string backend path.
