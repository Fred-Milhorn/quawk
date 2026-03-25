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
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TextIO

from . import runtime_support
from .parser import (
    Action,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BinaryOp,
    BlockStmt,
    CallExpr,
    EndPattern,
    Expr,
    ExprPattern,
    FieldExpr,
    FunctionDef,
    IfStmt,
    NameExpr,
    NumericLiteralExpr,
    PatternAction,
    PrintStmt,
    Program,
    RegexLiteralExpr,
    ReturnStmt,
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
    runtime_param: str | None = None
    state_param: str | None = None
    variable_indexes: dict[str, int] = field(default_factory=dict)

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
    functions: dict[str, FunctionDef] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordContext:
    """Host-side view of the current input record for field resolution."""

    field0: str
    fields: tuple[str, ...]


class ReturnSignal(Exception):
    """Internal control-flow signal used to unwind one function return."""

    def __init__(self, value: float):
        super().__init__()
        self.value = value


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
    if has_function_definitions(program):
        execute_host_runtime(program, [], None)
        return 0
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
        result = run_process_with_current_stdin([lli_path, "--entry-function=quawk_main", str(ir_path)])
    finally:
        ir_path.unlink(missing_ok=True)

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def lower_to_llvm_ir(program: Program) -> str:
    """Lower the currently supported AST subset to LLVM IR text."""
    if has_function_definitions(program):
        raise RuntimeError("user-defined functions are not supported by the LLVM-backed backend")
    if requires_input_aware_execution(program):
        return lower_reusable_program_to_llvm_ir(program)

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


def lower_reusable_program_to_llvm_ir(program: Program) -> str:
    """Lower a record-driven program into reusable BEGIN/record/END LLVM IR."""
    begin_actions, record_items, end_actions = partition_runtime_items(program)
    variable_indexes = collect_variable_indexes(program)
    state_type = render_state_type(variable_indexes)

    declarations = [
        "declare ptr @qk_get_field(ptr, i64)",
        "declare void @qk_print_string(ptr, ptr)",
        "declare void @qk_print_number(ptr, double)",
        "declare i1 @qk_regex_match_current_record(ptr, ptr)",
    ]
    if state_type is not None:
        declarations.append(state_type)

    begin_state = LoweringState(runtime_param="%rt", state_param="%state", variable_indexes=variable_indexes)
    for action in begin_actions:
        lower_action(action, begin_state, record=None)

    record_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        string_index=begin_state.string_index,
    )
    for pattern, action in record_items:
        lower_record_item(pattern, action, record_state)

    end_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        string_index=record_state.string_index,
    )
    for action in end_actions:
        lower_action(action, end_state, record=None)

    return "\n".join(
        [
            *declarations,
            "",
            *begin_state.globals,
            *record_state.globals,
            *end_state.globals,
            "",
            render_reusable_function("quawk_begin", begin_state),
            "",
            render_reusable_function("quawk_record", record_state),
            "",
            render_reusable_function("quawk_end", end_state),
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
    begin_actions, record_items, end_actions = partition_runtime_items(program)

    for action in begin_actions:
        lower_action(action, state, record=None)
    for record in records:
        for pattern, action in record_items:
            if record_matches_pattern(pattern, record):
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
    if isinstance(statement, ReturnStmt):
        raise RuntimeError("return statements are not supported by the LLVM-backed backend")
    if not isinstance(statement, PrintStmt):
        raise RuntimeError("the current backend only supports print, assignment, block, if, and while statements")
    if len(statement.arguments) != 1:
        raise RuntimeError("the current backend only supports print with one argument")
    lower_print_expression(statement.arguments[0], state)


def lower_record_item(pattern: ExprPattern | None, action: Action, state: LoweringState) -> None:
    """Lower one record-phase item in the reusable runtime model."""
    if pattern is None:
        lower_action(action, state, record=None)
        return

    condition = lower_record_pattern(pattern, state)
    then_label = state.next_label("record.match")
    end_label = state.next_label("record.next")
    state.instructions.append(f"  br i1 {condition}, label %{then_label}, label %{end_label}")
    state.instructions.append(f"{then_label}:")
    lower_action(action, state, record=None)
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{end_label}:")


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
    slot_name = variable_address(statement.name, state)
    numeric_value = lower_numeric_expression(statement.value, state)
    state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")


def variable_address(name: str, state: LoweringState) -> str:
    """Return the address used for a scalar variable in the active lowering mode."""
    if state.state_param is not None:
        variable_index = state.variable_indexes.get(name)
        if variable_index is None:
            raise RuntimeError(f"undefined variable slot in reusable backend: {name}")
        slot_name = state.next_temp(f"varptr.{name}")
        state.instructions.append(
            f"  {slot_name} = getelementptr inbounds %quawk.state, ptr {state.state_param}, i32 0, i32 {variable_index}"
        )
        return slot_name

    existing = state.variable_slots.get(name)
    if existing is not None:
        return existing

    slot_name = state.next_temp(f"var.{name}")
    state.allocas.append(f"  {slot_name} = alloca double")
    state.variable_slots[name] = slot_name
    return slot_name


def lower_print_expression(expression: Expr, state: LoweringState) -> None:
    """Lower one supported `print` expression into side-effecting IR."""
    if state.runtime_param is not None:
        lower_runtime_print_expression(expression, state)
        return

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


def lower_runtime_print_expression(expression: Expr, state: LoweringState) -> None:
    """Lower one print expression against the reusable runtime ABI."""
    assert state.runtime_param is not None
    if isinstance(expression, StringLiteralExpr):
        global_name, byte_length = declare_string(state, expression.value)
        string_ptr = state.next_temp("strptr")
        state.instructions.extend(
            [
                emit_gep(string_ptr, byte_length, global_name),
                f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {string_ptr})",
            ]
        )
        return
    if isinstance(expression, FieldExpr):
        field_ptr = state.next_temp("field")
        state.instructions.extend(
            [
                f"  {field_ptr} = call ptr @qk_get_field(ptr {state.runtime_param}, i64 {expression.index})",
                f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {field_ptr})",
            ]
        )
        return

    numeric_value = lower_numeric_expression(expression, state)
    state.instructions.append(f"  call void @qk_print_number(ptr {state.runtime_param}, double {numeric_value})")


def lower_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a numeric expression and return the LLVM operand for its value."""
    if isinstance(expression, NumericLiteralExpr):
        return format_double_literal(expression.value)

    if isinstance(expression, NameExpr):
        slot_name = variable_address(expression.name, state)
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
        if expression.op in {BinaryOp.LESS, BinaryOp.EQUAL, BinaryOp.LOGICAL_AND}:
            condition_value = lower_condition_expression(expression, state)
            temp = state.next_temp("boolnum")
            state.instructions.append(f"  {temp} = uitofp i1 {condition_value} to double")
            return temp
        raise RuntimeError(f"unsupported binary operator in numeric expression: {expression.op.name}")

    raise RuntimeError(
        "the current backend only supports numeric literals, variable reads, and the current arithmetic/boolean subset"
    )


def lower_condition_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a supported condition expression to an LLVM `i1` value."""
    if isinstance(expression, BinaryExpr):
        if expression.op is BinaryOp.LESS:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("cmp")
            state.instructions.append(f"  {temp} = fcmp olt double {left_operand}, {right_operand}")
            return temp
        if expression.op is BinaryOp.EQUAL:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("eq")
            state.instructions.append(f"  {temp} = fcmp oeq double {left_operand}, {right_operand}")
            return temp
        if expression.op is BinaryOp.LOGICAL_AND:
            left_condition = lower_condition_expression(expression.left, state)
            rhs_label = state.next_label("and.rhs")
            false_label = state.next_label("and.false")
            end_label = state.next_label("and.end")
            phi_temp = state.next_temp("and")

            state.instructions.append(f"  br i1 {left_condition}, label %{rhs_label}, label %{false_label}")
            state.instructions.append(f"{rhs_label}:")
            right_condition = lower_condition_expression(expression.right, state)
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{false_label}:")
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{end_label}:")
            state.instructions.append(
                f"  {phi_temp} = phi i1 [ false, %{false_label} ], [ {right_condition}, %{rhs_label} ]"
            )
            return phi_temp

    numeric_value = lower_numeric_expression(expression, state)
    temp = state.next_temp("truthy")
    state.instructions.append(f"  {temp} = fcmp one double {numeric_value}, 0.000000000000000e+00")
    return temp


def lower_record_pattern(pattern: ExprPattern, state: LoweringState) -> str:
    """Lower one supported record-selection pattern in the reusable runtime model."""
    if isinstance(pattern.test, RegexLiteralExpr):
        pattern_text = pattern.test.raw_text[1:-1]
        global_name, byte_length = declare_string(state, pattern_text)
        string_ptr = state.next_temp("regexptr")
        match_result = state.next_temp("match")
        assert state.runtime_param is not None
        state.instructions.extend(
            [
                emit_gep(string_ptr, byte_length, global_name),
                (
                    f"  {match_result} = call i1 @qk_regex_match_current_record("
                    f"ptr {state.runtime_param}, ptr {string_ptr})"
                ),
            ]
        )
        return match_result
    raise RuntimeError("the reusable backend only supports regex expression patterns for record selection")


def execute_with_inputs(program: Program, input_files: list[str], field_separator: str | None) -> int:
    """Execute the current program, routing record-driven programs through the host loop."""
    if has_function_definitions(program):
        execute_host_runtime(program, input_files, field_separator)
        return 0
    if requires_input_aware_execution(program):
        llvm_ir = lower_to_llvm_ir(program)
        llvm_ir = link_reusable_execution_module(llvm_ir, program, input_files, field_separator)
        return execute_llvm_ir(llvm_ir)
    return execute(program)


def link_reusable_execution_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
) -> str:
    """Link the reusable program module, runtime support, and execution driver into one IR module."""
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        runtime_bitcode = runtime_support.compile_runtime_bitcode(temp_dir)
        program_bitcode = assemble_llvm_ir(program_llvm_ir, temp_dir / "program.bc")
        driver_ir = build_execution_driver_llvm_ir(program, program_llvm_ir, input_files, field_separator)
        driver_bitcode = assemble_llvm_ir(driver_ir, temp_dir / "driver.bc")
        linked_ir_path = temp_dir / "linked.ll"

        result = subprocess.run(
            [
                runtime_support.find_llvm_link(),
                str(runtime_bitcode),
                str(program_bitcode),
                str(driver_bitcode),
                "-S",
                "-o",
                str(linked_ir_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "llvm-link failed to link the reusable execution module")
        return linked_ir_path.read_text(encoding="utf-8")


def assemble_llvm_ir(llvm_ir: str, output_path: Path) -> Path:
    """Assemble one LLVM IR module to bitcode and return the output path."""
    source_path = output_path.with_suffix(".ll")
    source_path.write_text(llvm_ir, encoding="utf-8")
    result = subprocess.run(
        [
            runtime_support.find_llvm_as(),
            str(source_path),
            "-o",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "llvm-as failed to assemble generated IR")
    return output_path


def build_execution_driver_llvm_ir(
    program: Program,
    program_llvm_ir: str,
    input_files: list[str],
    field_separator: str | None,
) -> str:
    """Build the reusable execution driver that invokes runtime and program phases."""
    _, record_items, _ = partition_runtime_items(program)
    has_record_phase = bool(record_items)
    state_type = extract_state_type_declaration(program_llvm_ir)
    uses_state = state_type is not None

    globals_block = render_driver_globals(input_files, field_separator)
    state_setup = render_driver_state_setup(uses_state)
    record_loop = render_driver_record_loop(has_record_phase)

    return "\n".join(
        [
            "declare ptr @qk_runtime_create(i32, ptr, ptr)",
            "declare void @qk_runtime_destroy(ptr)",
            "declare i1 @qk_next_record(ptr)",
            "declare void @quawk_begin(ptr, ptr)",
            "declare void @quawk_record(ptr, ptr)",
            "declare void @quawk_end(ptr, ptr)",
            "",
            *([state_type] if state_type is not None else []),
            *([] if state_type is None else [""]),
            *globals_block,
            "",
            "define i32 @quawk_main() {",
            "entry:",
            *state_setup,
            *render_driver_runtime_create(input_files, field_separator),
            "  call void @quawk_begin(ptr %rt, ptr %state)",
            *record_loop,
            "  call void @quawk_end(ptr %rt, ptr %state)",
            "  call void @qk_runtime_destroy(ptr %rt)",
            "  ret i32 0",
            "}",
            "",
        ]
    )


def render_driver_globals(input_files: list[str], field_separator: str | None) -> list[str]:
    """Render driver globals for input-file operands and field-separator text."""
    globals_block: list[str] = []

    for index, path in enumerate(input_files):
        global_name = f"@.driver.input.{index}"
        data = path.encode("utf-8") + b"\x00"
        globals_block.append(declare_bytes(global_name, data))

    if input_files:
        elements = []
        for index, path in enumerate(input_files):
            global_name = f"@.driver.input.{index}"
            byte_length = len(path.encode("utf-8")) + 1
            elements.append(f"ptr {emit_gep_constant(byte_length, global_name)}")
        globals_block.append(
            f"@.driver.inputs = private unnamed_addr constant [{len(input_files)} x ptr] [{', '.join(elements)}]"
        )

    if field_separator is not None:
        data = field_separator.encode("utf-8") + b"\x00"
        globals_block.append(declare_bytes("@.driver.fs", data))

    return globals_block


def render_driver_state_setup(uses_state: bool) -> list[str]:
    """Render driver setup for the reusable program state pointer."""
    if not uses_state:
        return ["  %state = getelementptr i8, ptr null, i64 0"]
    return [
        "  %state.storage = alloca %quawk.state",
        "  %state = getelementptr i8, ptr %state.storage, i64 0",
    ]


def render_driver_runtime_create(input_files: list[str], field_separator: str | None) -> list[str]:
    """Render the runtime-creation call for the execution driver."""
    if input_files:
        argv_setup = [
            f"  %argv = getelementptr inbounds [{len(input_files)} x ptr], ptr @.driver.inputs, i64 0, i64 0",
        ]
        argc_operand = str(len(input_files))
    else:
        argv_setup = ["  %argv = getelementptr i8, ptr null, i64 0"]
        argc_operand = "0"

    if field_separator is None:
        fs_setup = ["  %fs = getelementptr i8, ptr null, i64 0"]
    else:
        fs_length = len(field_separator.encode("utf-8")) + 1
        fs_setup = [f"  %fs = {emit_gep_inline(fs_length, '@.driver.fs')}"]

    return [
        *argv_setup,
        *fs_setup,
        f"  %rt = call ptr @qk_runtime_create(i32 {argc_operand}, ptr %argv, ptr %fs)",
    ]


def render_driver_record_loop(has_record_phase: bool) -> list[str]:
    """Render the per-record runtime loop in the execution driver."""
    if not has_record_phase:
        return []
    return [
        "  br label %record.cond",
        "record.cond:",
        "  %has.record = call i1 @qk_next_record(ptr %rt)",
        "  br i1 %has.record, label %record.body, label %record.done",
        "record.body:",
        "  call void @quawk_record(ptr %rt, ptr %state)",
        "  br label %record.cond",
        "record.done:",
    ]


def extract_state_type_declaration(program_llvm_ir: str) -> str | None:
    """Extract the reusable state-type declaration from one lowered program module."""
    for line in program_llvm_ir.splitlines():
        if line.startswith("%quawk.state = type "):
            return line
    return None


def requires_input_aware_execution(program: Program) -> bool:
    """Report whether `program` needs concrete input records during execution."""
    pattern_action_count = sum(1 for item in program.items if isinstance(item, PatternAction))
    return has_input_aware_patterns(program) or has_end_pattern(program) or pattern_action_count > 1


def has_input_aware_patterns(program: Program) -> bool:
    """Report whether `program` contains record-sensitive pattern actions."""
    for item in program.items:
        if not isinstance(item, PatternAction):
            continue
        if item.pattern is None:
            return True
        if isinstance(item.pattern, ExprPattern):
            return True
    return False


def has_end_pattern(program: Program) -> bool:
    """Report whether `program` contains any END action."""
    return any(isinstance(item, PatternAction) and isinstance(item.pattern, EndPattern) for item in program.items)


def execute_host_runtime(program: Program, input_files: list[str], field_separator: str | None) -> None:
    """Execute the supported subset with explicit BEGIN/record/END sequencing."""
    begin_actions, record_items, end_actions = partition_runtime_items(program)
    state = RuntimeState(functions=collect_function_definitions(program))

    for action in begin_actions:
        execute_action(action, state, record=None, locals_scope=None)

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
                    execute_action(action, state, record=record, locals_scope=None)

    for action in end_actions:
        execute_action(action, state, record=None, locals_scope=None)


def collect_record_contexts(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
) -> list[RecordContext]:
    """Materialize concrete input records for the active program execution."""
    _, record_items, _ = partition_runtime_items(program)
    if not record_items:
        return []

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
        if isinstance(item, FunctionDef):
            continue
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


def execute_action(
    action: Action,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: dict[str, float] | None,
) -> None:
    """Execute one action block in the host runtime."""
    for statement in action.statements:
        execute_statement(statement, state, record, locals_scope)


def execute_statement(
    statement: Stmt,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: dict[str, float] | None,
) -> None:
    """Execute one statement in the currently supported host-runtime subset."""
    if isinstance(statement, AssignStmt):
        value = evaluate_numeric_expression(statement.value, state, record, locals_scope)
        if locals_scope is not None and statement.name in locals_scope:
            locals_scope[statement.name] = value
        else:
            state.variables[statement.name] = value
        return
    if isinstance(statement, BlockStmt):
        for nested in statement.statements:
            execute_statement(nested, state, record, locals_scope)
        return
    if isinstance(statement, IfStmt):
        if evaluate_condition(statement.condition, state, record, locals_scope):
            execute_statement(statement.then_branch, state, record, locals_scope)
        return
    if isinstance(statement, WhileStmt):
        while evaluate_condition(statement.condition, state, record, locals_scope):
            execute_statement(statement.body, state, record, locals_scope)
        return
    if isinstance(statement, ReturnStmt):
        if locals_scope is None:
            raise RuntimeError("return is only valid inside a function")
        if statement.value is None:
            raise ReturnSignal(0.0)
        raise ReturnSignal(evaluate_numeric_expression(statement.value, state, record, locals_scope))
    if not isinstance(statement, PrintStmt) or len(statement.arguments) != 1:
        raise RuntimeError("the current runtime only supports print with one argument")
    print_value(evaluate_print_expression(statement.arguments[0], state, record, locals_scope))


def evaluate_print_expression(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: dict[str, float] | None,
) -> str | float:
    """Evaluate an expression in the forms the current runtime can print."""
    if isinstance(expression, StringLiteralExpr):
        return expression.value
    if isinstance(expression, FieldExpr):
        if record is None:
            raise RuntimeError("field expressions require an active input record")
        return resolve_field_value(expression.index, record)
    return evaluate_numeric_expression(expression, state, record, locals_scope)


def evaluate_numeric_expression(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: dict[str, float] | None,
) -> float:
    """Evaluate a numeric expression in the current host-runtime subset."""
    if isinstance(expression, NumericLiteralExpr):
        return expression.value
    if isinstance(expression, NameExpr):
        value = None
        if locals_scope is not None:
            value = locals_scope.get(expression.name)
        if value is None:
            value = state.variables.get(expression.name)
        if value is None:
            raise RuntimeError(f"undefined variable in current runtime: {expression.name}")
        return value
    if isinstance(expression, CallExpr):
        return call_function(expression, state, record, locals_scope)
    if isinstance(expression, BinaryExpr):
        if expression.op is BinaryOp.ADD:
            return evaluate_numeric_expression(
                expression.left,
                state,
                record,
                locals_scope,
            ) + evaluate_numeric_expression(expression.right, state, record, locals_scope)
        if expression.op is BinaryOp.LESS:
            return 1.0 if evaluate_condition(expression, state, record, locals_scope) else 0.0
        if expression.op is BinaryOp.EQUAL:
            left_value = evaluate_numeric_expression(expression.left, state, record, locals_scope)
            right_value = evaluate_numeric_expression(expression.right, state, record, locals_scope)
            return 1.0 if left_value == right_value else 0.0
        if expression.op is BinaryOp.LOGICAL_AND:
            if not evaluate_condition(expression.left, state, record, locals_scope):
                return 0.0
            return 1.0 if evaluate_condition(expression.right, state, record, locals_scope) else 0.0
        raise RuntimeError(f"unsupported numeric operator in current runtime: {expression.op.name}")
    raise RuntimeError(
        "the current runtime only supports numeric literals, variable reads, and the current arithmetic/boolean subset"
    )


def evaluate_condition(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: dict[str, float] | None,
) -> bool:
    """Evaluate a condition expression using the supported truthiness rules."""
    if isinstance(expression, BinaryExpr) and expression.op is BinaryOp.LESS:
        return evaluate_numeric_expression(
            expression.left,
            state,
            record,
            locals_scope,
        ) < evaluate_numeric_expression(expression.right, state, record, locals_scope)
    if isinstance(expression, BinaryExpr) and expression.op is BinaryOp.EQUAL:
        return evaluate_numeric_expression(
            expression.left,
            state,
            record,
            locals_scope,
        ) == evaluate_numeric_expression(expression.right, state, record, locals_scope)
    if isinstance(expression, BinaryExpr) and expression.op is BinaryOp.LOGICAL_AND:
        return evaluate_condition(expression.left, state, record, locals_scope) and evaluate_condition(
            expression.right,
            state,
            record,
            locals_scope,
        )
    return evaluate_numeric_expression(expression, state, record, locals_scope) != 0.0


def call_function(
    expression: CallExpr,
    state: RuntimeState,
    record: RecordContext | None,
    caller_locals: dict[str, float] | None,
) -> float:
    """Execute one user-defined function call in the current host runtime."""
    function_def = state.functions.get(expression.function)
    if function_def is None:
        raise RuntimeError(f"undefined function in current runtime: {expression.function}")
    if len(expression.args) != len(function_def.params):
        raise RuntimeError(
            f"function {expression.function} expects {len(function_def.params)} arguments, got {len(expression.args)}"
        )

    locals_scope = {
        param: evaluate_numeric_expression(argument, state, record, caller_locals)
        for param, argument in zip(function_def.params, expression.args, strict=True)
    }
    try:
        for statement in function_def.body.statements:
            execute_statement(statement, state, record, locals_scope)
    except ReturnSignal as signal:
        return signal.value
    return 0.0


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


def has_function_definitions(program: Program) -> bool:
    """Report whether `program` contains any top-level user-defined functions."""
    return any(isinstance(item, FunctionDef) for item in program.items)


def collect_function_definitions(program: Program) -> dict[str, FunctionDef]:
    """Collect function definitions in source order for host-runtime execution."""
    functions: dict[str, FunctionDef] = {}
    for item in program.items:
        if isinstance(item, FunctionDef):
            functions[item.name] = item
    return functions


def field_parameter_name(index: int) -> str:
    """Return the IR parameter name used for a supported field index."""
    if index == 0:
        return "%field0"
    if index == 1:
        return "%field1"
    raise RuntimeError("the record-loop increment only supports $0 and $1")


def collect_variable_indexes(program: Program) -> dict[str, int]:
    """Collect stable reusable-state indexes for scalar variables in `program`."""
    names: list[str] = []
    seen: set[str] = set()

    def note_name(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        names.append(name)

    def visit_expression(expression: Expr) -> None:
        if isinstance(expression, NameExpr):
            note_name(expression.name)
            return
        if isinstance(expression, BinaryExpr):
            visit_expression(expression.left)
            visit_expression(expression.right)

    def visit_statement(statement: Stmt) -> None:
        if isinstance(statement, AssignStmt):
            note_name(statement.name)
            visit_expression(statement.value)
            return
        if isinstance(statement, BlockStmt):
            for nested in statement.statements:
                visit_statement(nested)
            return
        if isinstance(statement, IfStmt):
            visit_expression(statement.condition)
            visit_statement(statement.then_branch)
            return
        if isinstance(statement, WhileStmt):
            visit_expression(statement.condition)
            visit_statement(statement.body)
            return
        if isinstance(statement, PrintStmt):
            for argument in statement.arguments:
                visit_expression(argument)

    for item in program.items:
        if not isinstance(item, PatternAction) or not isinstance(item.action, Action):
            continue
        for statement in item.action.statements:
            visit_statement(statement)

    return {name: index for index, name in enumerate(names)}


def render_state_type(variable_indexes: dict[str, int]) -> str | None:
    """Render the reusable state-struct declaration when variables are present."""
    if not variable_indexes:
        return None
    fields = ", ".join("double" for _ in variable_indexes)
    return f"%quawk.state = type {{ {fields} }}"


def render_reusable_function(name: str, state: LoweringState) -> str:
    """Render one reusable BEGIN/record/END function body."""
    return "\n".join(
        [
            f"define void @{name}(ptr %rt, ptr %state) {{",
            "entry:",
            *state.instructions,
            "  ret void",
            "}",
        ]
    )


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


def emit_gep_inline(byte_length: int, global_name: str) -> str:
    """Render an inline GEP expression from the start of a global byte array."""
    return f"getelementptr inbounds [{byte_length} x i8], ptr {global_name}, i64 0, i64 0"


def emit_gep_constant(byte_length: int, global_name: str) -> str:
    """Render a constant-expression GEP from the start of a global byte array."""
    return f"getelementptr inbounds ([{byte_length} x i8], ptr {global_name}, i64 0, i64 0)"


def run_process_with_current_stdin(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one subprocess while forwarding the current stdin source when possible."""
    stdin_handle = current_stdin_handle()
    if stdin_handle is not None:
        return subprocess.run(
            command,
            stdin=stdin_handle,
            capture_output=True,
            text=True,
            check=False,
        )

    try:
        stdin_text = sys.stdin.read()
    except OSError:
        stdin_text = ""

    return subprocess.run(command, input=stdin_text, capture_output=True, text=True, check=False)


def current_stdin_handle() -> TextIO | None:
    """Return the current stdin handle when it can be forwarded directly to a subprocess."""
    try:
        sys.stdin.fileno()
    except (AttributeError, OSError):
        return None
    return sys.stdin


def format_double_literal(value: float) -> str:
    """Format a Python float as a stable LLVM IR double literal."""
    return f"{value:.15e}"
