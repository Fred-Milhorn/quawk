# Performance Optimization Implementation Notes

This document contains technical implementation details for each phase of the performance optimization roadmap.

## P25: Static Variable Slots

### Data Structures

```python
# In semantics.py or a new slot_allocation.py module

@dataclass
class VariableSlot:
    """Compile-time allocated slot for a variable."""
    name: str
    index: int            # Index in the state struct
    inferred_type: str     # 'numeric' | 'string' | 'mixed' | 'unknown'
    storage: str           # 'slot' | 'hash' (fallback)


@dataclass  
class SlotAllocation:
    """Result of variable slot allocation pass."""
    slots: list[VariableSlot]
    numeric_count: int      # First N slots are numeric
    string_count: int       # Next M slots are string
    mixed_count: int        # Remaining slots are mixed
    state_struct_type: str  # LLVM struct type definition
```

### State Struct Layout

```llvm
; Current: no variable slots
%struct.qk_runtime = type { ... }

; After P25: extended with variable section
%quawk.state = type {
    ; Reserved fields
    double %exit_requested,
    double %range_1_active,  ; range pattern state
    ; ... other control flow state ...
    
    ; Variable slots (allocated per-program)
    double %var_0,           ; e.g., i (numeric)
    double %var_1,           ; e.g., j (numeric)
    ptr   %var_2,            ; e.g., s (string)
    %quawk.cell %var_3,     ; e.g., x (mixed)
}
```

### Code Generation Changes

**Before (current `jit.py`):**

```python
def variable_address(name: str, state: LoweringState) -> str:
    if name in state.variable_slots:
        return state.variable_slots[name]
    # Fallback to creating new alloca
    slot = state.next_temp(f"var.{name}")
    state.allocas.append(f"  {slot} = alloca double")
    state.variable_slots[name] = slot
    return slot
```

**After (P25):**

```python
def variable_address(name: str, state: LoweringState) -> str:
    slot_info = state.slot_allocation.get_slot(name)
    if slot_info is None:
        # Unknown variable at compile time - use hash lookup
        return emit_hash_lookup(name, state)
    
    if slot_info.storage == 'slot':
        # Direct slot access
        return f"getelementptr %quawk.state, ptr %state, i32 0, i32 {slot_info.index}"
    
    # Fallback to hash
    return emit_hash_lookup(name, state)
```

### Runtime Changes

Add accessor functions for slot-based variables:

```c
// In qk_runtime.h

// Fast path: direct slot access
double qk_slot_get_number(qk_runtime *rt, int64_t slot_index);
void qk_slot_set_number(qk_runtime *rt, int64_t slot_index, double value);
const char *qk_slot_get_string(qk_runtime *rt, int64_t slot_index);
void qk_slot_set_string(qk_runtime *rt, int64_t slot_index, const char *value);

// Get the combined cell for mixed-type slots
qk_cell *qk_slot_get_cell(qk_runtime *rt, int64_t slot_index);
```

### Tasks

| ID | Task | Depends | Acceptance |
|---|---|---|---|
| P25-T01 | Design slot allocation data structures | - | Structs defined, reviewed |
| P25-T02 | Implement slot allocation pass over AST | - | Pass produces SlotAllocation |
| P25-T03 | Generate LLVM struct type for state | P25-T02 | `--ir` shows struct definition |
| P25-T04 | Add runtime slot accessor functions | - | Functions compile and link |
| P25-T05 | Update lowering to use slot addresses | P25-T02, P25-T03 | Numeric variables use slots |
| P25-T06 | Fallback to hash for unknown variables | P25-T05 | Dynamic variables still work |
| P25-T07 | Add tests for slot-based variables | P25-T05 | Tests pass |
| P25-T08 | Benchmark slot vs hash access | P25-T07 | Numbers show improvement |

---

## P26: Type Inference

### Type Lattice

```
          mixed
         /      \
    numeric    string
         \      /
          unknown (bottom, no value yet)
```

Join operation: `join(numeric, string) = mixed`

### Inference Rules

```python
# In a new type_inference.py module

class TypeLattice:
    UNKNOWN = 'unknown'
    NUMERIC = 'numeric'
    STRING = 'string'
    MIXED = 'mixed'
    
    @staticmethod
    def join(type1: str, type2: str) -> str:
        if type1 == type2:
            return type1
        if type1 == TypeLattice.UNKNOWN:
            return type2
        if type2 == TypeLattice.UNKNOWN:
            return type1
        return TypeLattice.MIXED
    
    @staticmethod
    def can_be_numeric(type: str) -> bool:
        return type in (TypeLattice.UNKNOWN, TypeLattice.NUMERIC, TypeLattice.MIXED)
    
    @staticmethod
    def can_be_string(type: str) -> bool:
        return type in (TypeLattice.UNKNOWN, TypeLattice.STRING, TypeLattice.MIXED)
```

### Inference Pass

```python
class TypeInference:
    """Forward type inference over normalized AST."""
    
    def __init__(self):
        self.variable_types: dict[str, str] = {}
    
    def infer_program(self, program: Program) -> dict[str, str]:
        # Pass 1: collect assignments
        for item in program.items:
            self.infer_item(item)
        
        # Pass 2: propagate through control flow
        # (conservative: assume loops can execute any number of times)
        
        return self.variable_types
    
    def infer_item(self, item) -> None:
        if isinstance(item, BeginPattern | EndPattern):
            self.infer_statements(item.action.statements)
        # ... handle other item types
    
    def infer_assignment(self, target: str, value: Expr) -> str:
        value_type = self.infer_expr(value)
        
        # Update variable type
        current = self.variable_types.get(target, TypeLattice.UNKNOWN)
        self.variable_types[target] = TypeLattice.join(current, value_type)
        
        return value_type
    
    def infer_expr(self, expr: Expr) -> str:
        match expr:
            case NumericLiteralExpr():
                return TypeLattice.NUMERIC
            
            case StringLiteralExpr():
                return TypeLattice.STRING
            
            case NameExpr(name=name):
                return self.variable_types.get(name, TypeLattice.UNKNOWN)
            
            case BinaryExpr(op=op, left=left, right=right):
                left_type = self.infer_expr(left)
                right_type = self.infer_expr(right)
                
                if op in (BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, 
                          BinaryOp.DIV, BinaryOp.MOD, BinaryOp.POW):
                    # Arithmetic implies numeric operands
                    return TypeLattice.NUMERIC
                
                if op == BinaryOp.CONCAT:
                    return TypeLattice.STRING
                
                # Comparisons are numeric if both operands are numeric
                if op in COMPARISON_OPS:
                    if left_type == TypeLattice.NUMERIC and right_type == TypeLattice.NUMERIC:
                        return TypeLattice.NUMERIC
                    return TypeLattice.MIXED
                
                # ... other operators
            
            case FieldExpr():
                return TypeLattice.MIXED  # Fields can be either
            
            # ... other expression types
```

### Type Annotations in AST

```python
# Add type annotation pass after normalization

@dataclass
class TypedExpr:
    """Expression with inferred type."""
    expr: Expr
    inferred_type: str

def annotate_program_types(program: Program, 
                           types: dict[str, str]) -> Program:
    """Annotate expressions with inferred types."""
    # Recursively annotate the AST
    # Store type info for use during lowering
```

### Tasks

| ID | Task | Depends | Acceptance |
|---|---|---|---|
| P26-T01 | Define type lattice and join operation | - | Lattice operations tested |
| P26-T02 | Implement expression type inference | P26-T01 | Simple expressions infer correctly |
| P26-T03 | Implement variable type propagation | P26-T02 | Variables get consistent types |
| P26-T04 | Handle control flow conservatively | P26-T03 | Loops don't lose type info |
| P26-T05 | Add field access type (always mixed) | P26-T02 | Fields typed as mixed |
| P26-T06 | Store type annotations in lowering state | P26-T04, P26-T05 | State has type info |
| P26-T07 | Add tests for type inference | P26-T04 | All inference tests pass |

---

## P27: Specialized Operations

### Numeric Fast Path

**Condition:** Both operands are known numeric, comparison operator.

```python
def lower_comparison(expr: BinaryExpr, state: LoweringState) -> str:
    left_type = state.type_info.get_type(expr.left)
    right_type = state.type_info.get_type(expr.right)
    
    if left_type == 'numeric' and right_type == 'numeric':
        return lower_numeric_comparison(expr, state)
    else:
        return lower_generic_comparison(expr, state)

def lower_numeric_comparison(expr: BinaryExpr, state: LoweringState) -> str:
    left = lower_numeric_expression(expr.left, state)
    right = lower_numeric_expression(expr.right, state)
    
    op_map = {
        BinaryOp.LT: 'ult',
        BinaryOp.LE: 'ule', 
        BinaryOp.GT: 'ugt',
        BinaryOp.GE: 'uge',
        BinaryOp.EQ: 'ueq',
        BinaryOp.NE: 'une',
    }
    
    result = state.next_temp('cmp')
    state.instructions.append(
        f"  {result} = fcmp {op_map[expr.op]} double {left}, {right}"
    )
    return result
```

### String Fast Path

**Condition:** Both operands known string, comparison or concatenation.

```python
def lower_concat(expr: BinaryExpr, state: LoweringState) -> str:
    left_type = state.type_info.get_type(expr.left)
    right_type = state.type_info.get_type(expr.right)
    
    if left_type == 'string' and right_type == 'string':
        # Both are strings - direct concat
        left = lower_string_expression(expr.left, state)
        right = lower_string_expression(expr.right, state)
        return emit_runtime_call('qk_concat', [state.runtime_param, left, right])
    else:
        # Mixed types - use full coercion
        return lower_generic_concat(expr, state)
```

### Slot-Based Numeric Variable Access

```python
def lower_numeric_variable(name: str, state: LoweringState) -> str:
    slot = state.slot_allocation.get_slot(name)
    
    if slot and slot.storage == 'slot' and slot.inferred_type == 'numeric':
        # Direct load from numeric slot
        addr = f"getelementptr %quawk.state, ptr %state, i32 0, i32 {slot.index}"
        result = state.next_temp('num')
        state.instructions.append(f"  {result} = load double, ptr {addr}")
        return result
    
    # Fallback to hash lookup
    name_ptr = lower_constant_string(name, state)
    return state.next_temp_load(
        f"call double @qk_scalar_get_number(ptr {state.runtime_param}, ptr {name_ptr})"
    )
```

### Tasks

| ID | Task | Depends | Acceptance |
|---|---|---|---|
| P27-T01 | Implement numeric comparison fast path | P26 | Direct `fcmp` in IR for numeric comparisons |
| P27-T02 | Implement numeric arithmetic fast path | P26 | Direct `fadd`/`fsub`/etc. for numeric ops |
| P27-T03 | Implement string concat fast path | P26 | Direct concat call for string operands |
| P27-T04 | Implement slot-based numeric variable access | P25, P26 | Direct load/store for slot variables |
| P27-T05 | Implement slot-based string variable access | P25, P26 | String slot read/write |
| P27-T06 | Add slow-path fallback for mixed types | P27-T01 through P27-T05 | Mixed types use full semantics |
| P27-T07 | Add tests for specialized operations | P27-T01 through P27-T06 | Tests pass, IR shows specialization |
| P27-T08 | Benchmark numeric loop performance | P27-T07 | Measurable speedup vs current |

---

## P28: LLVM Optimization Integration

### CLI Flag

```python
# In cli.py

@dataclass
class ExecutionOptions:
    optimize: bool = False  # --optimize / -O flag
    optimization_level: int = 1  # 1 = basic, 2 = aggressive
```

### Optimization Pipeline

```python
# In a new optimize.py module

def optimize_ir(ir: str, level: int = 1) -> str:
    """Run LLVM opt on generated IR."""
    opt_path = shutil.which('opt')
    if opt_path is None:
        warnings.warn("LLVM 'opt' not found, skipping optimization")
        return ir
    
    passes_by_level = {
        1: ['-passes=mem2reg,instcombine,simplifycfg,gvn'],
        2: ['-O2', '-vectorize-loops'],  # Aggressive optimization
    }
    
    passes = passes_by_level.get(level, passes_by_level[1])
    
    result = subprocess.run(
        [opt_path, *passes, '-S'],  # -S for text output
        input=ir,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        warnings.warn(f"Optimization failed: {result.stderr}")
        return ir
    
    return result.stdout
```

### Integration

```python
# In jit.py

def execute(program: Program, options: ExecutionOptions | None = None) -> int:
    ensure_public_execution_supported(program)
    ir = build_public_execution_llvm_ir(program)
    
    if options and options.optimize:
        ir = optimize_ir(ir, level=options.optimization_level)
    
    return execute_llvm_ir(ir)
```

### IR Inspection

```python
def handle_ir_flag(args) -> None:
    ir = build_public_execution_llvm_ir(program)
    
    if args.optimize or args.optimized_ir:
        ir = optimize_ir(ir)
    
    print(ir)
```

`T-253` is implemented in the CLI using a raw-argv rewrite for
`--ir=optimized`, so plain `--ir` still prints the unoptimized module while the
inspection alias requests optimized IR explicitly.

### Tasks

| ID | Task | Depends | Acceptance |
|---|---|---|---|
| P28-T01 | Add `--optimize` / `-O` CLI flag | - | Flag parses correctly |
| P28-T02 | Implement `optimize_ir()` function | - | Function invokes opt |
| P28-T03 | Integrate optimization into execute path | P28-T02 | Optimized IR executes |
| P28-T04 | Add `--ir=optimized` for inspection | P28-T02 | Shows optimized IR |
| P28-T05 | Define pass pipeline for each level | - | Level 1 and level 2 pipelines documented |
| P28-T06 | Handle opt not found gracefully | P28-T02 | Warning emitted, fallback to unoptimized |
| P28-T07 | Add tests for optimization flag | P28-T03 | Tests pass with optimization enabled |
| P28-T08 | Benchmark optimized vs unoptimized | P28-T07 | Suite covers optimizer-sensitive kernels and end-to-end AWK workloads |

---

## P29: Runtime ABI Refinement

### Current Hot Paths

A sample medium-scale run of the current runtime workload profile
(`uv run python scripts/profile_runtime_hot_paths.py --dataset-scale medium`)
shows these functions at the top of the call counts:

1. `qk_capture_string_arg` - `71,994` calls
2. `qk_get_field` - `71,994` calls
3. `qk_next_record` - `24,001` calls
4. `qk_get_fnr` - `15,996` calls
5. `qk_get_nr` - `7,999` calls
6. `qk_print_number_fragment` - `3` calls

The remaining instrumented runtime helpers were zero in this sample run.
That points the next ABI work at field capture, field lookup, and record
bookkeeping before more speculative helper reductions.

### Proposed Fast Paths

```c
// In qk_runtime.h, add inline wrappers for the slot accessors.
static inline double qk_slot_get_number_inline(qk_runtime *rt, int64_t slot) {
    return qk_slot_get_number(rt, slot);
}

static inline void qk_slot_set_number_inline(qk_runtime *rt, int64_t slot, double val) {
    qk_slot_set_number(rt, slot, val);
}

static inline const char *qk_slot_get_string_inline(qk_runtime *rt, int64_t slot) {
    return qk_slot_get_string(rt, slot);
}

static inline void qk_slot_set_string_inline(qk_runtime *rt, int64_t slot, const char *value) {
    qk_slot_set_string(rt, slot, value);
}
```

### Slot Layout in Runtime

```c
// Extend qk_runtime struct

struct qk_runtime {
    // ... existing fields ...
    
    // Slot-based variable storage
    double *numeric_slots;    // Numeric variable slots
    char **string_slots;      // String variable slots  
    struct qk_cell *mixed_slots;  // Mixed-type variable slots
    int numeric_slot_count;
    int string_slot_count;
    int mixed_slot_count;
};
```

### Allocation at Program Start

```c
qk_runtime *qk_runtime_create_with_slots(
    int argc, char **argv,
    const char *field_separator,
    int numeric_slots, int string_slots, int mixed_slots
) {
    qk_runtime *rt = qk_runtime_create(argc, argv, field_separator);
    if (!rt) return NULL;

    if (numeric_slots > 0) {
        rt->numeric_slots = calloc(numeric_slots, sizeof(double));
        rt->numeric_slot_count = numeric_slots;
    }
    // ... allocate other slot arrays
    
    return rt;
}
```

### Tasks

| ID | Task | Depends | Acceptance |
|---|---|---|---|
| P29-T01 | Profile current hot paths | - | List of top 10 called functions |
| P29-T02 | Add slot storage to runtime struct | P25 | Struct compiles with numeric, string, and mixed slot arrays |
| P29-T03 | Add slot accessor functions | P29-T02 | Functions available |
| P29-T04 | Create slot-based runtime entry point | P29-T03 | `qk_runtime_create_with_slots` works | done |
| P29-T05 | Add inline versions of hot paths | P29-T03 | Inline-able functions defined |
| P29-T06 | Update generated IR to use fast paths | P27, P29-T05 | IR emits fast-path calls |
| P29-T07 | Benchmark fast-path improvements | P29-T06 | Measurable speedup |
| P29-T08 | Document ABI stability guarantees | P29-T05 | ABI documented |

---

## Benchmark Infrastructure

### Benchmark Programs

Create `tests/benchmark/` with:

```
numeric_sum.awk
# Sum first field over 1M lines
{ s += $1 }
END { print s }

numeric_loop.awk  
# Loop-intensive numeric operations
BEGIN {
    for (i = 1; i <= 100000; i++) {
        x = x + i * 2 - 1
    }
    print x
}

field_extract.awk
# Extract and transform fields
{ print $1, $3 * $5 }

string_concat.awk
# String operations
BEGIN {
    for (i = 1; i <= 10000; i++) {
        s = s "x"
    }
    print length(s)
}
```

### Benchmark Runner

```python
# tests/benchmark/benchmark_suite.py

import subprocess
import time
from pathlib import Path

def benchmark_program(awk_file: Path, input_file: Path | None = None, 
                      iterations: int = 3) -> dict:
    """Run benchmark and return timing stats."""
    
    quawk_times = []
    gawk_times = []
    mawk_times = []  # If available
    
    for _ in range(iterations):
        # Quawk
        start = time.perf_counter()
        result = subprocess.run(
            ['quawk', str(awk_file)],
            stdin=open(input_file) if input_file else None,
            capture_output=True,
        )
        quawk_times.append(time.perf_counter() - start)
        
        # Gawk --posix
        start = time.perf_counter()
        result = subprocess.run(
            ['gawk', '--posix', '-f', str(awk_file)],
            stdin=open(input_file) if input_file else None,
            capture_output=True,
        )
        gawk_times.append(time.perf_counter() - start)
    
    return {
        'quawk_avg': sum(quawk_times) / len(quawk_times),
        'quawk_min': min(quawk_times),
        'gawk_avg': sum(gawk_times) / len(gawk_times),
        'gawk_min': min(gawk_times),
        'ratio': (sum(quawk_times) / len(quawk_times)) / (sum(gawk_times) / len(gawk_times)),
    }
```

### Success Criteria

| Benchmark | Current Ratio vs Gawk | Target Ratio |
|-----------|----------------------|--------------|
| numeric_sum.awk | ~10-50x slower | <2x slower |
| numeric_loop.awk | ~10-50x slower | <2x slower |
| field_extract.awk | ~5-10x slower | <3x slower |
| string_concat.awk | ~3-5x slower | <2x slower |

---

## Notes

1. **Incremental approach:** Each phase builds on the previous. P25 provides the foundation (slots), P26 adds intelligence (types), P27 uses that intelligence (specialization), P28 adds optimization passes, P29 refines the ABI.

2. **Backward compatibility:** All changes maintain POSIX semantics. The optimizations are about taking fast paths when semantics allow, not changing behavior.

3. **Fallback safety:** Every optimization has a fallback to the current behavior. If type inference is uncertain, use mixed type semantics. If slots aren't available, use hash table. This ensures correctness is never compromised.

4. **Profiling needed:** Before P29, profile real workloads to identify actual hot paths. The assumed hot paths above are educated guesses.

5. **Testing priority:** After each phase, run the full test suite. No optimization is worth breaking correctness.
