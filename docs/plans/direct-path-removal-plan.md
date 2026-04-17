# Direct-Path Removal And Route Cleanup

This document records the `P33` follow-on after the POSIX closeout wave.

The product direction is unchanged:

- reusable backend/runtime lowering should be the compiled execution route
- public execution should not depend on a narrower direct-only lowering lane
- stale backend gating is routing debt, not an acceptable long-term contract

## Why This Follow-On Exists

The direct-function lane was already retired as product behavior, but
`src/quawk/jit.py` still keeps a smaller direct lowering fallback for some
`BEGIN`-only programs.

That fallback is now the main source of misleading backend failures:

- representative programs that reusable lowering can already handle still fail
  behind stale routing predicates
- some errors still describe the "direct LLVM-backed backend" as if it were an
  intended public route
- dead helper code from older direct-only paths still lives in the module and
  obscures the actual compiled execution model

The goal of `P33` is to remove that residual split rather than continue adding
feature-specific routing exceptions around it.

## Current Problem Shape

The remaining direct-lane entrypoint is centered on the fallback branch in
`lower_to_llvm_ir()` in [src/quawk/jit.py](/Users/fred/dev/quawk/src/quawk/jit.py).

Current stale or direct-only gate areas to make explicit before implementation:

- the fallback branch in `lower_to_llvm_ir()` that emits a standalone
  direct-lowered `quawk_main()`
- `supports_runtime_backend_subset()` false negatives that keep some programs
  off reusable lowering even though `lower_runtime_*` code already exists for
  the same feature family
- `has_host_runtime_only_operations()` rejections that still fire before the
  reusable route is chosen for some representative rows
- direct-only statement and expression guards in `lower_statement()` and
  `lower_numeric_expression()`
- dead or stale helper paths such as
  `lower_direct_function_program_to_llvm_ir()`,
  `supports_direct_function_backend_subset()`,
  `lower_record_program_to_llvm_ir()`, and `field_parameter_name()`

## T-284 Baseline Result

Focused routing regressions now pin the representative over-gated rows that
still expose the direct-lane split.

Current pinned state:

- `BEGIN { print $1 }` still fails during lowering with
  `field expressions require the reusable runtime backend`
- `BEGIN { x = $1 }` still fails behind the narrower direct numeric-expression
  subset, even though the closely related `BEGIN { x = $1; print x }` already
  lowers through the reusable backend path
- `BEGIN { x = a["k"] }` still fails with the
  `host-runtime-only operations are not supported by the LLVM-backed backend`
  gate, even though `BEGIN { x = a["k"]; print x }` already lowers through the
  reusable backend path
- `BEGIN { x = 1; x += 2 }` still fails behind the same pre-routing host gate,
  even though `BEGIN { x = 1; x += 2; print x }` already lowers through the
  reusable backend path
- `BEGIN { if ("a" "b") x = 1 }` still fails in the direct condition path with
  `unsupported binary operator in numeric expression: CONCAT`, even though
  `BEGIN { print ("a" "b") }` already lowers through the reusable backend path
- representative unary and increment-only forms such as `BEGIN { x = !1 }` and
  `BEGIN { x = ++y }` still fail behind the direct numeric-expression subset,
  even though the related `...; print x` variants already route through the
  reusable backend path

That leaves `T-285` to remove the restricted direct-lowering fallback and dead
direct-only helpers, then `T-286` / `T-287` / `T-288` to widen reusable
routing, prune stale diagnostics, and close execution-plus-inspection parity
for the representative rows above.
