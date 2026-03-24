# Lowering and execution backend for the currently supported subset.
# This module converts the currently supported AST subset into LLVM IR text and
# shells out to LLVM tools for assembly emission and execution.

from __future__ import annotations

import re
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
    BlockStmt,
    EndPattern,
    Expr,
    ExprPattern,
    FieldExpr,
    IfStmt,
    NameExpr,
    NumericLiteralExpr,
    PatternAction,
    PrintStmt,
    Program,
    RegexLiteralExpr,
    Stmt,
    StringLiteralExpr,
    WhileStmt,
)


@dataclass
class LoweringState:
    """Mutable state for lowering one program into LLVM IR text."""

    globals: list[str] = field(default_factory=list)
    allocas: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    temp_index: int = 0
    label_index: int = 0
    string_index: int = 0
    variable_slots: dict[str, str] = field(default_factory=dict)
    uses_puts: bool = False
    uses_printf: bool = False
    numeric_format_declared: bool = False
    current_record: RecordContext | None = None

    def next_temp(self, prefix: str) -> str:
        """Return a fresh SSA temporary name with the given prefix."""
        name = f"%{prefix}.{self.temp_index}"
        self.temp_index += 1
        return name

    def next_label(self, prefix: str) -> str:
        """Return a fresh LLVM basic-block label name."""
        name = f"{prefix}.{self.label_index}"
        self.label_index += 1
        return name


@dataclass
class RuntimeState:
    """Mutable host-runtime state for the currently supported interpreter path."""

    variables: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordContext:
    """Host-side view of the current input record for field resolution."""

    field0: str
    fields: tuple[str, ...]


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
    if requires_input_aware_execution(program):
        raise RuntimeError("input-aware programs require input-aware execution")

    llvm_ir = lower_to_llvm_ir(program)
    return execute_llvm_ir(llvm_ir)


def execute_llvm_ir(llvm_ir: str) -> int:
    """Run one LLVM IR module with `lli` and return its exit status."""
    lli_path = shutil.which("lli")
    if lli_path is None:
        raise RuntimeError("LLVM JIT tool 'lli' is not available on PATH")

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


def collect_supported_statements(program: Program) -> tuple[Stmt, ...]:
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

    return item.action.statements


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


def lower_input_aware_program_to_llvm_ir(
    program: Program,
    records: list[RecordContext],
) -> str:
    """Lower one concrete input-aware execution into a single `quawk_main` module."""
    state = LoweringState()
    begin_actions, record_actions, end_actions = partition_runtime_actions(program)

    for action in begin_actions:
        lower_action(action, state, record=None)
    for record in records:
        for action in record_actions:
            lower_action(action, state, record=record)
    for action in end_actions:
        lower_action(action, state, record=None)

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


def lower_statement(statement: Stmt, state: LoweringState) -> None:
    """Lower one supported statement into side-effecting IR."""
    if isinstance(statement, AssignStmt):
        lower_assignment_statement(statement, state)
        return
    if isinstance(statement, BlockStmt):
        for nested in statement.statements:
            lower_statement(nested, state)
        return
    if isinstance(statement, IfStmt):
        lower_if_statement(statement, state)
        return
    if isinstance(statement, WhileStmt):
        lower_while_statement(statement, state)
        return
    if not isinstance(statement, PrintStmt):
        raise RuntimeError("the current backend only supports print, assignment, block, if, and while statements")
    if len(statement.arguments) != 1:
        raise RuntimeError("the current backend only supports print with one argument")
    lower_print_expression(statement.arguments[0], state)


def lower_action(action: Action, state: LoweringState, record: RecordContext | None) -> None:
    """Lower one action block with an optional active input record."""
    previous_record = state.current_record
    state.current_record = record
    try:
        for statement in action.statements:
            lower_statement(statement, state)
    finally:
        state.current_record = previous_record


def lower_if_statement(statement: IfStmt, state: LoweringState) -> None:
    """Lower an `if` statement with a single then-branch."""
    then_label = state.next_label("if.then")
    end_label = state.next_label("if.end")
    condition = lower_condition_expression(statement.condition, state)
    state.instructions.append(f"  br i1 {condition}, label %{then_label}, label %{end_label}")
    state.instructions.append(f"{then_label}:")
    lower_statement(statement.then_branch, state)
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{end_label}:")


def lower_while_statement(statement: WhileStmt, state: LoweringState) -> None:
    """Lower a `while` loop over the current numeric condition subset."""
    cond_label = state.next_label("while.cond")
    body_label = state.next_label("while.body")
    end_label = state.next_label("while.end")
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{cond_label}:")
    condition = lower_condition_expression(statement.condition, state)
    state.instructions.append(f"  br i1 {condition}, label %{body_label}, label %{end_label}")
    state.instructions.append(f"{body_label}:")
    lower_statement(statement.body, state)
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{end_label}:")


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
    if isinstance(expression, FieldExpr):
        if state.current_record is None:
            raise RuntimeError("field expressions require an active input record in the current backend")
        state.uses_puts = True
        global_name, byte_length = declare_string(state, resolve_field_value(expression.index, state.current_record))
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
        if expression.op is BinaryOp.ADD:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("add")
            state.instructions.append(f"  {temp} = fadd double {left_operand}, {right_operand}")
            return temp
        raise RuntimeError(f"unsupported binary operator in numeric expression: {expression.op.name}")

    raise RuntimeError(
        "the current backend only supports numeric literals, variable reads, and addition in numeric expressions"
    )


def lower_condition_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a supported condition expression to an LLVM `i1` value."""
    if isinstance(expression, BinaryExpr) and expression.op is BinaryOp.LESS:
        left_operand = lower_numeric_expression(expression.left, state)
        right_operand = lower_numeric_expression(expression.right, state)
        temp = state.next_temp("cmp")
        state.instructions.append(f"  {temp} = fcmp olt double {left_operand}, {right_operand}")
        return temp

    numeric_value = lower_numeric_expression(expression, state)
    temp = state.next_temp("truthy")
    state.instructions.append(f"  {temp} = fcmp one double {numeric_value}, 0.000000000000000e+00")
    return temp


def execute_with_inputs(program: Program, input_files: list[str], field_separator: str | None) -> int:
    """Execute the current program, routing record-driven programs through the host loop."""
    if requires_input_aware_execution(program):
        records = collect_record_contexts(program, input_files, field_separator)
        llvm_ir = lower_input_aware_program_to_llvm_ir(program, records)
        return execute_llvm_ir(llvm_ir)
    return execute(program)


def requires_input_aware_execution(program: Program) -> bool:
    """Report whether `program` needs concrete input records during execution."""
    return is_record_program(program) or has_end_pattern(program) or len(program.items) > 1


def has_end_pattern(program: Program) -> bool:
    """Report whether `program` contains any END action."""
    return any(isinstance(item, PatternAction) and isinstance(item.pattern, EndPattern) for item in program.items)


def execute_host_runtime(program: Program, input_files: list[str], field_separator: str | None) -> None:
    """Execute the supported subset with explicit BEGIN/record/END sequencing."""
    begin_actions, record_items, end_actions = partition_runtime_items(program)
    state = RuntimeState()

    for action in begin_actions:
        execute_action(action, state, record=None)

    if record_items:
        for line in iter_input_records(input_files):
            record_text = line.rstrip("\n")
            fields = split_fields(record_text, field_separator)
            record = RecordContext(
                field0=record_text,
                fields=tuple(fields),
            )
            for pattern, action in record_items:
                if record_matches_pattern(pattern, record):
                    execute_action(action, state, record=record)

    for action in end_actions:
        execute_action(action, state, record=None)


def collect_record_contexts(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
) -> list[RecordContext]:
    """Materialize concrete input records for the active program execution."""
    _, record_items, _ = partition_runtime_items(program)
    if not record_items:
        return []
    if any(pattern is not None for pattern, _ in record_items):
        raise RuntimeError("regex-driven filtering is not supported in the current LLVM lowering path")

    records: list[RecordContext] = []
    for line in iter_input_records(input_files):
        record_text = line.rstrip("\n")
        records.append(RecordContext(
            field0=record_text,
            fields=tuple(split_fields(record_text, field_separator)),
        ))
    return records


def partition_runtime_items(
    program: Program,
) -> tuple[
        list[Action],
        list[tuple[ExprPattern | None, Action]],
        list[Action],
]:
    """Split items into ordered BEGIN actions, per-record items, and END actions."""
    begin_actions: list[Action] = []
    record_items: list[tuple[ExprPattern | None, Action]] = []
    end_actions: list[Action] = []

    for item in program.items:
        if not isinstance(item, PatternAction):
            raise RuntimeError("the current runtime only supports pattern-action items")
        if not isinstance(item.action, Action):
            raise RuntimeError("the current runtime requires an action block for each supported item")

        if item.pattern is None:
            record_items.append((None, item.action))
            continue
        if isinstance(item.pattern, BeginPattern):
            begin_actions.append(item.action)
            continue
        if isinstance(item.pattern, EndPattern):
            end_actions.append(item.action)
            continue
        if isinstance(item.pattern, ExprPattern):
            record_items.append((item.pattern, item.action))
            continue
        raise RuntimeError("the current runtime only supports BEGIN, END, and regex expression patterns")

    return begin_actions, record_items, end_actions


def partition_runtime_actions(program: Program) -> tuple[list[Action], list[Action], list[Action]]:
    """Split top-level items into ordered BEGIN, record, and END action lists."""
    begin_actions, record_items, end_actions = partition_runtime_items(program)
    record_actions = [action for pattern, action in record_items if pattern is None]
    if len(record_actions) != len(record_items):
        raise RuntimeError("regex-driven filtering is not supported in the current LLVM lowering path")
    return begin_actions, record_actions, end_actions


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


def split_fields(line: str, field_separator: str | None) -> list[str]:
    """Split one input record into AWK fields for the current supported subset."""
    if field_separator is None:
        return line.split()
    return line.split(field_separator)


def record_matches_pattern(pattern: ExprPattern | None, record: RecordContext) -> bool:
    """Report whether the current record matches a supported record-selection pattern."""
    if pattern is None:
        return True
    if isinstance(pattern.test, RegexLiteralExpr):
        return regex_matches_record(pattern.test, record)
    raise RuntimeError("the current runtime only supports regex expression patterns for record selection")


def regex_matches_record(expression: RegexLiteralExpr, record: RecordContext) -> bool:
    """Report whether `expression` matches the current record text."""
    raw_text = expression.raw_text
    if len(raw_text) < 2 or not raw_text.startswith("/") or not raw_text.endswith("/"):
        raise RuntimeError("invalid regex literal in current runtime")
    pattern_text = raw_text[1:-1]
    return re.search(pattern_text, record.field0) is not None


def execute_action(action: Action, state: RuntimeState, record: RecordContext | None) -> None:
    """Execute one action block in the host runtime."""
    for statement in action.statements:
        execute_statement(statement, state, record)


def execute_statement(statement: Stmt, state: RuntimeState, record: RecordContext | None) -> None:
    """Execute one statement in the currently supported host-runtime subset."""
    if isinstance(statement, AssignStmt):
        state.variables[statement.name] = evaluate_numeric_expression(statement.value, state, record)
        return
    if isinstance(statement, BlockStmt):
        for nested in statement.statements:
            execute_statement(nested, state, record)
        return
    if isinstance(statement, IfStmt):
        if evaluate_condition(statement.condition, state, record):
            execute_statement(statement.then_branch, state, record)
        return
    if isinstance(statement, WhileStmt):
        while evaluate_condition(statement.condition, state, record):
            execute_statement(statement.body, state, record)
        return
    if not isinstance(statement, PrintStmt) or len(statement.arguments) != 1:
        raise RuntimeError("the current runtime only supports print with one argument")
    print_value(evaluate_print_expression(statement.arguments[0], state, record))


def evaluate_print_expression(expression: Expr, state: RuntimeState, record: RecordContext | None) -> str | float:
    """Evaluate an expression in the forms the current runtime can print."""
    if isinstance(expression, StringLiteralExpr):
        return expression.value
    if isinstance(expression, FieldExpr):
        if record is None:
            raise RuntimeError("field expressions require an active input record")
        return resolve_field_value(expression.index, record)
    return evaluate_numeric_expression(expression, state, record)


def evaluate_numeric_expression(expression: Expr, state: RuntimeState, record: RecordContext | None) -> float:
    """Evaluate a numeric expression in the current host-runtime subset."""
    if isinstance(expression, NumericLiteralExpr):
        return expression.value
    if isinstance(expression, NameExpr):
        value = state.variables.get(expression.name)
        if value is None:
            raise RuntimeError(f"undefined variable in current runtime: {expression.name}")
        return value
    if isinstance(expression, BinaryExpr):
        if expression.op is BinaryOp.ADD:
            return evaluate_numeric_expression(expression.left, state,
                                               record) + evaluate_numeric_expression(expression.right, state, record)
        raise RuntimeError(f"unsupported numeric operator in current runtime: {expression.op.name}")
    raise RuntimeError(
        "the current runtime only supports numeric literals, variable reads, and addition in numeric expressions"
    )


def evaluate_condition(expression: Expr, state: RuntimeState, record: RecordContext | None) -> bool:
    """Evaluate a condition expression using the supported truthiness rules."""
    if isinstance(expression, BinaryExpr) and expression.op is BinaryOp.LESS:
        return evaluate_numeric_expression(expression.left, state,
                                           record) < evaluate_numeric_expression(expression.right, state, record)
    return evaluate_numeric_expression(expression, state, record) != 0.0


def print_value(value: str | float) -> None:
    """Print one runtime value with the same formatting the LLVM path uses today."""
    if isinstance(value, str):
        print(value)
        return
    print(f"{value:g}")


def resolve_field_value(index: int, record: RecordContext) -> str:
    """Resolve the value of a supported field expression."""
    if index == 0:
        return record.field0
    field_position = index - 1
    if 0 <= field_position < len(record.fields):
        return record.fields[field_position]
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
