# Expression Surface Decision Table

This table is the current decision aid for any future proposal to widen the
intentionally unclaimed POSIX expression surface beyond the current AOT-backed
contract in [SPEC.md](../../SPEC.md).

Legend:

- `yes`: explicitly evidenced in the current repo state
- `partial`: implementation or evidence exists, but the public AOT/inspection
  contract is still narrower
- `no`: no current evidence in the public backend path
- `unknown`: not yet audited precisely enough to claim either way

| Candidate form | Parses today | Host executes today | Public backend executes today | `--ir` / `--asm` today | Clean direct tests exist | Clean reference anchor exists | Known semantic risks | Estimated implementation cost to claim cleanly | Recommended claim action |
|---|---|---|---|---|---|---|---|---|---|
| `||` | yes | yes | yes | yes | yes | yes | short-circuit behavior, regex-term truthiness | medium | backend work complete; widen the public claim only in `T-212` |
| Broader comparisons: `<=`, `>`, `>=`, `!=` | yes | yes | yes | yes | yes | yes | AWK string-vs-numeric comparison choice, mixed operand-shape handling | medium | backend work complete; widen the public claim only in `T-212` |
| Broader arithmetic: `-`, `*`, `/`, `%`, `^` | yes | yes | yes | yes | yes | yes | precedence/associativity, coercion through numeric and string contexts, modulo/power edge cases | medium to high | backend work complete; widen the public claim only in `T-217` |
| Ternary: `test ? a : b` | yes | yes | yes | yes | yes | no | mixed side-effect branches remain intentionally outside the current pure-expression claim | medium | backend work complete; claim widened in `T-221` |
| Match operators: `~`, `!~` | yes | yes | yes | yes | yes | no | regex evaluation semantics, string coercion, and keeping match operators distinct from `match()` side effects | high | backend work complete; claim widened in `T-226` |
| Membership: `expr in array` | yes | yes | yes | yes | yes | no | array-key coercion and scalar-vs-array legality remain the primary semantic edges | high | backend work complete; claim widened in `T-226` |

## Notes

- The currently scheduled widening waves `P21` through `P24` are now complete.
- For every future phase, any newly claimed form must be fully implemented on
  the compiled backend/runtime path. Public Python host fallback is not an
  acceptable steady state for widened claims.

- Parser admission evidence is in
  [tests/test_p7_posix_core_frontend.py](../../tests/test_p7_posix_core_frontend.py).
- Host-runtime execution evidence exists broadly in
  [src/quawk/jit.py](../../src/quawk/jit.py), with selected direct runtime
  checks in [tests/test_p8_runtime_baselines.py](../../tests/test_p8_runtime_baselines.py)
  and [tests/test_jit.py](../../tests/test_jit.py).
- `P21` has now closed the backend/runtime and inspection work for `||` plus
  broader comparisons, and `T-212` has already widened that claim.
- `P22` has now closed the backend/runtime and inspection work for broader
  arithmetic, and `T-217` has already widened that claim.
- `P23` has now closed the backend/runtime and inspection work for ternary, and
  `T-221` has already widened that claim.
- Runnable reference anchors already exist for `P21`, especially
  `one-true-awk:p.7`, `one-true-awk:p.8`, `one-true-awk:p.21a`, and
  `one-true-awk:t.next`.
- Runnable reference anchors also already exist for `P22`, especially
  `one-true-awk:p.25`, `one-true-awk:p.34`, `one-true-awk:p.36`, and
  `one-true-awk:p.44`.
- No clean checked-in reference anchor is pinned for `P23` or `P24` yet; those
  waves are currently closed by backend/runtime, routing, inspection, and
  runtime coverage instead.
