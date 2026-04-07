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

## Current Recommendation

Based on the current repo state, the conservative recommendation remains:

- keep the broader expression surface intentionally unclaimed for now
- only reopen it as a fresh explicit roadmap wave
- start with a narrow, ranked operator/form set rather than a blanket POSIX
  expression expansion

The main reason is not parser readiness. The parser already admits most of the
surface. The real decision boundary is whether the repo wants to take on the
public AOT/inspection contract, direct tests, and reference corroboration for
those forms as a coherent new feature wave.
