# Claimed Value-Fallback Cleanup

This document records the follow-on architecture work after `P19`.

The host-runtime boundary audit distinguished two different problems:

- unclaimed host-runtime-only forms
- claimed behavior that can still rely on the host evaluator's richer value
  semantics in some public cases

`T-201` resolved only the first category. Ordinary public `quawk` now fails
clearly for representative unclaimed host-runtime-only forms instead of
silently falling back.

This document covers the second category.

## Why This Follow-On Exists

The desired steady state remains:

- host semantic execution exists: `no`
- public host fallback exists: `no`
- public backend execution exists: `yes`

That is still not fully true for every currently claimed behavior.

The remaining gap is narrower than the old residual matrix:

- some currently claimed programs can still require the Python host evaluator's
  richer value semantics
- those are not broader unclaimed operator families
- they are claimed behaviors that should eventually stay on the backend too

## Current Problem Shape

The remaining fallback path is centered on
`requires_host_runtime_value_execution()` in [src/quawk/jit.py](/Users/fred/dev/quawk/src/quawk/jit.py).

This is not the same as the host-runtime-only residual surface from `P19`.
Instead, it covers claimed programs whose semantics still depend on the richer
AWK value model available in the host evaluator.

Representative examples to audit first:

- `BEGIN { print x }`
- `BEGIN { y = x; print y }`
- other unset-scalar string-context cases
- any claimed program shapes that currently depend on host-side value coercion
  or unset-value behavior instead of the backend/runtime path

The goal is to identify exactly which claimed cases still rely on that path and
then remove it.

## T-203 Inventory Result

The first checked-in inventory pass is now complete.

The current representative matrix lives in:

- [claimed-value-fallback-matrix.md](claimed-value-fallback-matrix.md)

Current inventory result:

- the remaining claimed value-fallback path is real and narrower than the old
  `P19` residual host-runtime matrix
- the representative rows are concentrated in plain scalar-name reads and
  unset-scalar value flows that still depend on the host evaluator's richer
  AWK value model
- a second smaller bucket remains for string-valued `-v` combined with
  user-defined functions; that route is separate from
  `requires_host_runtime_value_execution()` but still part of the same claimed
  public fallback debt
- simple string-valued `-v` programs without function definitions are not part
  of the remaining matrix because the public path already keeps them on the
  backend

That leaves `T-204` to add focused routing regressions for these claimed rows,
then `T-205` / `T-206` to remove the fallback rather than just inventory it.

## T-204 Routing Regression Result

Focused routing regressions now pin the representative claimed rows from the
matrix.

Current pinned state:

- ordinary public execution still routes the representative unset-scalar and
  plain scalar-name rows through the host evaluator today
- the string-`-v` plus user-defined-function row also still routes through the
  host evaluator today, but by the separate string-initial-variable plus
  function-definition guard rather than by
  `requires_host_runtime_value_execution()`
- direct behavior regressions now pin the user-visible requirements those routes
  currently preserve, including unset-scalar string views and the string-`-v`
  plus function combination

That leaves `T-205` to close the backend/runtime value-semantics gaps instead
of only documenting the remaining host-assisted path.

## Required Outputs

### 1. Claimed Value-Fallback Inventory

Produce a checked-in list or matrix of currently claimed programs that still
depend on `requires_host_runtime_value_execution()`.

Each row should answer:

- claimed in `SPEC.md` today
- public execution currently reaches the host evaluator
- representative direct regression exists
- backend/runtime behavior already matches or still diverges
- likely reason for fallback

### 2. Focused Routing Regressions

Add direct tests that pin the remaining claimed value-fallback cases.

These regressions should prove:

- the case is part of the claimed public surface
- public execution still reaches the host evaluator today
- removing that fallback would currently change behavior

### 3. Backend Value-Semantics Closure

Implement the backend/runtime work needed to keep those claimed cases correct
without host assistance.

Expected areas:

- unset scalar handling in string contexts
- plain scalar-name reads in `print` and assignment flows
- value coercion behavior shared between unset, numeric, and string contexts

### 4. Fallback Removal For Claimed Cases

Once the backend/runtime path is correct for the claimed cases, remove the
remaining claimed value-fallback path from ordinary public execution.

After that point:

- claimed programs should not need the host evaluator
- unclaimed host-runtime-only forms should already be failing clearly from
  `T-201`

## Acceptance Direction

This follow-on should end with:

- no remaining claimed public feature that requires semantic host execution
- no remaining public host fallback for claimed programs
- backend/runtime-only public execution for the full claimed surface

That is the stronger architecture state implied by the project direction.
