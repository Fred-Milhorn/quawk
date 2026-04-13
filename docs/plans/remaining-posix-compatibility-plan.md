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

| Gap | Current state | POSIX-required | Notes |
|---|---|---|---|
| Compound assignment | parser-admitted, not yet claimed end to end | yes | `+=`, `-=`, `*=`, `/=`, `%=` and `^=` are still outside the claimed backend/runtime contract. |
| Non-name `for (k in ...)` iterables | parser-admitted, out of contract | no | AWK arrays are not first-class values; this is extension-like surface admitted by the generic parser shape. |
| Non-name right-hand sides for `expr in array` | parser-admitted, out of contract | no | Like `for ... in`, this is an extension-like shape rather than a POSIX requirement. |
| Non-name `split()` targets | parser-admitted, out of contract | no | Forms like `split($0, a[i])` or `split($0, $1)` still need an explicit contract decision. |
| Broader `sub()` / `gsub()` targets | partially admitted, out of contract | mixed | Scalar, field, and one-subscript array targets work; broader target shapes still need classification. |
| Builtin names beyond the current claimed subset | unsupported | mixed | Remaining names must be classified as POSIX-required, extension, or intentionally unsupported. |
| Top-level items outside `PatternAction` / `FunctionDef` | parser-admitted, out of contract | no | These are not part of the intended AWK program contract. |
| Narrow direct-function execution lane | internal technical debt | n/a | Claimed function programs should not need a separate restricted lowering route long term. |

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
