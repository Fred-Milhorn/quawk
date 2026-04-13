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
| `sub()` / `gsub()` array-element lvalues beyond the current admitted subset | implemented | POSIX-required, closed by `T-276` | Scalar variables, fields, and multi-subscript array-element lvalues now work as substitution targets. | none |
| Builtin names beyond the current claimed subset | unsupported | extension-only or intentionally out of contract | The checked-in builtin subset is the full current POSIX builtin claim. Names beyond that subset are not part of the product-side contract. | none |
| Top-level items outside `PatternAction` / `FunctionDef` | parser-admitted | intentionally out of contract | These are generic parser shapes, not part of the intended AWK program contract. | `T-273` |
| Narrow direct-function execution lane | retired | retired into the reusable backend path by `T-277` | The T-278 re-audit confirms this lane no longer counts as a remaining product-side gap. | none |

## T-272 Baseline Result

The checked-in product-side classification baseline is now:

- compound assignment has been closed and is now part of the checked-in product-side contract
- parenthesized array-target wrappers are now part of the checked-in contract
- substitution targets on scalar variables, fields, and multi-subscript array
  elements are now part of the checked-in contract
- builtin names beyond the current claimed subset are intentionally out of
  contract rather than future POSIX-required widening targets
- extra top-level item shapes are intentionally out of contract rather than
  future public widening targets
- the narrow direct-function execution lane is retired into the reusable
  backend path and is no longer public contract surface

## T-274 Result

Compound assignment is now implemented end to end for the current public
execution and inspection paths. The remaining P31 work continues with
`T-275` and later buckets.

## T-275 Result

Parenthesized array-target wrappers in `for ... in`, `expr in array`, and
`split()` target positions are now implemented end to end for the current
public execution and inspection paths. The remaining P31 work continues with
`T-276` and later buckets.

## T-276 Result

Substitution targets on scalar variables, fields, and multi-subscript array
elements are now implemented end to end for the current public execution and
inspection paths. Builtin names beyond the current claimed subset remain
explicitly out of contract rather than remaining POSIX-required work. The
remaining P32 work continues with `T-280` and later buckets.

## T-277 Result

The narrow direct-function execution lane is now collapsed into the reusable
backend path. Claimed function programs no longer need a separate restricted
lowering route for public execution or inspection.

## T-278 Result

The re-audit confirmed that the only remaining product-side gaps are the
explicit out-of-contract builtin-name and top-level-item forms. The narrow
direct-function execution lane is retired into the reusable backend path and
no longer belongs in the remaining gap inventory. The remaining P32 work
continues with `T-280` and later buckets.

## T-279 Baseline Result

The remaining compatibility-only closeout baseline is now explicit:

- field rebuild is already implemented, and the reviewed `p.35` / `t.NF`
  anchors are now promoted in the selected upstream subset
- record-target `gsub` remains a narrower reviewed backend skip rather than a
  product gap
- `rand()` remains direct-test-only because the pinned references still
  disagree on deterministic seeded output

The checked-in baseline now makes the record-target `gsub` skip and `rand()`
disagreement the explicit remaining corroboration-only gaps for the
implemented POSIX surface.

## T-280 Result

The field rebuild corroboration re-audit is now complete:

- the reviewed `p.35` / `t.NF` style anchors are now promoted in the selected
  upstream subset
- field rebuild remains implemented end to end, with no remaining
  corroboration gap

The remaining P32 corroboration work now continues only with the reviewed
record-target `gsub` skip and the `rand()` disagreement policy.

## Compatibility Corroboration Gaps

These are not broad product-surface blockers, but they still matter for a
credible end-to-end POSIX claim.

| Gap | Current state | Notes |
|---|---|---|
| Field rebuild corroboration re-audit | resolved | The reviewed `p.35` / `t.NF` style anchors are now promoted in the selected upstream subset. | none |
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
