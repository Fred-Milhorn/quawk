# Residual Host-Runtime Boundary Audit

This document records the next audit wave after `P18`.

The product direction is unchanged:

- the Python front end should parse, normalize, compile, and orchestrate
  execution
- the backend/runtime path should execute the AWK program
- Python-side AWK interpretation is transition debt, not a target end state

Desired steady state for an implemented AWK feature:

- host semantic execution exists: `no`
- public host fallback exists: `no`
- public backend execution exists: `yes`

## Why This Audit Exists

The current claimed AOT-backed contract is narrower than the full frontend- and
host-admitted language surface.

That is intentional, but it leaves one important follow-up question:

- which public programs still route through the Python host runtime, and why?

This audit is meant to answer that precisely before any future widening or
further architecture-tightening work starts.

## Known Residual Risk Area

The main residual host-heavy area is the broader intentionally unclaimed POSIX
expression surface, including forms such as:

- `||`
- `<=`, `>`, `>=`, `!=`
- `-`, `*`, `/`, `%`, `^`
- ternary
- match operators
- `in`

Some of these forms parse today, and some execute in the Python host runtime,
but they are not part of the current claimed AOT-backed product contract.

The audit must also check for accidental host routing of any behavior that is
already claimed in `SPEC.md`.

Terminology for this audit:

- `host semantic execution exists`
  The Python interpreter layer can execute the representative program today.
- `public host fallback exists`
  Ordinary `quawk` execution can currently reach that Python interpreter path.
- `public backend execution exists`
  Ordinary `quawk` can keep the representative program on the compiled
  backend/runtime path instead.

## Required Audit Outputs

### 1. Public Host-Routing Inventory

Trace every public path that can still lead to Python-side AWK execution.

At minimum, the audit should identify:

- direct routes to `execute_host_runtime()`
- any routing predicates that keep public execution on the host
- whether those routes are reachable from ordinary `quawk` execution,
  `execute_with_inputs()`, or related public helpers

### 2. Residual Host-Only Matrix

Produce a checked-in matrix of residual host-routed forms.

Each row should answer:

- parses today
- host semantic execution exists today
- public host fallback exists today
- public backend execution exists today
- `--ir` / `--asm` works today
- claimed in `SPEC.md` today
- representative direct tests exist
- clean corroborating reference anchor exists

Candidate rows should include at least:

- `||`
- broader comparisons
- broader arithmetic
- ternary
- match operators
- `in`

### 3. Residual Classification

Each residual host-routed form should be classified as one of:

- `AOT debt`
  Claimed behavior that still reaches the host runtime.
- `unclaimed but backend-ready`
  Already backended enough that the contract could widen with tests/docs.
- `unclaimed and backend-incomplete`
  Real implementation debt before any widening claim is possible.
- `host-only by design`
  Intentionally outside the public AOT-backed contract for now.

### 4. Focused Routing Regressions

Add direct tests that pin, for representative forms:

- whether ordinary `quawk` execution routes to the backend or the host
- whether `--ir` / `--asm` succeeds or fails
- whether current behavior is contract-backed or intentionally outside scope

### 5. Public Fallback Policy Decision

Decide what public execution should do for unclaimed host-routed forms:

- continue temporary host fallback, or
- fail explicitly as outside the AOT-backed contract

The default direction should be stricter, not looser: do not quietly normalize
host execution as long-term product behavior without an explicit decision.

### 6. Ranked Reduction Plan

After the inventory is complete, rank the likely next reduction wave.

Expected low-to-medium risk candidates:

- broader comparisons
- `||`
- broader arithmetic

Expected higher-risk candidates:

- ternary
- match operators
- `in`

### 7. Inspection-Parity Re-Audit

Any future widening or host-scope reduction should also re-audit:

- `--ir`
- `--asm`

Do not widen public execution claims while inspection parity remains silently
behind the same surface.

## Expected Decisions After The Audit

The audit should end with explicit answers to these questions:

1. Are any currently claimed behaviors still accidental host-runtime debt?
2. Which unclaimed forms are already backend-ready enough to claim cleanly?
3. Which unclaimed forms require real backend/runtime work first?
4. Should ordinary `quawk` keep temporary host fallback for unclaimed forms, or
   should those programs fail clearly outside the AOT-backed contract?
5. What is the next ranked implementation wave, if any?

## Relationship To Other Planning Docs

- [POSIX.md](../../POSIX.md) records the current public POSIX contract and the
  result of `T-192`, which kept the broader expression surface intentionally
  unclaimed.
- [expression-surface-decision-table.md](expression-surface-decision-table.md)
  records operator-by-operator widening data for the broader unclaimed POSIX
  expression surface.
- [expression-surface-widening-analysis.md](expression-surface-widening-analysis.md)
  explains the evidence needed before any future widening decision.

This document is narrower than those POSIX-planning notes. Its purpose is to
audit the remaining Python host-runtime boundary and turn that into explicit
next-step architecture work.

## T-197 Baseline Result

The baseline and scope for this audit are now explicit:

- the backend/runtime path remains the intended execution engine for AWK
  programs
- the Python host runtime remains transition debt, not part of the desired end
  state
- the desired steady state is no host semantic execution and no public host
  fallback for implemented AWK features
- this audit is not a widening plan for the broader unclaimed POSIX expression
  surface
- this audit first asks where ordinary public execution still reaches the host
  runtime, and only then what to do about it

## T-198 Inventory Result

### Current Public Routing Entry Points

The current public routing boundary is concentrated in three places:

- `execute()`
  Ordinary public execution routes to `execute_host_runtime()` when
  `requires_host_runtime_execution(program)` is true, or when
  `requires_host_runtime_value_execution(program)` is true and the
  string-initial-variable backend exception does not apply.
- `execute_with_inputs()`
  Record-driven public execution uses the same routing rules before building
  reusable backend IR.
- `lower_to_llvm_ir()`
  Inspection entry points such as `--ir` and `--asm` reject representative
  residual host-routed forms with
  `host-runtime-only operations are not supported by the LLVM-backed backend`.

### Current Residual Inventory

The checked-in residual matrix now lives in:

- [residual-host-runtime-matrix.md](residual-host-runtime-matrix.md)

That matrix records the current representative residual host-routed forms and
their public status.

Current summary:

- representative logical-or, broader-comparison, broader-arithmetic, ternary,
  match-operator, and `in` programs are all still reachable from ordinary
  public `quawk` execution
- those representative programs all still have host semantic execution today
- those representative programs all still have public host fallback today
- those representative programs do not yet have public backend execution today
- those representative programs all fail the current `--ir` / `--asm`
  inspection path
- none of those forms are currently claimed in `SPEC.md`

Preliminary boundary result:

- the current checked-in architecture audit still governs the claimed AOT-backed
  surface
- this inventory has not identified a new claimed family that is known to rely
  on the host runtime
- the remaining residual host routing is concentrated in the intentionally
  unclaimed broader expression surface

That claim-vs-residual classification is the subject of `T-200`; `T-198`
records only the current inventory.

## T-199 Routing Regression Result

Focused routing regressions now pin the representative residual forms tracked in
the matrix.

Current pinned state:

- ordinary public execution is now pinned to fail clearly rather than use host
  fallback for the representative logical-or, broader-comparison,
  broader-arithmetic, ternary, match-operator, and `in` forms
- representative `--ir` and `--asm` requests still fail with the standard
  host-runtime-only backend error for those same forms
- this routing behavior is now explicit regression coverage rather than an
  inferred property from the current implementation

That leaves `T-200` to classify those residual forms as real AOT debt,
backend-ready widening candidates, backend-incomplete work, or intentionally
out-of-contract forms.

## T-200 Classification Result

The residual classification pass is now complete.

Current result:

- no new claimed family is currently classified as `AOT debt`
- the representative residual forms tracked in the matrix are not currently
  `unclaimed but backend-ready`
- the representative logical-or, broader-comparison, broader-arithmetic,
  ternary, match-operator, and `in` rows are all currently classified as
  `unclaimed and backend-incomplete`

Why they are not classified as `AOT debt`:

- none of those representative forms are currently claimed in `SPEC.md`
- the checked-in architecture audit still governs the claimed AOT-backed surface
- the current residual host fallback is concentrated in the broader
  intentionally unclaimed expression families

Why they are not classified as `unclaimed but backend-ready`:

- ordinary public execution still relies on host fallback for those
  representative forms
- `supports_runtime_backend_subset(program)` remains false for those rows
- representative `--ir` and `--asm` requests still fail with the current
  host-runtime-only backend error

Current audit conclusion:

- the residual boundary problem is a policy and implementation question about
  intentionally unclaimed surface, not evidence of a hidden leak in the
  currently claimed contract
- `T-201` should make that public behavior explicit in the product contract

## T-201 Public Fallback Policy Result

The public fallback decision is now explicit:

- ordinary public `quawk` execution does not keep temporary host fallback for
  the representative unclaimed residual host-runtime-only forms
- those programs now fail clearly outside the current AOT-backed contract
- the Python host runtime remains available only as internal transition and
  test-oracle infrastructure, not as a public semantic execution path

Current public behavior split:

- ordinary public execution now raises a clear runtime error for representative
  unclaimed host-runtime-only programs
- representative `--ir` and `--asm` requests still fail with the current
  host-runtime-only backend error
- the residual matrix now records `public host fallback exists today: no` for
  the representative unclaimed rows

That leaves `T-202` to rebaseline the broader execution-model docs around this
now-explicit no-fallback policy.

Remaining claimed follow-on:

- `P19` resolves the unclaimed host-runtime-only surface and its public
  fallback policy
- a narrower follow-on still remains for claimed programs that can depend on
  `requires_host_runtime_value_execution()`
- that next cleanup wave is planned separately in:
  - [claimed-value-fallback-cleanup.md](claimed-value-fallback-cleanup.md)
