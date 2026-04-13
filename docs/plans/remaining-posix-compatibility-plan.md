# Remaining POSIX Compatibility Plan

This plan turns the remaining product and compatibility gaps into explicit
follow-on work after `P30`.

The main split is:

- product-side end-to-end gaps: parser-admitted or partially claimed forms that
  still need a final contract decision or backend/runtime implementation
- compatibility-side corroboration gaps: implemented behavior that still needs
  final upstream-anchor cleanup or explicit disagreement policy

## Product Gaps

These are the remaining end-to-end product items that still need either
implementation or an explicit contract decision.

| Gap | Current state | T-272 classification | Notes | Follow-on |
|---|---|---|---|---|
| Compound assignment | implemented | POSIX-required, closed by `T-274` | `+=`, `-=`, `*=`, `/=`, `%=` and `^=` are ordinary AWK assignment forms and are now part of the checked-in product-side contract. | none |
| Parenthesized array-target wrappers for `for ... in`, `expr in array`, and `split()` | implemented | POSIX-required, closed by `T-275` | Parenthesized array-name wrappers in `for ... in`, `expr in array`, and `split()` target positions are now part of the checked-in product-side contract. | none |
| `sub()` / `gsub()` array-element lvalues beyond the current admitted subset | partially admitted | POSIX-required | Scalar variables, fields, and one-subscript array elements already work. Multi-subscript array-element lvalues should be treated as ordinary AWK lvalues rather than permanent exclusions. | `T-276` |
| `sub()` / `gsub()` non-lvalue expression targets | parser-admitted | intentionally out of contract | Calls such as `sub(/a/, \"b\", expr())` should fail clearly rather than remain parse-only because they do not name an assignable AWK target. | `T-276` |
| Builtin names beyond the current claimed subset | unsupported | extension-only or intentionally out of contract | The checked-in builtin subset is the full current POSIX builtin claim. T-272 does not identify any remaining builtin names as POSIX-required product work. | `T-276` |
| Top-level items outside `PatternAction` / `FunctionDef` | parser-admitted | intentionally out of contract | These are generic parser shapes, not part of the intended AWK program contract. | `T-273` |
| Narrow direct-function execution lane | internal technical debt | non-contract internal debt | Claimed function programs should not need a separate restricted lowering route long term. The lane should be retired or documented as internal debt only. | `T-277` |

## T-272 Baseline Result

The checked-in product-side classification baseline is now:

- compound assignment has been closed and is now part of the checked-in product-side contract
- parenthesized array-target wrappers are now part of the checked-in contract
- extra top-level item shapes are intentionally out of contract rather than
  future public widening targets
- broader `sub()` / `gsub()` targets split into:
  - POSIX-required array-element lvalues
  - intentionally out-of-contract non-lvalue expressions
- builtin names beyond the current claimed subset are not currently treated as
  remaining POSIX-required work
- the narrow direct-function execution lane is internal debt, not a public
  contract promise

## T-274 Result

Compound assignment is now implemented end to end for the current public
execution and inspection paths. The remaining P31 work continues with
`T-275` and later buckets.

## T-275 Result

Parenthesized array-target wrappers in `for ... in`, `expr in array`, and
`split()` target positions are now implemented end to end for the current
public execution and inspection paths. The remaining P31 work continues with
`T-276` and later buckets.

## Compatibility Corroboration Gaps

These are not broad product-surface blockers, but they still matter for a
credible end-to-end POSIX claim.

| Gap | Current state | Notes |
|---|---|---|
| Field-rebuild corroboration re-audit | product behavior implemented | The remaining work is to re-audit the reviewed `p.35` / `t.NF` style anchors and promote or classify them precisely. |
| Record-target `gsub` reviewed skip | product note still narrowed | The current contract still mentions a narrower reviewed backend skip that should be either fixed or replaced with a precise classified divergence. |
| `rand()` corroboration strategy | direct-test-only product coverage | The references disagree on deterministic seeded output, so the final compatibility policy still needs to be made explicit. |

## Planned Phases

### P31: Remaining Contract Classification And Gap Closure

Goal:

- classify every remaining product-side gap as POSIX-required, extension, or
  intentionally out of contract
- implement the POSIX-required items that remain open
- reduce internal special cases such as the narrow direct-function lane

### P32: Final POSIX Compatibility Corroboration

Goal:

- close the remaining corroboration-only gaps for the implemented POSIX surface
- promote clean anchors where possible
- classify any true upstream disagreements explicitly instead of leaving them as
  reviewed but vague skips
