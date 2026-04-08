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
| Broader arithmetic: `-`, `*`, `/`, `%`, `^` | yes | yes | partial | partial | partial | partial | precedence/associativity, coercion through numeric and string contexts, modulo/power edge cases | medium to high | widen only as a deliberate arithmetic wave, not piecemeal |
| Ternary: `test ? a : b` | yes | yes | no | no | parse-only | no | branch coercion, string-vs-numeric branch result typing, backend lowering shape not yet public | medium | keep unclaimed |
| Match operators: `~`, `!~` | yes | yes | no | no | parse-only | no dedicated clean anchor yet | regex evaluation semantics, string coercion, current backend supports regex patterns but not the binary match operators as public expressions | high | keep unclaimed |
| Membership: `expr in array` | yes | yes | no | no | parse-only | no dedicated clean anchor yet | array-key coercion, scalar-vs-array legality, backend lowering for membership tests is not public | high | keep unclaimed |

## Notes

- The approved future roadmap order is:
  - `P21`: `||` plus broader comparisons
  - `P22`: broader arithmetic
  - `P23`: ternary
  - `P24`: match operators plus `in`
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
  broader comparisons; the remaining step for that wave is the claim rebaseline
  in `T-212`.
- Runnable reference anchors already exist for `P21`, especially
  `one-true-awk:p.7`, `one-true-awk:p.8`, `one-true-awk:p.21a`, and
  `one-true-awk:t.next`.
