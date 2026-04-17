# Expression Surface Widening Analysis

This note captures the data we would need before approving any future roadmap
wave that widens the intentionally unclaimed POSIX expression surface.

It complements the operator-by-operator matrix in
[expression-surface-decision-table.md](expression-surface-decision-table.md).

## Required Data

To make a widening decision responsibly, we need evidence in four buckets.

### 1. Product Scope Data

We need an explicit product decision, not an implied “finish everything”
assumption.

Required answers:

- do we want `quawk` to claim broader POSIX expression compatibility now, or is
  the current subset sufficient?
- what is the ranked next target set?
  Typical candidates:
  - `||`
  - broader comparisons: `<=`, `>`, `>=`, `!=`
  - broader arithmetic: `-`, `*`, `/`, `%`, `^`
  - ternary
  - match operators
  - `in`
- should the chosen forms become part of the public AOT-backed contract
  immediately, or only become parser/runtime-admitted first?

Without those answers, “widen the expression surface” is too vague and tends to
turn into accidental scope creep.

### 2. Current Implementation Gap Data

For each candidate form, we need a precise inventory of:

- what already parses
- what already executes in the host path
- what already executes through the public backend/runtime path
- what already supports `--ir` / `--asm`
- what is only partially implemented or only reachable through narrower
  support gates

The current repo already shows that parser admission is broader than the
claimed backend contract. That gap needs to be measured per operator/form, not
described as one umbrella row.

### 3. Compatibility Evidence

We need both repo-owned evidence and reference corroboration.

Required evidence:

- direct local tests for each candidate operator/form
- clean corroborating reference anchors where they exist
- an explicit list of upstream cases that are unsuitable as anchors even if
  they mention the feature
- expected AWK semantics for the tricky coercion and control cases, especially:
  - string-vs-numeric comparison choice
  - short-circuit behavior
  - truthiness of regex and expression terms
  - `in` semantics against arrays
  - ternary precedence and branch coercion
  - exponentiation precedence and associativity

### 4. Cost and Risk Data

We need implementation-shape data before approving a widening wave.

Required questions:

- how much of each candidate is parser work vs runtime work vs backend/runtime
  ABI work?
- does any candidate force a larger normalization or lowering redesign?
- would widening the claim create new inspection-parity debt?
- are there high-risk semantics or stability risks for the form?

The highest-risk candidates are likely:

- match operators
- `in`
- exponentiation
- ternary

## Minimum Decision Package

Before approving a widening wave, the minimum useful artifact is one table with
rows for each candidate form and these columns:

- parses today
- host executes today
- public backend executes today
- `--ir` / `--asm` today
- clean direct tests exist
- clean reference anchor exists
- known semantic risks
- estimated implementation cost
- recommended claim action

That is exactly what the companion decision table starts to provide.

## Approved Widening Phase Shape

The widening work was intentionally structured as ranked backend-first phases
rather than one large POSIX-expression wave.

Completed phase order:

1. `P21`: logical-or and broader comparisons
2. `P22`: broader arithmetic
3. `P23`: ternary
4. `P24`: match operators and `in`

These phases are backend-first by contract:

- any newly claimed form must execute through the compiled backend/runtime path
- ordinary public `quawk` execution must not depend on Python host semantics
  for newly claimed forms
- `--ir` / `--asm` support must land before the widened claim is considered
  complete
- direct tests and clean corroborating evidence must be checked in before the
  public contract widens

The main decision boundary is not parser readiness. The parser already admits
most of the surface. The real question is whether the repo is ready to take on
the backend/runtime, inspection, test, and corroboration cost for each ranked
wave.

## T-208 Baseline Result

The checked-in `P21` baseline now makes the next widening wave explicit:

- logical-or: `||`
- broader comparisons: `<=`, `>`, `>=`, `!=`

The current starting point is intentionally narrowed to representative
expression cases, not `print` redirection ambiguities:

- representative parenthesized `||`, `<=`, `>`, `>=`, and `!=` programs still
  fail cleanly outside the current claimed surface
- the broader comparison family remains unclaimed until the exact `P21`
  surface is widened coherently under one backend-only contract

The baseline also makes the backend-only claim rule explicit:

- these forms remain unclaimed until ordinary public `quawk` execution runs
  them through the compiled backend/runtime path
- public Python host execution is not an acceptable dependency for a widened
  claim
- `--ir` / `--asm` support, focused routing coverage, and direct target tests
  are part of the baseline before implementation begins

## T-209 And T-210 Backend Implementation Result

The backend/runtime implementation work for the exact `P21` target forms is now
checked in:

- representative `||` programs now execute through ordinary public
  backend/runtime execution with no host fallback
- representative `<=`, `>`, `>=`, and `!=` programs now execute through
  ordinary public backend/runtime execution with no host fallback
- the direct runtime-backed path now preserves the intended `P21`
  string-vs-numeric comparison behavior for representative mixed operand cases

This closes the implementation side of the original `P21` widening target
without widening the public claim yet. `T-212` remains the contract-rebaseline
step for that.

## T-211 Inspection And Corroboration Result

The inspection and corroboration closeout for `P21` is now explicit:

- representative `||`, `<=`, `>`, `>=`, and `!=` programs now succeed under
  `--ir` and `--asm`
- focused routing regressions now pin those representative forms to the
  compiled backend/runtime path rather than the residual host-boundary path
- the existing runnable reference subset already contains clean corroborating
  anchors for this wave, especially `one-true-awk:p.7`, `one-true-awk:p.8`,
  `one-true-awk:p.21a`, and `one-true-awk:t.next`

That leaves `T-212` as a pure public-contract rebaseline step, not an
implementation or evidence gap.

## T-212 Public-Contract Rebaseline Result

The public contract now reflects the completed `P21` wave:

- `||`, `<=`, `>`, `>=`, and `!=` are now part of the claimed
  backend/runtime expression surface
- the earlier `P21` target rows are no longer planned follow-on work
- the remaining unclaimed expression surface now starts at broader arithmetic
  only because `P22` is the next widening wave

## T-213 P22 Baseline Result

The checked-in `P22` baseline fixes the exact next arithmetic widening target:

- `-`
- `*`
- `/`
- `%`
- `^`

The direct baseline pins those forms as the next backend-only widening wave
with representative arithmetic execution, inspection, and routing checks.

## T-214 And T-215 Backend Implementation Result

The backend/runtime implementation work for the exact `P22` target forms is now
checked in:

- representative subtraction, multiplication, and division programs now
  execute through ordinary public backend/runtime execution with no host
  fallback
- representative modulo and exponentiation programs now execute through
  ordinary public backend/runtime execution with no host fallback
- direct execution checks now pin representative arithmetic precedence and
  result semantics for the widened family

## T-216 Inspection And Corroboration Result

The inspection and corroboration closeout for `P22` is now explicit:

- representative `-`, `*`, `/`, `%`, and `^` programs now succeed under `--ir`
  and `--asm`
- focused routing regressions now pin those representative forms to the
  compiled backend/runtime path rather than the residual host-boundary path
- the existing runnable reference subset already contains clean corroborating
  anchors for this wave, especially `one-true-awk:p.25`,
  `one-true-awk:p.34`, `one-true-awk:p.36`, and `one-true-awk:p.44`

That leaves `T-217` as a pure public-contract rebaseline step, not an
implementation or evidence gap.

## T-218 P23 Baseline Result

The checked-in `P23` baseline fixes the exact next ternary widening target:

- pure ternary expressions over the current claimed numeric/string subset

The direct baseline pins those forms as the next backend-only widening wave
with representative ternary execution, inspection, and routing checks.

## T-219 Backend Implementation Result

The backend/runtime implementation work for the exact `P23` target forms is now
checked in:

- representative numeric ternary programs now execute through ordinary public
  backend/runtime execution with no host fallback
- representative string ternary programs now execute through ordinary public
  backend/runtime execution with no host fallback
- direct execution checks now pin representative nested ternary and branch
  coercion behavior for the widened pure-expression family

## T-220 Inspection And Corroboration Result

The inspection and corroboration closeout for `P23` is now explicit:

- representative ternary programs now succeed under `--ir` and `--asm`
- focused routing regressions now pin those representative forms to the
  compiled backend/runtime path rather than the residual host-boundary path
- no clean checked-in reference anchor is pinned for `P23` yet, so this wave
  is currently closed by backend/runtime, routing, inspection, and runtime
  coverage instead

That leaves `T-221` as a pure public-contract rebaseline step, not an
implementation or evidence gap.

## T-221 Public-Contract Rebaseline Result

The public contract now reflects the completed `P23` wave:

- pure ternary expressions over the current claimed numeric/string subset are
  now part of the claimed backend/runtime expression surface
- the earlier `P23` target rows are no longer planned follow-on work
- the remaining unclaimed expression surface now starts at match operators and
  membership only because `P24` is the next widening wave

## T-222 P24 Baseline Result

The checked-in `P24` baseline fixes the exact final widening target from the
ranked plan:

- match operators: `~`, `!~`
- membership: `expr in array`

The direct baseline pins those forms as the next backend-only widening wave
with representative execution, inspection, and routing checks.

## T-223 And T-224 Backend Implementation Result

The backend/runtime implementation work for the exact `P24` target forms is now
checked in:

- representative `~` and `!~` programs now execute through ordinary public
  backend/runtime execution with no host fallback
- representative scalar-key `expr in array` programs now execute through
  ordinary public backend/runtime execution with no host fallback
- direct execution checks now pin representative match and membership
  semantics, including keeping `~` / `!~` separate from `match()` builtin side
  effects

## T-225 Inspection And Corroboration Result

The inspection and corroboration closeout for `P24` is now explicit:

- representative `~`, `!~`, and `in` programs now succeed under `--ir` and
  `--asm`
- focused routing regressions now pin those representative forms to the
  compiled backend/runtime path rather than the residual host-boundary path
- no clean checked-in reference anchor is pinned for `P24` yet, so this wave
  is currently closed by backend/runtime, routing, inspection, and runtime
  coverage instead

That leaves `T-226` as a pure public-contract rebaseline step, not an
implementation or evidence gap.

## T-226 Public-Contract Rebaseline Result

The public contract now reflects the completed `P24` wave:

- `~`, `!~`, and scalar-key `expr in array` membership are now part of the
  claimed backend/runtime expression surface
- the earlier `P24` target rows are no longer planned follow-on work
- all currently scheduled widening waves `P21` through `P24` are now complete
