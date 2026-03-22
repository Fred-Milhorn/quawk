# Lowering and execution backend for the currently supported subset.
# This module converts the currently supported AST subset into LLVM IR text and
# shells out to LLVM tools for assembly emission and execution.

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile

from .parser import (
    Action,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BinaryOp,
    Expr,
    FieldExpr,
    NameExpr,
    NumericLiteralExpr,
    PatternAction,
    PrintStmt,
    Program,
    StringLiteralExpr,
)


@dataclass
class LoweringState:
    """Mutable state for lowering one program into LLVM IR text."""

    globals: list[str] = field(default_factory=list)
    allocas: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    temp_index: int = 0
    string_index: int = 0
    variable_slots: dict[str, str] = field(default_factory=dict)
    uses_puts: bool = False
    uses_printf: bool = False
    numeric_format_declared: bool = False

    def next_temp(self, prefix: str) -> str:
        """Return a fresh SSA temporary name with the given prefix."""
        name = f"%{prefix}.{self.temp_index}"
        self.temp_index += 1
        return name


def emit_assembly(llvm_ir: str) -> str:
    """Run `llc` on LLVM IR and return the emitted assembly text."""
    llc_path = shutil.which("llc")
    if llc_path is None:
        raise RuntimeError("LLVM code generation tool 'llc' is not available on PATH")

    result = subprocess.run(
        [llc_path, "-o", "-", "-"],
        input=llvm_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "llc failed to produce assembly output")
    return result.stdout


def execute(program: Program) -> int:
    """Lower `program` to IR, run it with `lli`, and return the process status."""
    if is_record_program(program):
        raise RuntimeError("record-driven programs require input-aware execution")

    lli_path = shutil.which("lli")
    if lli_path is None:
        raise RuntimeError("LLVM JIT tool 'lli' is not available on PATH")

    llvm_ir = lower_to_llvm_ir(program)
    with NamedTemporaryFile(mode="w", suffix=".ll", encoding="utf-8", delete=False) as file_obj:
        file_obj.write(llvm_ir)
        ir_path = Path(file_obj.name)

    try:
        result = subprocess.run(
            [lli_path, "--entry-function=quawk_main", str(ir_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        ir_path.unlink(missing_ok=True)

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def lower_to_llvm_ir(program: Program) -> str:
    """Lower the currently supported AST subset to LLVM IR text."""
    if is_record_program(program):
        return lower_record_program_to_llvm_ir(program)

    state = LoweringState()
    for statement in collect_supported_statements(program):
        lower_statement(statement, state)

    declarations: list[str] = []
    if state.uses_puts:
        declarations.append("declare i32 @puts(ptr)")
    if state.uses_printf:
        declarations.append("declare i32 @printf(ptr, ...)")

    return "\n".join(
        [
            *declarations,
            "",
            *state.globals,
            "",
            "define i32 @quawk_main() {",
            "entry:",
            *state.allocas,
            *state.instructions,
            "  ret i32 0",
            "}",
            "",
        ]
    )


def collect_supported_statements(program: Program) -> tuple[PrintStmt | AssignStmt, ...]:
    """Extract the statements accepted by the current backend.

    The parser is intentionally broader than the current lowering path, so the
    backend validates that it only sees the AST forms the current subset can execute.
    """
    if len(program.items) != 1:
        raise RuntimeError("the current backend supports exactly one top-level pattern-action")

    item = program.items[0]
    if not isinstance(item, PatternAction):
        raise RuntimeError("the current backend only supports pattern-action items")
    if not isinstance(item.pattern, BeginPattern):
        raise RuntimeError("the current backend only supports BEGIN actions")
    if not isinstance(item.action, Action):
        raise RuntimeError("the current backend requires an action block")

    statements: list[PrintStmt | AssignStmt] = []
    for statement in item.action.statements:
        if not isinstance(statement, (PrintStmt, AssignStmt)):
            raise RuntimeError("the current backend only supports print and assignment statements")
        statements.append(statement)

    return tuple(statements)


def is_record_program(program: Program) -> bool:
    """Report whether `program` is a bare-action record processor."""
    if len(program.items) != 1:
        return False
    item = program.items[0]
    return isinstance(item, PatternAction) and item.pattern is None and isinstance(item.action, Action)


def lower_record_program_to_llvm_ir(program: Program) -> str:
    """Lower a bare-action record program to an inspectable per-record IR shape."""
    item = program.items[0]
    assert isinstance(item, PatternAction)
    assert isinstance(item.action, Action)

    declarations = ["declare i32 @puts(ptr)"]
    instructions: list[str] = []
    temp_index = 0

    def next_temp(prefix: str) -> str:
        nonlocal temp_index
        name = f"%{prefix}.{temp_index}"
        temp_index += 1
        return name

    for statement in item.action.statements:
        if not isinstance(statement, PrintStmt) or len(statement.arguments) != 1:
            raise RuntimeError("the record-loop increment only supports single-argument print statements")
        argument = statement.arguments[0]
        if not isinstance(argument, FieldExpr):
            raise RuntimeError("the record-loop increment only supports $0 and $1 field expressions")
        param_name = field_parameter_name(argument.index)
        call_temp = next_temp("call")
        instructions.append(f"  {call_temp} = call i32 @puts(ptr {param_name})")

    return "\n".join(
        [
            *declarations,
            "",
            "define i32 @quawk_record(ptr %field0, ptr %field1) {",
            "entry:",
            *instructions,
            "  ret i32 0",
            "}",
            "",
        ]
    )


def lower_statement(statement: PrintStmt | AssignStmt, state: LoweringState) -> None:
    """Lower one supported statement into side-effecting IR."""
    if isinstance(statement, AssignStmt):
        lower_assignment_statement(statement, state)
        return

    if len(statement.arguments) != 1:
        raise RuntimeError("the current backend only supports print with one argument")
    lower_print_expression(statement.arguments[0], state)


def lower_assignment_statement(statement: AssignStmt, state: LoweringState) -> None:
    """Lower a scalar numeric assignment."""
    slot_name = ensure_variable_slot(statement.name, state)
    numeric_value = lower_numeric_expression(statement.value, state)
    state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")


def ensure_variable_slot(name: str, state: LoweringState) -> str:
    """Return the stack slot used for a scalar variable, creating it if needed."""
    existing = state.variable_slots.get(name)
    if existing is not None:
        return existing

    slot_name = state.next_temp(f"var.{name}")
    state.allocas.append(f"  {slot_name} = alloca double")
    state.variable_slots[name] = slot_name
    return slot_name


def lower_print_expression(expression: Expr, state: LoweringState) -> None:
    """Lower one supported `print` expression into side-effecting IR."""
    if isinstance(expression, StringLiteralExpr):
        state.uses_puts = True
        global_name, byte_length = declare_string(state, expression.value)
        string_ptr = state.next_temp("strptr")
        call_temp = state.next_temp("call")
        state.instructions.extend(
            [
                emit_gep(string_ptr, byte_length, global_name),
                f"  {call_temp} = call i32 @puts(ptr {string_ptr})",
            ]
        )
        return

    state.uses_printf = True
    format_name, format_length = ensure_numeric_format(state)
    format_ptr = state.next_temp("fmtptr")
    numeric_value = lower_numeric_expression(expression, state)
    call_temp = state.next_temp("call")
    state.instructions.extend(
        [
            emit_gep(format_ptr, format_length, format_name),
            f"  {call_temp} = call i32 (ptr, ...) @printf(ptr {format_ptr}, double {numeric_value})",
        ]
    )


def lower_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a numeric expression and return the LLVM operand for its value."""
    if isinstance(expression, NumericLiteralExpr):
        return format_double_literal(expression.value)

    if isinstance(expression, NameExpr):
        slot_name = state.variable_slots.get(expression.name)
        if slot_name is None:
            raise RuntimeError(f"undefined variable in current backend: {expression.name}")
        temp = state.next_temp("load")
        state.instructions.append(f"  {temp} = load double, ptr {slot_name}")
        return temp

    if isinstance(expression, BinaryExpr):
        if expression.op is not BinaryOp.ADD:
            raise RuntimeError(f"unsupported binary operator in current backend: {expression.op.name}")
        left_operand = lower_numeric_expression(expression.left, state)
        right_operand = lower_numeric_expression(expression.right, state)
        temp = state.next_temp("add")
        state.instructions.append(f"  {temp} = fadd double {left_operand}, {right_operand}")
        return temp

    raise RuntimeError("the numeric-print increment currently supports only numeric literals and addition")


def execute_with_inputs(program: Program, input_files: list[str], field_separator: str | None) -> int:
    """Execute record-driven programs over input files or standard input."""
    if is_record_program(program):
        execute_record_program(program, input_files, field_separator)
        return 0
    return execute(program)


def execute_record_program(program: Program, input_files: list[str], field_separator: str | None) -> None:
    """Execute a bare-action record program using the Python host input loop."""
    item = program.items[0]
    assert isinstance(item, PatternAction)
    assert isinstance(item.action, Action)

    for line in iter_input_records(input_files):
        field0 = line.rstrip("\n")
        field1 = extract_first_field(field0, field_separator)
        for statement in item.action.statements:
            execute_record_statement(statement, field0, field1)


def iter_input_records(input_files: list[str]) -> list[str]:
    """Collect logical input records from files or standard input."""
    records: list[str] = []
    if not input_files:
        records.extend(sys.stdin.readlines())
        return records

    for path in input_files:
        if path == "-":
            records.extend(sys.stdin.readlines())
            continue
        with Path(path).open("r", encoding="utf-8") as handle:
            records.extend(handle.readlines())
    return records


def extract_first_field(line: str, field_separator: str | None) -> str:
    """Return `$1` for the current record under the supported field rules."""
    if field_separator is None:
        parts = line.split()
    else:
        parts = line.split(field_separator)
    return parts[0] if parts else ""


def execute_record_statement(statement: PrintStmt | AssignStmt, field0: str, field1: str) -> None:
    """Execute one supported record-loop statement."""
    if not isinstance(statement, PrintStmt) or len(statement.arguments) != 1:
        raise RuntimeError("the record-loop increment only supports single-argument print statements")

    argument = statement.arguments[0]
    if not isinstance(argument, FieldExpr):
        raise RuntimeError("the record-loop increment only supports $0 and $1 field expressions")
    print(resolve_field_value(argument.index, field0, field1))


def resolve_field_value(index: int, field0: str, field1: str) -> str:
    """Resolve the value of a supported field expression."""
    if index == 0:
        return field0
    if index == 1:
        return field1
    return ""


def field_parameter_name(index: int) -> str:
    """Return the IR parameter name used for a supported field index."""
    if index == 0:
        return "%field0"
    if index == 1:
        return "%field1"
    raise RuntimeError("the record-loop increment only supports $0 and $1")


def declare_string(state: LoweringState, literal: str) -> tuple[str, int]:
    """Declare one global LLVM string constant for `literal`."""
    global_name = f"@.str.{state.string_index}"
    state.string_index += 1
    data = literal.encode("utf-8") + b"\x00"
    state.globals.append(declare_bytes(global_name, data))
    return global_name, len(data)


def ensure_numeric_format(state: LoweringState) -> tuple[str, int]:
    """Declare the shared numeric print format if it is needed."""
    global_name = "@.fmt.num"
    data = b"%g\n\x00"
    if not state.numeric_format_declared:
        state.globals.append(declare_bytes(global_name, data))
        state.numeric_format_declared = True
    return global_name, len(data)


def declare_bytes(global_name: str, data: bytes) -> str:
    """Emit one global LLVM byte array constant."""
    escaped = "".join(f"\\{byte:02X}" for byte in data)
    return f'{global_name} = private unnamed_addr constant [{len(data)} x i8] c"{escaped}"'


def emit_gep(target: str, byte_length: int, global_name: str) -> str:
    """Emit a GEP from the start of a global byte array."""
    return f"  {target} = getelementptr inbounds [{byte_length} x i8], ptr {global_name}, i64 0, i64 0"


def format_double_literal(value: float) -> str:
    """Format a Python float as a stable LLVM IR double literal."""
    return f"{value:.15e}"
