# Performance Optimization Roadmap

This document outlines the phased plan to improve generated code efficiency in `quawk`. The current implementation prioritizes correctness and POSIX compliance. This roadmap adds performance optimizations while maintaining semantic correctness.

## Current State

The current LLVM IR generation produces correct but inefficient code:

```llvm
; Every variable access is a string-named hash lookup
%strptr.0 = getelementptr inbounds [2 x i8], ptr @.str.0, ...
call void @qk_scalar_set_number(ptr %rt, ptr %strptr.0, double 1.0)

; Comparisons use full AWK string/number semantics
%cmp = call i1 @qk_compare_values(ptr %str.capture.3, double %scalar.num.5, ...)
```

### Measured Overhead

| Operation | Current Cost | Target Cost |
|-----------|--------------|-------------|
| Variable read (numeric-only) | Hash lookup + string operations | Direct memory access |
| Variable write (numeric-only) | Hash lookup + allocation | Direct memory access |
| Numeric comparison (i <= 10) | ~6 function calls | 1 `fcmp` instruction |
| Loop iteration overhead | String materialization per iteration | SSA register or stack slot |

## Phase Overview

| Phase | Name | Primary Outcome |
|-------|------|-----------------|
| P25 | Static Variable Slots | Compile-time allocation of typed variable slots in state struct |
| P26 | Type Inference | Static inference of numeric vs string types for variables |
| P27 | Specialized Operations | Type-aware code generation for numeric/string fast paths |
| P28 | LLVM Optimization Integration | Optional optimization passes for generated IR |
| P29 | Runtime ABI Refinement | Direct-call convention improvements for hot paths |

## Phase Details

### P25: Static Variable Slots

**Objective:** Allocate known variables in fixed struct offsets instead of string-named hash table entries.

**In scope:**
- Add variable slot allocation pass during lowering
- Generate a `%quawk.state` struct with typed fields for each discovered variable
- Emit static slot indices for variables known at compile time
- Preserve fallback to string-named hash for dynamic/unknown variables
- Update runtime to support both slot-based and string-based access

**Key insight:** The current `%state` struct is unused for local variables. We can either:
- **Option A:** Extend the state struct with a typed variable section (preferred)
- **Option B:** Generate per-program struct definitions

**Example transformation:**

Before (current):
```llvm
; Each variable access does string lookup
%strptr = getelementptr [2 x i8], ptr @"i", ...
%val = call double @qk_scalar_get_number(ptr %rt, ptr %strptr)
```

After (P25):
```llvm
; Variables have fixed offsets in state
%val = load double, ptr getelementptr(%quawk.state, ptr %state, i32 0, i32 VAR_i)
```

**Exit criteria:**
- All scalar variables in `BEGIN` blocks use static slots
- Tests pass with slot-based variable access
- String-based hash access still works for dynamic cases
- `--ir` output shows static slot access for simple programs

### P26: Type Inference

**Objective:** Infer whether variables are numeric-only, string-only, or mixed at compile time.

**In scope:**
- Build a type inference pass over the normalized AST
- Track type sets: `numeric`, `string`, `mixed`, `unknown`
- Propagate types through expressions and assignments
- Identify comparison contexts where types are known
- Generate type metadata for each variable slot

**Inference rules:**

| Expression | Inferred Type |
|------------|---------------|
| `x = 1` | numeric |
| `x = "hello"` | string |
| `x = x + 1` | numeric (requires x numeric) |
| `x = x "suffix"` | string (requires x string-compatible) |
| `x = $1` | mixed (field access) |
| `x = y` | inherits y's type |
| `x++`, `++x` | numeric |
| `x < 10` | comparison uses numeric path if x is numeric |

**Conservative default:** If type cannot be proven, fall back to `mixed` (AWK's full string/number duality).

**Exit criteria:**
- Type inference pass produces type annotations for all variables
- Numeric-only variables are identified in simple programs
- Tests verify inference matches expected types
- No regression in correctness for mixed-type programs

### P27: Specialized Operations

**Objective:** Generate type-specialized IR for operations where types are known.

**In scope:**
- Numeric fast path for arithmetic operations on numeric variables
- Numeric fast path for comparisons where both sides are numeric
- String fast path for concatenation where strings are known
- Field access specialization for known-numeric indices ($1 vs $n)
- Inline numeric storage without conversion overhead
- Specialized print/printf for known types

**Example transformation:**

Before (current numeric comparison):
```llvm
; Full AWK comparison semantics
%str1 = call ptr @qk_scalar_get(ptr %rt, ptr %strptr1)
%cap1 = call ptr @qk_capture_string_arg(ptr %rt, ptr %str1)
%num1 = call double @qk_scalar_get_number(ptr %rt, ptr %strptr1)
%str2 = call ptr @qk_format_number(ptr %rt, double 10.0)
%cap2 = call ptr @qk_capture_string_arg(ptr %rt, ptr %str2)
%cmp = call i1 @qk_compare_values(ptr %cap1, double %num1, i1 true, i1 false, ...)
```

After (P27, when both operands are known numeric):
```llvm
; Direct numeric comparison
%num1 = load double, ptr %slot_i
%cmp = fcmp ule double %num1, 10.0
```

**Exit criteria:**
- Numeric-only loops show direct `fcmp` instructions in `--ir` output
- Arithmetic on numeric variables uses direct `fadd/fsub/fmul/fdiv`
- Full semantics preserved for mixed/unknown types
- Performance benchmarks show measurable improvement

### P28: LLVM Optimization Integration

**Objective:** Apply LLVM optimization passes to generated IR for constant folding, dead code elimination, and register allocation.

**In scope:**
- Add optional `-O` / `--optimize` flag to CLI
- Integration with `opt` pass pipeline for LLVM IR
- Minimum optimization passes: `-mem2reg -instcombine -simplifycfg -gvn`
- Higher optimization levels: `-O2` equivalent for performance-critical use
- Preserve debuggability by making optimization optional
- Skip optimization for `--ir` and `--asm` inspection modes by default

**Pass pipeline:**

Level 0 (current): No optimization, IR as generated.

Level 1 (recommended for debugging):
```
opt -mem2reg -instcombine -simplifycfg
```

Level 2 (recommended for production):
```
opt -O2 -vectorize-loops
```

**Implementation notes:**
- Use `subprocess` to invoke LLVM `opt` tool
- Cache optimized IR in temp file for `lli` execution
- Document LLVM version requirements

**Exit criteria:**
- `quawk -O program.awk` produces optimized IR
- Constant expressions like `1 + 2` are folded
- Dead variable stores are eliminated
- Performance benchmarks show additional improvement

### P29: Runtime ABI Refinement

**Objective:** Reduce function call overhead for hot runtime operations.

**In scope:**
- Analyze hot paths in runtime (`qk_scalar_get_number`, `qk_compare_values`, `qk_get_field`)
- Consider inline alternatives for numeric operations
- Evaluate struct-based parameter passing vs string pointers
- Add fast-path entry points for common cases (e.g., known-numeric slot access)
- Consider batched operations where applicable

**Hot path candidates:**

| Current Function | Optimization Approach |
|------------------|----------------------|
| `qk_scalar_get_number` | Slot-based direct load (P25 dependency) |
| `qk_scalar_set_number` | Slot-based direct store (P25 dependency) |
| `qk_compare_values` | Specialized `fcmp`/`strcmp` based on types (P26/P27 dependency) |
| `qk_get_field` | Cache field parsing, consider two-level access |
| `qk_print_number` | Inline fast path for integer formatting |

**Exit criteria:**
- Microbenchmarks show reduced call overhead
- No API breakage for string-based runtime consumers
- `--ir` output shows fewer function calls for hot paths

## Implementation Order

```
P25 → P26 → P27 → P28 → P29
 │      │      │      │      │
 │      │      │      │      └── Runtime ABI (depends on slots + types)
 │      │      │      └───────── LLVM optimization (works better with typed IR)
 │      │      └──────────────── Type-aware codegen (depends on inference)
 │      └─────────────────────── Type inference (depends on slot allocation)
 └────────────────────────────── Static slot allocation (foundational)
```

## Testing Strategy

### Unit Tests
- Type inference correctness (numeric, string, mixed, unknown)
- Slot allocation for variable counts and ordering
- IR generation for each specialized operation

### Integration Tests
- `BEGIN` block programs with known numeric variables
- Loop-intensive programs measuring iteration overhead
- Field access patterns with known vs dynamic indices

### Performance Benchmarks
- Target: <2x overhead vs native `awk` for numeric-heavy programs
- Benchmark suite in `tests/benchmark/`:
  - Sum calculation over 1M lines
  - Numeric field extraction and arithmetic
  - Loop iteration with numeric counter
  - Field assignment and rebuild

### Compatibility Tests
- All existing test suites pass unchanged
- Optimization levels don't change observable behavior
- `--ir` output remains inspectable

## Non-Goals

- Replacing the C runtime with LLVM-generated code (maintainability trade-off)
- JIT compilation of the runtime itself
- SIMD vectorization (requires deeper data flow analysis)
- Ahead-of-time native compilation (separate non-goal, already documented)

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Loop iteration overhead | Hash lookup + string ops per iteration | 1-2 instructions (load/increment/compare) |
| Numeric comparison | ~6 function calls | 1-2 instructions (fcmp + branch) |
| Variable access (numeric) | Hash lookup + potential allocation | Direct memory load/store |
| Constant expression | Computed at runtime | Folded at compile time |

## Open Questions

1. **Slot layout:** Should slots be indexed by variable discovery order, or should we group by type (numeric slots first, then string, then mixed)?

2. **Fallback granularity:** Should type specialization fall back per-operation, or fall back to fully generic for a whole statement if any operand is unknown?

3. **Optimization mode default:** Should `-O1` become the default for non-inspection execution, or remain opt-in?

4. **IR inspection:** Should there be a `--ir-optimized` flag separate from `--ir`, or a mode selector like `--ir=raw|optimized`?

## References

- `docs/roadmap.md` - Primary implementation roadmap
- `docs/design.md` - Architecture and execution design
- `src/quawk/jit.py` - Current LLVM IR lowering
- `src/quawk/runtime/qk_runtime.c` - C runtime implementation