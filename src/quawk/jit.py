# Lowering and execution backend for the currently supported subset.
# This module converts the currently supported AST subset into LLVM IR text and
# shells out to LLVM tools for assembly emission and execution.

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TextIO

from . import runtime_support
from .builtins import is_builtin_function_name, is_builtin_variable_name
from .normalization import NormalizedLoweringProgram, normalize_program_for_lowering
from .parser import (
    Action,
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignOp,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BinaryOp,
    BlockStmt,
    BreakStmt,
    CallExpr,
    ConditionalExpr,
    ContinueStmt,
    DeleteStmt,
    DoWhileStmt,
    EndPattern,
    ExitStmt,
    Expr,
    ExprPattern,
    ExprStmt,
    FieldExpr,
    FieldLValue,
    ForInStmt,
    ForStmt,
    FunctionDef,
    IfStmt,
    NameExpr,
    NameLValue,
    NextFileStmt,
    NextStmt,
    NumericLiteralExpr,
    PostfixOp,
    PatternAction,
    PostfixExpr,
    PrintfStmt,
    PrintStmt,
    Program,
    RangePattern,
    RegexLiteralExpr,
    ReturnStmt,
    Stmt,
    StringLiteralExpr,
    UnaryExpr,
    UnaryOp,
    WhileStmt,
    expression_to_lvalue,
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
    action_exit_label: str | None = None
    array_names: frozenset[str] = field(default_factory=frozenset)
    loop_string_bindings: dict[str, str] = field(default_factory=dict)
    function_defs: dict[str, FunctionDef] = field(default_factory=dict)
    return_slot: str | None = None
    return_label: str | None = None

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

    variables: dict[str, AwkValue] = field(default_factory=dict)
    arrays: dict[str, dict[str, AwkValue]] = field(default_factory=dict)
    functions: dict[str, FunctionDef] = field(default_factory=dict)
    field_separator: str | None = None
    current_filename: str = "-"


@dataclass
class RecordContext:
    """Host-side view of the current input record for field resolution."""

    field0: str
    fields: list[str]


@dataclass
class HostRuntimeRecordItem:
    """One record-phase item with optional range-pattern state."""

    pattern: ExprPattern | RangePattern | None
    action: Action | None
    range_active: bool = False


class ReturnSignal(Exception):
    """Internal control-flow signal used to unwind one function return."""

    def __init__(self, value: AwkValue):
        super().__init__()
        self.value = value


class BreakSignal(Exception):
    """Internal control-flow signal used to unwind one loop break."""


class ContinueSignal(Exception):
    """Internal control-flow signal used to skip to the next loop iteration."""


class NextSignal(Exception):
    """Internal control-flow signal used to skip to the next record."""


class NextFileSignal(Exception):
    """Internal control-flow signal used to skip the rest of the current file."""


class ExitSignal(Exception):
    """Internal control-flow signal used to terminate execution with a status."""

    def __init__(self, status: int):
        super().__init__()
        self.status = status


InitialVariables = list[tuple[str, float]]


class ValueKind(Enum):
    """Classify the host runtime's scalar values by their primary AWK view."""

    UNINITIALIZED = auto()
    NUMBER = auto()
    STRING = auto()


@dataclass(frozen=True)
class AwkValue:
    """Host-runtime scalar cell with AWK-style numeric and string coercions."""

    kind: ValueKind
    number: float = 0.0
    string: str = ""


UNINITIALIZED_VALUE = AwkValue(ValueKind.UNINITIALIZED)
NUMERIC_PREFIX_PATTERN = re.compile(r"^[ \t\r\n\f\v]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")
PRINTF_SPEC_PATTERN = re.compile(r"%(?:[-+ #0]*\d*(?:\.\d+)?)([%aAcdeEfgGiosuxX])")

LocalScope = dict[str, AwkValue]


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


def execute(program: Program, initial_variables: InitialVariables | None = None) -> int:
    """Lower `program` to IR, run it with `lli`, and return the process status."""
    if requires_host_runtime_execution(program) or requires_host_runtime_value_execution(program):
        return execute_host_runtime(program, [], None, initial_variables)
    llvm_ir = build_public_execution_llvm_ir(program, [], None, initial_variables)
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


def lower_to_llvm_ir(program: Program, initial_variables: InitialVariables | None = None) -> str:
    """Lower the currently supported AST subset to LLVM IR text."""
    if has_function_definitions(program) and not supports_direct_function_backend_subset(program):
        raise RuntimeError("user-defined functions are not supported by the LLVM-backed backend")
    if has_host_runtime_only_operations(program) and not (
        supports_runtime_backend_subset(program) or supports_direct_function_backend_subset(program)
    ):
        raise RuntimeError("host-runtime-only operations are not supported by the LLVM-backed backend")
    normalized_program = normalize_program_for_lowering(program)
    if supports_direct_function_backend_subset(program):
        return lower_direct_function_program_to_llvm_ir(program, normalized_program, initial_variables)
    if supports_runtime_backend_subset(program):
        return lower_reusable_program_to_llvm_ir(normalized_program)
    if requires_input_aware_execution(program):
        return lower_reusable_program_to_llvm_ir(normalized_program)

    state = LoweringState()
    lower_initial_variables(initial_variables or [], state)
    statements = normalized_program.direct_begin_statements
    if statements is None:
        raise RuntimeError("the current backend only supports exactly one top-level BEGIN action")
    for statement in statements:
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


def lower_direct_function_program_to_llvm_ir(
    program: Program,
    normalized_program: NormalizedLoweringProgram,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Lower one direct-BEGIN program with backend-supported user-defined functions."""
    direct_begin_statements = normalized_program.direct_begin_statements
    if direct_begin_statements is None:
        raise RuntimeError("user-defined functions currently require a direct BEGIN program in the LLVM-backed backend")

    function_defs = {
        item.name: item
        for item in program.items
        if isinstance(item, FunctionDef)
    }
    variable_indexes = normalized_program.variable_indexes
    state_type = render_state_type(variable_indexes)
    state_param = "%state" if state_type is not None else "null"
    string_index = 0
    globals_out: list[str] = []
    function_bodies: list[str] = []
    uses_puts = False
    uses_printf = False
    numeric_format_declared = False

    for function_def in function_defs.values():
        function_state = LoweringState(
            state_param="%state",
            variable_indexes=variable_indexes,
            function_defs=function_defs,
            string_index=string_index,
            numeric_format_declared=numeric_format_declared,
        )
        return_slot = function_state.next_temp("retval")
        function_state.allocas.append(f"  {return_slot} = alloca double")
        function_state.instructions.append(f"  store double 0.000000000000000e+00, ptr {return_slot}")
        function_state.return_slot = return_slot
        function_state.return_label = function_state.next_label("return")
        for index, param in enumerate(function_def.params):
            param_slot = function_state.next_temp(f"arg.{param}")
            function_state.allocas.append(f"  {param_slot} = alloca double")
            function_state.instructions.append(f"  store double %arg.{index}, ptr {param_slot}")
            function_state.variable_slots[param] = param_slot
        terminated = False
        for statement in function_def.body.statements:
            lower_statement(statement, function_state)
            if isinstance(statement, ReturnStmt):
                terminated = True
                break
        if not terminated:
            function_state.instructions.append(f"  br label %{function_state.return_label}")
        function_state.instructions.extend(
            [
                f"{function_state.return_label}:",
                f"  %retval.load = load double, ptr {return_slot}",
                "  ret double %retval.load",
            ]
        )
        globals_out.extend(function_state.globals)
        function_bodies.append(render_user_function(function_def, function_state))
        string_index = function_state.string_index
        uses_puts = uses_puts or function_state.uses_puts
        uses_printf = uses_printf or function_state.uses_printf
        numeric_format_declared = numeric_format_declared or function_state.numeric_format_declared

    main_state = LoweringState(
        state_param=state_param,
        variable_indexes=variable_indexes,
        function_defs=function_defs,
        string_index=string_index,
        uses_printf=uses_printf,
        numeric_format_declared=numeric_format_declared,
    )
    if initial_variables is not None:
        lower_initial_variables(initial_variables, main_state)
    for statement in direct_begin_statements:
        lower_statement(statement, main_state)

    globals_out.extend(main_state.globals)
    uses_puts = uses_puts or main_state.uses_puts
    uses_printf = uses_printf or main_state.uses_printf

    declarations: list[str] = []
    if uses_puts:
        declarations.append("declare i32 @puts(ptr)")
    if uses_printf:
        declarations.append("declare i32 @printf(ptr, ...)")
    if state_type is not None:
        declarations.append(state_type)

    state_setup: list[str] = []
    if state_type is not None:
        state_setup = [
            "  %state = alloca %quawk.state",
            "  store %quawk.state zeroinitializer, ptr %state",
        ]

    return "\n".join(
        [
            *declarations,
            "",
            *globals_out,
            "",
            *function_bodies,
            "",
            "define i32 @quawk_main() {",
            "entry:",
            *state_setup,
            *main_state.allocas,
            *main_state.instructions,
            "  ret i32 0",
            "}",
            "",
        ]
    )


def build_public_execution_llvm_ir(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Build the IR module used by public execution and inspection paths."""
    if initial_variables is None:
        llvm_ir = lower_to_llvm_ir(program)
    else:
        llvm_ir = lower_to_llvm_ir(program, initial_variables=initial_variables)
    if program_requires_linked_execution_module(program):
        return link_reusable_execution_module(llvm_ir, program, input_files, field_separator, initial_variables)
    return llvm_ir


def program_requires_linked_execution_module(program: Program) -> bool:
    """Report whether public execution/inspection needs the reusable driver module."""
    return supports_runtime_backend_subset(program) or requires_input_aware_execution(program)


def lower_reusable_program_to_llvm_ir(normalized_program: NormalizedLoweringProgram) -> str:
    """Lower a record-driven program into reusable BEGIN/record/END LLVM IR."""
    begin_actions = normalized_program.begin_actions
    record_items = normalized_program.record_items
    end_actions = normalized_program.end_actions
    variable_indexes = normalized_program.variable_indexes
    array_names = normalized_program.array_names
    state_type = render_state_type(variable_indexes)

    declarations = [
        "declare ptr @qk_get_field(ptr, i64)",
        "declare void @qk_set_field_number(ptr, i64, double)",
        "declare void @qk_print_string(ptr, ptr)",
        "declare void @qk_print_number(ptr, double)",
        "declare i1 @qk_regex_match_current_record(ptr, ptr)",
        "declare double @qk_get_nr(ptr)",
        "declare double @qk_get_fnr(ptr)",
        "declare double @qk_get_nf(ptr)",
        "declare ptr @qk_get_filename(ptr)",
        "declare double @qk_split_into_array(ptr, ptr, ptr, ptr)",
        "declare ptr @qk_array_get(ptr, ptr, ptr)",
        "declare void @qk_array_set_number(ptr, ptr, ptr, double)",
        "declare void @qk_array_delete(ptr, ptr, ptr)",
        "declare void @qk_array_clear(ptr, ptr)",
        "declare double @qk_array_length(ptr, ptr)",
        "declare ptr @qk_array_first_key(ptr, ptr)",
        "declare ptr @qk_array_next_key(ptr, ptr, ptr)",
        "declare ptr @qk_substr2(ptr, ptr, i64)",
        "declare ptr @qk_substr3(ptr, ptr, i64, i64)",
        "declare i64 @strlen(ptr)",
        "declare i32 @printf(ptr, ...)",
    ]
    if state_type is not None:
        declarations.append(state_type)

    begin_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        array_names=array_names,
    )
    for action in begin_actions:
        lower_action(action, begin_state, record=None)

    record_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        string_index=begin_state.string_index,
        array_names=array_names,
    )
    for record_item in record_items:
        lower_runtime_record_item(record_item.pattern, record_item.action, record_state, record_item.range_state_name)

    end_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        string_index=record_state.string_index,
        array_names=array_names,
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
        param_name = field_parameter_name(static_field_index(argument))
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
    match statement:
        case AssignStmt():
            if state.runtime_param is not None:
                lower_runtime_assignment_statement(statement, state)
            else:
                lower_assignment_statement(statement, state)
        case BlockStmt(statements=statements):
            for nested in statements:
                lower_statement(nested, state)
        case BreakStmt():
            raise RuntimeError("break statements are not supported by the current backend")
        case ContinueStmt():
            raise RuntimeError("continue statements are not supported by the current backend")
        case DeleteStmt():
            if state.runtime_param is None:
                raise RuntimeError("delete statements are not supported by the direct LLVM-backed backend")
            lower_runtime_delete_statement(statement, state)
        case IfStmt():
            lower_if_statement(statement, state)
        case WhileStmt():
            lower_while_statement(statement, state)
        case ForStmt():
            if state.runtime_param is None:
                raise RuntimeError("for statements are not supported by the direct LLVM-backed backend")
            lower_runtime_for_statement(statement, state)
        case ForInStmt():
            if state.runtime_param is None:
                raise RuntimeError("for-in statements are not supported by the direct LLVM-backed backend")
            lower_runtime_for_in_statement(statement, state)
        case ReturnStmt():
            if state.return_label is None or state.return_slot is None:
                raise RuntimeError("return statements are not supported by the LLVM-backed backend")
            return_value = (
                "0.000000000000000e+00"
                if statement.value is None
                else lower_numeric_expression(statement.value, state)
            )
            state.instructions.extend(
                [
                    f"  store double {return_value}, ptr {state.return_slot}",
                    f"  br label %{state.return_label}",
                ]
            )
        case PrintStmt(arguments=arguments):
            if len(arguments) != 1:
                raise RuntimeError("the current backend only supports print with one argument")
            lower_print_expression(arguments[0], state)
        case PrintfStmt():
            if state.runtime_param is None:
                raise RuntimeError("printf statements are not supported by the direct LLVM-backed backend")
            lower_runtime_printf_statement(statement, state)
        case ExprStmt(value=value):
            if state.runtime_param is None:
                raise RuntimeError("expression statements are not supported by the direct LLVM-backed backend")
            lower_runtime_side_effect_expression(value, state)
        case NextStmt():
            if state.runtime_param is None or state.action_exit_label is None:
                raise RuntimeError("next is not supported by the direct LLVM-backed backend")
            state.instructions.append(f"  br label %{state.action_exit_label}")
        case _:
            raise RuntimeError("the current backend only supports print, assignment, block, if, and while statements")


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


def lower_runtime_record_item(
    pattern: ExprPattern | RangePattern | None,
    action: Action | None,
    state: LoweringState,
    range_state_name: str | None = None,
) -> None:
    """Lower one record-phase item in the backend-parity runtime subset."""
    if pattern is None:
        lower_runtime_action_or_default(action, state)
        return
    if isinstance(pattern, ExprPattern):
        condition = lower_record_pattern(pattern, state)
        then_label = state.next_label("record.match")
        end_label = state.next_label("record.next")
        state.instructions.append(f"  br i1 {condition}, label %{then_label}, label %{end_label}")
        state.instructions.append(f"{then_label}:")
        lower_runtime_action_or_default(action, state)
        state.instructions.append(f"  br label %{end_label}")
        state.instructions.append(f"{end_label}:")
        return
    if isinstance(pattern, RangePattern):
        if range_state_name is None:
            raise RuntimeError("range patterns require a stable backend state slot")
        lower_runtime_range_record_item(pattern, action, state, range_state_name)
        return
    raise RuntimeError("unsupported record item in runtime-backed backend")


def lower_runtime_action_or_default(action: Action | None, state: LoweringState) -> None:
    """Lower one runtime-backed action or AWK's default print action."""
    if action is None:
        assert state.runtime_param is not None
        field_ptr = state.next_temp("field")
        state.instructions.extend(
            [
                f"  {field_ptr} = call ptr @qk_get_field(ptr {state.runtime_param}, i64 0)",
                f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {field_ptr})",
            ]
        )
        return
    lower_action(action, state, record=None)


def lower_runtime_range_record_item(
    pattern: RangePattern,
    action: Action | None,
    state: LoweringState,
    range_state_name: str,
) -> None:
    """Lower one range-pattern record item using a synthetic state slot."""
    if not isinstance(pattern.left, ExprPattern) or not isinstance(pattern.right, ExprPattern):
        raise RuntimeError("the runtime-backed backend only supports expression endpoints in range patterns")
    slot_name = variable_address(range_state_name, state)
    active_value = state.next_temp("range.active")
    active_flag = state.next_temp("range.flag")
    active_label = state.next_label("range.active")
    inactive_label = state.next_label("range.inactive")
    end_label = state.next_label("range.end")
    state.instructions.extend(
        [
            f"  {active_value} = load double, ptr {slot_name}",
            f"  {active_flag} = fcmp one double {active_value}, 0.000000000000000e+00",
            f"  br i1 {active_flag}, label %{active_label}, label %{inactive_label}",
            f"{active_label}:",
        ]
    )
    lower_runtime_action_or_default(action, state)
    right_matches = lower_record_pattern(pattern.right, state)
    keep_active = state.next_temp("range.keep")
    keep_active_num = state.next_temp("range.keepnum")
    state.instructions.extend(
        [
            f"  {keep_active} = xor i1 {right_matches}, true",
            f"  {keep_active_num} = uitofp i1 {keep_active} to double",
            f"  store double {keep_active_num}, ptr {slot_name}",
            f"  br label %{end_label}",
            f"{inactive_label}:",
        ]
    )
    left_matches = lower_record_pattern(pattern.left, state)
    matched_label = state.next_label("range.matched")
    state.instructions.append(f"  br i1 {left_matches}, label %{matched_label}, label %{end_label}")
    state.instructions.append(f"{matched_label}:")
    lower_runtime_action_or_default(action, state)
    right_after_start = lower_record_pattern(pattern.right, state)
    start_keep_active = state.next_temp("range.start.keep")
    start_keep_active_num = state.next_temp("range.start.keepnum")
    state.instructions.extend(
        [
            f"  {start_keep_active} = xor i1 {right_after_start}, true",
            f"  {start_keep_active_num} = uitofp i1 {start_keep_active} to double",
            f"  store double {start_keep_active_num}, ptr {slot_name}",
            f"  br label %{end_label}",
            f"{end_label}:",
        ]
    )


def lower_action(action: Action, state: LoweringState, record: RecordContext | None) -> None:
    """Lower one action block with an optional active input record."""
    previous_record = state.current_record
    previous_exit_label = state.action_exit_label
    state.current_record = record
    if state.runtime_param is not None:
        state.action_exit_label = state.next_label("action.exit")
    try:
        terminated = False
        for statement in action.statements:
            lower_statement(statement, state)
            if state.runtime_param is not None and isinstance(statement, NextStmt):
                terminated = True
                break
        if state.runtime_param is not None and state.action_exit_label is not None:
            if not terminated:
                state.instructions.append(f"  br label %{state.action_exit_label}")
            state.instructions.append(f"{state.action_exit_label}:")
    finally:
        state.current_record = previous_record
        state.action_exit_label = previous_exit_label


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
    if statement.op is not statement.op.PLAIN:
        raise RuntimeError("compound assignments are not supported by the LLVM-backed backend")
    if statement.name is None:
        raise RuntimeError("non-scalar assignments are not supported by the LLVM-backed backend")
    if statement.index is not None or statement.extra_indexes:
        raise RuntimeError("array assignments are not supported by the LLVM-backed backend")
    slot_name = variable_address(statement.name, state)
    numeric_value = lower_numeric_expression(statement.value, state)
    state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")


def lower_runtime_assignment_statement(statement: AssignStmt, state: LoweringState) -> None:
    """Lower one runtime-backed assignment in the reusable backend subset."""
    if statement.op is not statement.op.PLAIN:
        raise RuntimeError("compound assignments are not supported by the runtime-backed backend")
    assert state.runtime_param is not None

    field_index = statement.field_index
    if field_index is not None:
        index_value = lower_runtime_field_index(field_index, state)
        numeric_value = lower_runtime_numeric_expression(statement.value, state)
        state.instructions.append(
            f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {index_value}, double {numeric_value})"
        )
        return

    if statement.name is None:
        raise RuntimeError("non-scalar assignments are not supported by the runtime-backed backend")
    if statement.extra_indexes:
        raise RuntimeError("multi-subscript assignments are not supported by the runtime-backed backend")
    if statement.index is not None:
        array_name_ptr = lower_runtime_constant_string(statement.name, state)
        key_ptr = lower_runtime_array_key(statement.index, state)
        numeric_value = lower_runtime_numeric_expression(statement.value, state)
        state.instructions.append(
            (
                f"  call void @qk_array_set_number("
                f"ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {numeric_value})"
            )
        )
        return
    slot_name = variable_address(statement.name, state)
    numeric_value = lower_runtime_numeric_expression(statement.value, state)
    state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")


def lower_runtime_delete_statement(statement: DeleteStmt, state: LoweringState) -> None:
    """Lower one `delete` statement in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    array_name = statement.array_name
    if array_name is None:
        raise RuntimeError("non-array delete targets are not supported by the runtime-backed backend")
    if statement.extra_indexes:
        raise RuntimeError("multi-subscript delete targets are not supported by the runtime-backed backend")

    array_name_ptr = lower_runtime_constant_string(array_name, state)
    if statement.index is None:
        state.instructions.append(f"  call void @qk_array_clear(ptr {state.runtime_param}, ptr {array_name_ptr})")
        return
    key_ptr = lower_runtime_array_key(statement.index, state)
    state.instructions.append(
        f"  call void @qk_array_delete(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
    )


def lower_runtime_for_statement(statement: ForStmt, state: LoweringState) -> None:
    """Lower one classic `for` loop in the runtime-backed backend subset."""
    for expression in statement.init:
        lower_runtime_side_effect_expression(expression, state)

    cond_label = state.next_label("for.cond")
    body_label = state.next_label("for.body")
    update_label = state.next_label("for.update")
    end_label = state.next_label("for.end")
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{cond_label}:")
    if statement.condition is None:
        state.instructions.append(f"  br label %{body_label}")
    else:
        condition = lower_condition_expression(statement.condition, state)
        state.instructions.append(f"  br i1 {condition}, label %{body_label}, label %{end_label}")
    state.instructions.append(f"{body_label}:")
    lower_statement(statement.body, state)
    state.instructions.append(f"  br label %{update_label}")
    state.instructions.append(f"{update_label}:")
    for expression in statement.update:
        lower_runtime_side_effect_expression(expression, state)
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{end_label}:")


def lower_runtime_for_in_statement(statement: ForInStmt, state: LoweringState) -> None:
    """Lower one `for (k in a)` loop in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    array_name = statement.array_name
    if array_name is None:
        raise RuntimeError("for-in iteration requires a named array in the runtime-backed backend")
    array_name_ptr = lower_runtime_constant_string(array_name, state)
    key_slot = state.next_temp("forin.slot")
    first_key = state.next_temp("forin.first")
    cond_label = state.next_label("forin.cond")
    body_label = state.next_label("forin.body")
    step_label = state.next_label("forin.step")
    end_label = state.next_label("forin.end")
    current_key = state.next_temp("forin.key")
    has_key = state.next_temp("forin.has")
    next_key = state.next_temp("forin.next")

    state.allocas.append(f"  {key_slot} = alloca ptr")
    state.instructions.extend(
        [
            f"  {first_key} = call ptr @qk_array_first_key(ptr {state.runtime_param}, ptr {array_name_ptr})",
            f"  store ptr {first_key}, ptr {key_slot}",
            f"  br label %{cond_label}",
            f"{cond_label}:",
            f"  {current_key} = load ptr, ptr {key_slot}",
            f"  {has_key} = icmp ne ptr {current_key}, null",
            f"  br i1 {has_key}, label %{body_label}, label %{end_label}",
            f"{body_label}:",
        ]
    )
    previous_binding = state.loop_string_bindings.get(statement.name)
    state.loop_string_bindings[statement.name] = current_key
    try:
        lower_statement(statement.body, state)
    finally:
        if previous_binding is None:
            state.loop_string_bindings.pop(statement.name, None)
        else:
            state.loop_string_bindings[statement.name] = previous_binding
    state.instructions.extend(
        [
            f"  br label %{step_label}",
            f"{step_label}:",
            (
                f"  {next_key} = call ptr @qk_array_next_key("
                f"ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {current_key})"
            ),
            f"  store ptr {next_key}, ptr {key_slot}",
            f"  br label %{cond_label}",
            f"{end_label}:",
        ]
    )


def lower_initial_variables(initial_variables: InitialVariables, state: LoweringState) -> None:
    """Seed ordered numeric preassignments before user statements execute."""
    for name, value in initial_variables:
        slot_name = variable_address(name, state)
        state.instructions.append(f"  store double {format_double_literal(value)}, ptr {slot_name}")


def variable_address(name: str, state: LoweringState) -> str:
    """Return the address used for a scalar variable in the active lowering mode."""
    existing = state.variable_slots.get(name)
    if existing is not None:
        return existing

    if state.state_param is not None:
        variable_index = state.variable_indexes.get(name)
        if variable_index is None:
            raise RuntimeError(f"undefined variable slot in reusable backend: {name}")
        slot_name = state.next_temp(f"varptr.{name}")
        state.instructions.append(
            f"  {slot_name} = getelementptr inbounds %quawk.state, ptr {state.state_param}, i32 0, i32 {variable_index}"
        )
        return slot_name

    slot_name = state.next_temp(f"var.{name}")
    state.allocas.append(f"  {slot_name} = alloca double")
    state.instructions.append(f"  store double 0.000000000000000e+00, ptr {slot_name}")
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
        global_name, byte_length = declare_string(
            state,
            resolve_field_value(static_field_index(expression), state.current_record),
        )
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
    if isinstance(expression, NameExpr) and expression.name in state.loop_string_bindings:
        string_value = lower_runtime_string_expression(expression, state)
        state.instructions.append(f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {string_value})")
        return
    if isinstance(expression, StringLiteralExpr):
        string_value = lower_runtime_string_expression(expression, state)
        state.instructions.append(f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {string_value})")
        return
    if runtime_expression_has_string_result(expression):
        string_value = lower_runtime_string_expression(expression, state)
        state.instructions.append(f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {string_value})")
        return

    numeric_value = lower_runtime_numeric_expression(expression, state)
    state.instructions.append(f"  call void @qk_print_number(ptr {state.runtime_param}, double {numeric_value})")


def lower_runtime_printf_statement(statement: PrintfStmt, state: LoweringState) -> None:
    """Lower one runtime-backed `printf` statement."""
    arguments = statement.arguments
    if not arguments:
        raise RuntimeError("printf requires at least a format string")
    format_expression = arguments[0]
    if not isinstance(format_expression, StringLiteralExpr):
        raise RuntimeError("the runtime-backed backend currently requires a literal printf format string")

    format_name, format_length = declare_string(state, format_expression.value)
    format_ptr = state.next_temp("fmtptr")
    specifiers = [
        match.group(1) for match in PRINTF_SPEC_PATTERN.finditer(format_expression.value) if match.group(1) != "%"
    ]
    if len(specifiers) != len(arguments) - 1:
        raise RuntimeError("printf argument count does not match the format string in the runtime-backed backend")

    operands: list[str] = []
    for specifier, argument in zip(specifiers, arguments[1:], strict=True):
        if specifier == "s":
            operands.append(f"ptr {lower_runtime_string_expression(argument, state)}")
            continue
        if specifier in {"d", "i", "o", "u", "x", "X"}:
            integer_value = state.next_temp("printf.int")
            numeric_value = lower_runtime_numeric_expression(argument, state)
            state.instructions.append(f"  {integer_value} = fptosi double {numeric_value} to i32")
            operands.append(f"i32 {integer_value}")
            continue
        operands.append(f"double {lower_runtime_numeric_expression(argument, state)}")

    call_args = ", ".join([f"ptr {format_ptr}", *operands])
    state.instructions.extend(
        [
            emit_gep(format_ptr, format_length, format_name),
            f"  call i32 (ptr, ...) @printf({call_args})",
        ]
    )


def lower_runtime_side_effect_expression(expression: Expr, state: LoweringState) -> None:
    """Lower one expression statement for the runtime-backed backend subset."""
    if runtime_expression_has_string_result(expression):
        _ = lower_runtime_string_expression(expression, state)
        return
    try:
        _ = lower_runtime_numeric_expression(expression, state)
        return
    except RuntimeError as exc:
        raise RuntimeError("expression statements are not supported by the runtime-backed backend") from exc


def lower_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a numeric expression and return the LLVM operand for its value."""
    if isinstance(expression, NumericLiteralExpr):
        return format_double_literal(expression.value)

    if isinstance(expression, ArrayIndexExpr):
        raise RuntimeError("array reads are not supported by the LLVM-backed backend")

    if isinstance(expression, NameExpr):
        slot_name = variable_address(expression.name, state)
        temp = state.next_temp("load")
        state.instructions.append(f"  {temp} = load double, ptr {slot_name}")
        return temp

    if isinstance(expression, CallExpr):
        if expression.function not in state.function_defs:
            raise RuntimeError(f"unsupported function call in numeric expression: {expression.function}")
        if state.state_param is None:
            raise RuntimeError("user-defined function calls require backend state support")
        function_def = state.function_defs[expression.function]
        if len(expression.args) != len(function_def.params):
            raise RuntimeError(
                f"function {expression.function} expects {len(function_def.params)} arguments, got {len(expression.args)}"
            )
        arguments = [f"ptr {state.state_param}"]
        for argument in expression.args:
            arguments.append(f"double {lower_numeric_expression(argument, state)}")
        temp = state.next_temp("call")
        state.instructions.append(f"  {temp} = call double @qk_fn_{expression.function}({', '.join(arguments)})")
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


def lower_runtime_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower one numeric expression in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    match expression:
        case NumericLiteralExpr(value=value):
            return format_double_literal(value)
        case NameExpr(name="NR"):
            temp = state.next_temp("nr")
            state.instructions.append(f"  {temp} = call double @qk_get_nr(ptr {state.runtime_param})")
            return temp
        case NameExpr(name="FNR"):
            temp = state.next_temp("fnr")
            state.instructions.append(f"  {temp} = call double @qk_get_fnr(ptr {state.runtime_param})")
            return temp
        case NameExpr(name="NF"):
            temp = state.next_temp("nf")
            state.instructions.append(f"  {temp} = call double @qk_get_nf(ptr {state.runtime_param})")
            return temp
        case NameExpr(name=name):
            slot_name = variable_address(name, state)
            temp = state.next_temp("load")
            state.instructions.append(f"  {temp} = load double, ptr {slot_name}")
            return temp
        case AssignExpr():
            return lower_runtime_assignment_expression(expression, state)
        case UnaryExpr(op=UnaryOp.UPLUS, operand=operand):
            return lower_runtime_numeric_expression(operand, state)
        case UnaryExpr(op=UnaryOp.UMINUS, operand=operand):
            operand_value = lower_runtime_numeric_expression(operand, state)
            temp = state.next_temp("neg")
            state.instructions.append(f"  {temp} = fsub double 0.000000000000000e+00, {operand_value}")
            return temp
        case UnaryExpr(op=UnaryOp.NOT, operand=operand):
            condition_value = lower_condition_expression(operand, state)
            temp = state.next_temp("notnum")
            state.instructions.append(
                f"  {temp} = select i1 {condition_value}, double 0.000000000000000e+00, double 1.000000000000000e+00"
            )
            return temp
        case UnaryExpr(op=UnaryOp.PRE_INC, operand=NameExpr(name=name)):
            return lower_runtime_increment_expression(name, 1.0, return_old=False, state=state)
        case UnaryExpr(op=UnaryOp.PRE_DEC, operand=NameExpr(name=name)):
            return lower_runtime_increment_expression(name, -1.0, return_old=False, state=state)
        case PostfixExpr(op=PostfixOp.POST_INC, operand=NameExpr(name=name)):
            return lower_runtime_increment_expression(name, 1.0, return_old=True, state=state)
        case PostfixExpr(op=PostfixOp.POST_DEC, operand=NameExpr(name=name)):
            return lower_runtime_increment_expression(name, -1.0, return_old=True, state=state)
        case CallExpr(function="split"):
            return lower_runtime_split_builtin(expression, state)
        case CallExpr(function="length"):
            return lower_runtime_length_builtin(expression, state)
        case BinaryExpr(op=BinaryOp.ADD, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            temp = state.next_temp("add")
            state.instructions.append(f"  {temp} = fadd double {left_operand}, {right_operand}")
            return temp
        case BinaryExpr(op=BinaryOp.LESS | BinaryOp.EQUAL | BinaryOp.LOGICAL_AND):
            condition_value = lower_condition_expression(expression, state)
            temp = state.next_temp("boolnum")
            state.instructions.append(f"  {temp} = uitofp i1 {condition_value} to double")
            return temp
        case _:
            raise RuntimeError("unsupported numeric expression in runtime-backed backend")


def lower_runtime_assignment_expression(expression: AssignExpr, state: LoweringState) -> str:
    """Lower one numeric assignment expression in the runtime-backed backend subset."""
    if expression.op is not AssignOp.PLAIN:
        raise RuntimeError("compound assignment expressions are not supported by the runtime-backed backend")

    target = expression.target
    numeric_value = lower_runtime_numeric_expression(expression.value, state)
    match target:
        case FieldLValue(index=index):
            index_value = lower_runtime_field_index(index, state)
            assert state.runtime_param is not None
            state.instructions.append(
                f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {index_value}, double {numeric_value})"
            )
        case ArrayLValue(name=name, subscripts=(subscript,)):
            assert state.runtime_param is not None
            array_name_ptr = lower_runtime_constant_string(name, state)
            key_ptr = lower_runtime_array_key(subscript, state)
            state.instructions.append(
                f"  call void @qk_array_set_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {numeric_value})"
            )
        case NameLValue(name=name):
            slot_name = variable_address(name, state)
            state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
        case _:
            raise RuntimeError("unsupported assignment expression in the runtime-backed backend")
    return numeric_value


def lower_runtime_increment_expression(name: str, delta: float, *, return_old: bool, state: LoweringState) -> str:
    """Lower one scalar pre/post increment or decrement expression."""
    slot_name = variable_address(name, state)
    old_value = state.next_temp("inc.old")
    new_value = state.next_temp("inc.new")
    state.instructions.append(f"  {old_value} = load double, ptr {slot_name}")
    opcode = "fadd" if delta >= 0 else "fsub"
    amount = format_double_literal(abs(delta))
    state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
    state.instructions.append(f"  store double {new_value}, ptr {slot_name}")
    return old_value if return_old else new_value


def lower_runtime_string_expression(expression: Expr, state: LoweringState) -> str:
    """Lower one string-valued expression in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    match expression:
        case StringLiteralExpr(value=value):
            global_name, byte_length = declare_string(state, value)
            string_ptr = state.next_temp("strptr")
            state.instructions.append(emit_gep(string_ptr, byte_length, global_name))
            return string_ptr
        case NameExpr(name=name) if name in state.loop_string_bindings:
            return state.loop_string_bindings[name]
        case NameExpr(name="FILENAME"):
            temp = state.next_temp("filename")
            state.instructions.append(f"  {temp} = call ptr @qk_get_filename(ptr {state.runtime_param})")
            return temp
        case FieldExpr(index=index):
            field_index = lower_runtime_field_index(index, state)
            temp = state.next_temp("field")
            state.instructions.append(
                f"  {temp} = call ptr @qk_get_field(ptr {state.runtime_param}, i64 {field_index})"
            )
            return temp
        case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
            if extra_indexes:
                raise RuntimeError("multi-subscript array reads are not supported by the runtime-backed backend")
            array_name_ptr = lower_runtime_constant_string(array_name, state)
            key_ptr = lower_runtime_array_key(index, state)
            temp = state.next_temp("array.get")
            state.instructions.append(
                f"  {temp} = call ptr @qk_array_get(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
            )
            return temp
        case CallExpr(function="substr"):
            return lower_runtime_substr_builtin(expression, state)
        case CallExpr(function="length"):
            raise RuntimeError("length lowers as a numeric expression in the runtime-backed backend")
        case _:
            raise RuntimeError("unsupported string expression in runtime-backed backend")


def lower_runtime_length_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `length` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) > 1:
        raise RuntimeError("builtin length expects zero or one argument")

    if not expression.args:
        field_ptr = state.next_temp("length.record")
        size_value = state.next_temp("length.size")
        numeric_value = state.next_temp("length.num")
        state.instructions.extend(
            [
                f"  {field_ptr} = call ptr @qk_get_field(ptr {state.runtime_param}, i64 0)",
                f"  {size_value} = call i64 @strlen(ptr {field_ptr})",
                f"  {numeric_value} = uitofp i64 {size_value} to double",
            ]
        )
        return numeric_value

    argument = expression.args[0]
    if isinstance(argument, NameExpr) and argument.name in state.array_names:
        array_name_ptr = lower_runtime_constant_string(argument.name, state)
        numeric_value = state.next_temp("length.array")
        state.instructions.append(
            f"  {numeric_value} = call double @qk_array_length(ptr {state.runtime_param}, ptr {array_name_ptr})"
        )
        return numeric_value

    string_value = lower_runtime_string_expression(argument, state)
    size_value = state.next_temp("length.size")
    numeric_value = state.next_temp("length.num")
    state.instructions.extend(
        [
            f"  {size_value} = call i64 @strlen(ptr {string_value})",
            f"  {numeric_value} = uitofp i64 {size_value} to double",
        ]
    )
    return numeric_value


def lower_runtime_split_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `split` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) not in {2, 3}:
        raise RuntimeError("builtin split expects two or three arguments")
    target = expression.args[1]
    if not isinstance(target, NameExpr):
        raise RuntimeError("builtin split requires a named array target in the runtime-backed backend")

    text_ptr = lower_runtime_string_expression(expression.args[0], state)
    array_name_ptr = lower_runtime_constant_string(target.name, state)
    if len(expression.args) == 3:
        separator_ptr = lower_runtime_string_expression(expression.args[2], state)
    else:
        separator_ptr = "null"
    temp = state.next_temp("split")
    state.instructions.append(
        (
            f"  {temp} = call double @qk_split_into_array("
            f"ptr {state.runtime_param}, ptr {text_ptr}, ptr {array_name_ptr}, ptr {separator_ptr})"
        )
    )
    return temp


def lower_runtime_substr_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `substr` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) not in {2, 3}:
        raise RuntimeError("builtin substr expects two or three arguments")

    text_ptr = lower_runtime_string_expression(expression.args[0], state)
    start_numeric = lower_runtime_numeric_expression(expression.args[1], state)
    start_value = state.next_temp("substr.start")
    state.instructions.append(f"  {start_value} = fptosi double {start_numeric} to i64")
    if len(expression.args) == 2:
        result = state.next_temp("substr")
        state.instructions.append(
            f"  {result} = call ptr @qk_substr2(ptr {state.runtime_param}, ptr {text_ptr}, i64 {start_value})"
        )
        return result

    length_numeric = lower_runtime_numeric_expression(expression.args[2], state)
    length_value = state.next_temp("substr.length")
    result = state.next_temp("substr")
    state.instructions.extend(
        [
            f"  {length_value} = fptosi double {length_numeric} to i64",
            (
                f"  {result} = call ptr @qk_substr3("
                f"ptr {state.runtime_param}, ptr {text_ptr}, i64 {start_value}, i64 {length_value})"
            ),
        ]
    )
    return result


def lower_runtime_constant_string(value: str, state: LoweringState) -> str:
    """Lower one compile-time string constant to a runtime pointer."""
    global_name, byte_length = declare_string(state, value)
    string_ptr = state.next_temp("strptr")
    state.instructions.append(emit_gep(string_ptr, byte_length, global_name))
    return string_ptr


def lower_runtime_array_key(expression: Expr, state: LoweringState) -> str:
    """Lower one array key expression to a string pointer."""
    match expression:
        case NameExpr(name=name) if name in state.loop_string_bindings:
            return state.loop_string_bindings[name]
        case NumericLiteralExpr(value=value):
            return lower_runtime_constant_string(format_numeric_value(value), state)
        case StringLiteralExpr(value=value):
            return lower_runtime_constant_string(value, state)
        case _:
            raise RuntimeError("unsupported array index in runtime-backed backend")


def lower_runtime_field_index(index: int | Expr, state: LoweringState) -> str:
    """Lower one field index to an `i64` operand."""
    if isinstance(index, int):
        return str(index)
    numeric_value = lower_runtime_numeric_expression(index, state)
    integer_value = state.next_temp("field.index")
    state.instructions.append(f"  {integer_value} = fptosi double {numeric_value} to i64")
    return integer_value


def runtime_expression_has_string_result(expression: Expr) -> bool:
    """Report whether one runtime-backed expression lowers as a string result."""
    match expression:
        case StringLiteralExpr() | FieldExpr() | ArrayIndexExpr():
            return True
        case NameExpr(name="FILENAME"):
            return True
        case CallExpr(function="substr"):
            return True
        case _:
            return False


def lower_condition_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a supported condition expression to an LLVM `i1` value."""
    numeric_lowerer = lower_runtime_numeric_expression if state.runtime_param is not None else lower_numeric_expression
    if isinstance(expression, BinaryExpr):
        if expression.op is BinaryOp.LESS:
            left_operand = numeric_lowerer(expression.left, state)
            right_operand = numeric_lowerer(expression.right, state)
            temp = state.next_temp("cmp")
            state.instructions.append(f"  {temp} = fcmp olt double {left_operand}, {right_operand}")
            return temp
        if expression.op is BinaryOp.EQUAL:
            left_operand = numeric_lowerer(expression.left, state)
            right_operand = numeric_lowerer(expression.right, state)
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

    numeric_value = numeric_lowerer(expression, state)
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


def execute_with_inputs(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> int:
    """Execute the current program, routing record-driven programs through the host loop."""
    if requires_host_runtime_execution(program) or requires_host_runtime_value_execution(program):
        return execute_host_runtime(program, input_files, field_separator, initial_variables)
    llvm_ir = build_public_execution_llvm_ir(program, input_files, field_separator, initial_variables)
    return execute_llvm_ir(llvm_ir)


def link_reusable_execution_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Link the reusable program module, runtime support, and execution driver into one IR module."""
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        runtime_bitcode = runtime_support.compile_runtime_bitcode(temp_dir)
        program_bitcode = assemble_llvm_ir(program_llvm_ir, temp_dir / "program.bc")
        driver_ir = build_execution_driver_llvm_ir(
            program,
            program_llvm_ir,
            input_files,
            field_separator,
            initial_variables,
        )
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
    initial_variables: InitialVariables | None = None,
) -> str:
    """Build the reusable execution driver that invokes runtime and program phases."""
    normalized_program = normalize_program_for_lowering(program)
    has_record_phase = bool(normalized_program.record_items)
    state_type = extract_state_type_declaration(program_llvm_ir)
    variable_indexes = normalized_program.variable_indexes

    globals_block = render_driver_globals(input_files, field_separator)
    state_setup = render_driver_state_setup(variable_indexes, initial_variables or [])
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


def render_driver_state_setup(
    variable_indexes: dict[str, int],
    initial_variables: InitialVariables,
) -> list[str]:
    """Render driver setup for the reusable program state pointer."""
    if not variable_indexes:
        return ["  %state = getelementptr i8, ptr null, i64 0"]

    setup = [
        "  %state.storage = alloca %quawk.state",
        "  %state = getelementptr i8, ptr %state.storage, i64 0",
    ]
    for name, index in sorted(variable_indexes.items(), key=lambda item: item[1]):
        slot_name = f"%state.init.{name}"
        setup.extend(
            [
                f"  {slot_name} = getelementptr inbounds %quawk.state, ptr %state, i32 0, i32 {index}",
                f"  store double 0.000000000000000e+00, ptr {slot_name}",
            ]
        )

    for name, value in initial_variables:
        variable_index = variable_indexes.get(name)
        if variable_index is None:
            continue
        slot_name = f"%state.preassign.{name}"
        setup.extend(
            [
                (
                    f"  {slot_name} = getelementptr inbounds %quawk.state, ptr %state, "
                    f"i32 0, i32 {variable_index}"
                ),
                f"  store double {format_double_literal(value)}, ptr {slot_name}",
            ]
        )
    return setup


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
        if isinstance(item.pattern, ExprPattern | RangePattern):
            return True
    return False


def has_end_pattern(program: Program) -> bool:
    """Report whether `program` contains any END action."""
    return any(isinstance(item, PatternAction) and isinstance(item.pattern, EndPattern) for item in program.items)


def execute_host_runtime(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> int:
    """Execute the supported subset with explicit BEGIN/record/END sequencing."""
    begin_actions, record_items, end_actions = partition_host_runtime_items(program)
    state = RuntimeState(
        variables={name: make_numeric_value(value) for name, value in (initial_variables or [])},
        functions=collect_function_definitions(program),
        field_separator=field_separator,
    )
    initialize_builtin_variables(state)
    exit_status = 0
    terminated = False

    try:
        for action in begin_actions:
            execute_action(action, state, record=None, locals_scope=None)
    except ExitSignal as signal:
        exit_status = signal.status
        terminated = True

    if not terminated and record_items:
        for filename, input_records in iter_input_files(input_files):
            skip_remaining_file = False
            state.current_filename = filename
            state.variables["FNR"] = make_numeric_value(0.0)
            for line in input_records:
                record_text = line.rstrip("\n")
                record = RecordContext(
                    field0=record_text,
                    fields=split_fields(record_text, field_separator),
                )
                update_record_builtin_variables(state, record)
                try:
                    for item in record_items:
                        if record_item_matches(item, state, record):
                            execute_record_item(item, state, record)
                except NextSignal:
                    continue
                except NextFileSignal:
                    skip_remaining_file = True
                    break
                except ExitSignal as signal:
                    exit_status = signal.status
                    terminated = True
                    break
            if terminated:
                break
            if skip_remaining_file:
                continue

    for action in end_actions:
        try:
            execute_action(action, state, record=None, locals_scope=None)
        except ExitSignal as signal:
            return signal.status
    return exit_status


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
            fields=split_fields(record_text, field_separator),
        ))
    return records


def partition_host_runtime_items(
    program: Program,
) -> tuple[
    list[Action],
    list[HostRuntimeRecordItem],
    list[Action],
]:
    """Split items into ordered BEGIN actions, record items, and END actions for the host runtime."""
    begin_actions: list[Action] = []
    record_items: list[HostRuntimeRecordItem] = []
    end_actions: list[Action] = []

    for item in program.items:
        if isinstance(item, FunctionDef):
            continue
        if not isinstance(item, PatternAction):
            raise RuntimeError("the current runtime only supports pattern-action items")

        if item.pattern is None:
            if item.action is None:
                raise RuntimeError("bare record rules require an action in the current runtime")
            record_items.append(HostRuntimeRecordItem(pattern=None, action=item.action))
            continue
        if isinstance(item.pattern, BeginPattern):
            if item.action is None:
                raise RuntimeError("BEGIN rules require an action in the current runtime")
            begin_actions.append(item.action)
            continue
        if isinstance(item.pattern, EndPattern):
            if item.action is None:
                raise RuntimeError("END rules require an action in the current runtime")
            end_actions.append(item.action)
            continue
        if isinstance(item.pattern, ExprPattern | RangePattern):
            record_items.append(HostRuntimeRecordItem(pattern=item.pattern, action=item.action))
            continue
        raise RuntimeError("unsupported pattern in current runtime")

    return begin_actions, record_items, end_actions


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


def iter_input_files(input_files: list[str]) -> list[tuple[str, list[str]]]:
    """Collect logical input records grouped by input source."""
    if not input_files:
        return [("-", sys.stdin.readlines())]

    grouped_records: list[tuple[str, list[str]]] = []
    for path in input_files:
        if path == "-":
            grouped_records.append(("-", sys.stdin.readlines()))
            continue
        with Path(path).open("r", encoding="utf-8") as handle:
            grouped_records.append((path, handle.readlines()))
    return grouped_records


def iter_input_records(input_files: list[str]) -> list[str]:
    """Collect logical input records from files or standard input."""
    records: list[str] = []
    for _, grouped_records in iter_input_files(input_files):
        records.extend(grouped_records)
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


def record_item_matches(
    item: HostRuntimeRecordItem,
    state: RuntimeState,
    record: RecordContext,
) -> bool:
    """Report whether one host-runtime record item should fire for the current record."""
    pattern = item.pattern
    if pattern is None:
        return True
    if isinstance(pattern, RangePattern):
        if item.range_active:
            if pattern_matches_record(pattern.right, state, record):
                item.range_active = False
            return True
        if pattern_matches_record(pattern.left, state, record):
            item.range_active = not pattern_matches_record(pattern.right, state, record)
            return True
        return False
    return pattern_matches_record(pattern, state, record)


def pattern_matches_record(
    pattern: ExprPattern | BeginPattern | EndPattern | RangePattern,
    state: RuntimeState,
    record: RecordContext,
) -> bool:
    """Evaluate one record-phase pattern against the current record."""
    if isinstance(pattern, ExprPattern):
        if isinstance(pattern.test, RegexLiteralExpr):
            return regex_matches_record(pattern.test, record)
        return evaluate_condition(pattern.test, state, record, locals_scope=None)
    raise RuntimeError("BEGIN, END, and nested range patterns are not supported in record-phase matching")


def execute_record_item(
    item: HostRuntimeRecordItem,
    state: RuntimeState,
    record: RecordContext,
) -> None:
    """Execute one record item, applying AWK's default print when no action is present."""
    if item.action is None:
        print_value(make_string_value(record.field0))
        return
    execute_action(item.action, state, record=record, locals_scope=None)


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
    locals_scope: LocalScope | None,
) -> None:
    """Execute one action block in the host runtime."""
    for statement in action.statements:
        execute_statement(statement, state, record, locals_scope)


def execute_statement(
    statement: Stmt,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> None:
    """Execute one statement in the currently supported host-runtime subset."""
    match statement:
        case AssignStmt(target=target, op=op, value=value, span=span):
            _ = evaluate_assignment_expression(
                AssignExpr(target=target, op=op, value=value, span=span),
                state,
                record,
                locals_scope,
            )
        case BlockStmt(statements=statements):
            for nested in statements:
                execute_statement(nested, state, record, locals_scope)
        case BreakStmt():
            raise BreakSignal()
        case ContinueStmt():
            raise ContinueSignal()
        case DeleteStmt():
            array_name = statement.array_name
            index = statement.index
            if array_name is None:
                raise RuntimeError("non-array delete targets are not supported by the current runtime")
            if statement.extra_indexes:
                raise RuntimeError("multi-subscript delete targets are not supported by the current runtime")
            if index is None:
                state.arrays.pop(array_name, None)
                return
            key = evaluate_array_index(index, state, record, locals_scope)
            target_array = state.arrays.get(array_name)
            if target_array is not None:
                target_array.pop(key, None)
        case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
            if evaluate_condition(condition, state, record, locals_scope):
                execute_statement(then_branch, state, record, locals_scope)
            elif else_branch is not None:
                execute_statement(else_branch, state, record, locals_scope)
        case WhileStmt(condition=condition, body=body):
            while evaluate_condition(condition, state, record, locals_scope):
                try:
                    execute_statement(body, state, record, locals_scope)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
        case DoWhileStmt(body=body, condition=condition):
            while True:
                try:
                    execute_statement(body, state, record, locals_scope)
                except ContinueSignal:
                    pass
                except BreakSignal:
                    break
                if not evaluate_condition(condition, state, record, locals_scope):
                    break
        case ForStmt(init=init, condition=condition, update=update, body=body):
            for expression in init:
                evaluate_value_expression(expression, state, record, locals_scope)
            while condition is None or evaluate_condition(condition, state, record, locals_scope):
                should_continue = False
                try:
                    execute_statement(body, state, record, locals_scope)
                except ContinueSignal:
                    should_continue = True
                except BreakSignal:
                    break
                for expression in update:
                    evaluate_value_expression(expression, state, record, locals_scope)
                if should_continue:
                    continue
        case ForInStmt(name=name, iterable=iterable, body=body):
            if not isinstance(iterable, NameExpr):
                raise RuntimeError("for-in iteration requires an array name in the current runtime")
            array_name = iterable.name
            keys = tuple(state.arrays.get(array_name, {}).keys())
            for key in keys:
                assign_scalar_value(name, make_string_value(key), state, locals_scope)
                try:
                    execute_statement(body, state, record, locals_scope)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
        case ReturnStmt(value=value):
            if locals_scope is None:
                raise RuntimeError("return is only valid inside a function")
            if value is None:
                raise ReturnSignal(UNINITIALIZED_VALUE)
            raise ReturnSignal(evaluate_value_expression(value, state, record, locals_scope))
        case PrintStmt(arguments=arguments):
            if len(arguments) != 1:
                raise RuntimeError("the current runtime only supports print with one argument")
            print_value(evaluate_value_expression(arguments[0], state, record, locals_scope))
        case PrintfStmt(arguments=arguments):
            if not arguments:
                raise RuntimeError("printf requires at least a format string")
            print(render_printf_output(arguments, state, record, locals_scope), end="")
        case ExprStmt(value=value):
            evaluate_value_expression(value, state, record, locals_scope)
        case NextStmt():
            raise NextSignal()
        case NextFileStmt():
            raise NextFileSignal()
        case ExitStmt(value=value):
            status = 0 if value is None else int(evaluate_numeric_expression(value, state, record, locals_scope))
            raise ExitSignal(status)
        case _:
            raise RuntimeError("the current runtime only supports print with one argument")


def evaluate_value_expression(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Evaluate an expression into the host runtime's AWK value model."""
    match expression:
        case NumericLiteralExpr(value=literal_value):
            return make_numeric_value(literal_value)
        case StringLiteralExpr(value=literal_value):
            return make_string_value(literal_value)
        case AssignExpr():
            return evaluate_assignment_expression(expression, state, record, locals_scope)
        case FieldExpr(index=index):
            if record is None:
                raise RuntimeError("field expressions require an active input record")
            field_index = index if isinstance(index, int) else evaluate_field_index(index, state, record, locals_scope)
            return make_string_value(resolve_field_value(field_index, record))
        case ArrayIndexExpr(array_name=array_name, index=index):
            key = evaluate_array_index(index, state, record, locals_scope)
            array = state.arrays.get(array_name)
            if array is None:
                return UNINITIALIZED_VALUE
            return array.get(key, UNINITIALIZED_VALUE)
        case NameExpr(name=name):
            return read_scalar_value(name, state, locals_scope)
        case CallExpr():
            return call_function(expression, state, record, locals_scope)
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            if evaluate_condition(test, state, record, locals_scope):
                return evaluate_value_expression(if_true, state, record, locals_scope)
            return evaluate_value_expression(if_false, state, record, locals_scope)
        case UnaryExpr(op=op, operand=operand):
            match op:
                case UnaryOp.UPLUS:
                    return make_numeric_value(evaluate_numeric_expression(operand, state, record, locals_scope))
                case UnaryOp.UMINUS:
                    return make_numeric_value(-evaluate_numeric_expression(operand, state, record, locals_scope))
                case UnaryOp.NOT:
                    return make_numeric_value(0.0 if evaluate_condition(operand, state, record, locals_scope) else 1.0)
                case UnaryOp.PRE_INC:
                    return evaluate_increment_expression(
                        operand, 1.0, return_old=False, state=state, record=record, locals_scope=locals_scope
                    )
                case UnaryOp.PRE_DEC:
                    return evaluate_increment_expression(
                        operand, -1.0, return_old=False, state=state, record=record, locals_scope=locals_scope
                    )
                case _:
                    raise RuntimeError(f"unsupported unary operator in current runtime: {op.name}")
        case PostfixExpr(op=PostfixOp.POST_INC, operand=operand):
            return evaluate_increment_expression(
                operand, 1.0, return_old=True, state=state, record=record, locals_scope=locals_scope
            )
        case PostfixExpr(op=PostfixOp.POST_DEC, operand=operand):
            return evaluate_increment_expression(
                operand, -1.0, return_old=True, state=state, record=record, locals_scope=locals_scope
            )
        case BinaryExpr(op=op, left=left, right=right):
            match op:
                case BinaryOp.ADD:
                    return make_numeric_value(
                        evaluate_numeric_expression(left, state, record, locals_scope)
                        + evaluate_numeric_expression(right, state, record, locals_scope)
                    )
                case BinaryOp.SUB:
                    return make_numeric_value(
                        evaluate_numeric_expression(left, state, record, locals_scope)
                        - evaluate_numeric_expression(right, state, record, locals_scope)
                    )
                case BinaryOp.MUL:
                    return make_numeric_value(
                        evaluate_numeric_expression(left, state, record, locals_scope)
                        * evaluate_numeric_expression(right, state, record, locals_scope)
                    )
                case BinaryOp.DIV:
                    return make_numeric_value(
                        evaluate_numeric_expression(left, state, record, locals_scope)
                        / evaluate_numeric_expression(right, state, record, locals_scope)
                    )
                case BinaryOp.MOD:
                    return make_numeric_value(
                        evaluate_numeric_expression(left, state, record, locals_scope)
                        % evaluate_numeric_expression(right, state, record, locals_scope)
                    )
                case BinaryOp.POW:
                    return make_numeric_value(
                        evaluate_numeric_expression(left, state, record, locals_scope)
                        ** evaluate_numeric_expression(right, state, record, locals_scope)
                    )
                case BinaryOp.LESS | BinaryOp.LESS_EQUAL | BinaryOp.GREATER | BinaryOp.GREATER_EQUAL:
                    return make_numeric_value(
                        1.0 if compare_values(op, left, right, state, record, locals_scope) else 0.0
                    )
                case BinaryOp.EQUAL | BinaryOp.NOT_EQUAL:
                    return make_numeric_value(
                        1.0 if compare_values(op, left, right, state, record, locals_scope) else 0.0
                    )
                case BinaryOp.LOGICAL_AND:
                    if not evaluate_condition(left, state, record, locals_scope):
                        return make_numeric_value(0.0)
                    return make_numeric_value(1.0 if evaluate_condition(right, state, record, locals_scope) else 0.0)
                case BinaryOp.LOGICAL_OR:
                    if evaluate_condition(left, state, record, locals_scope):
                        return make_numeric_value(1.0)
                    return make_numeric_value(1.0 if evaluate_condition(right, state, record, locals_scope) else 0.0)
                case BinaryOp.CONCAT:
                    return make_string_value(
                        coerce_scalar_to_string(evaluate_value_expression(left, state, record, locals_scope))
                        + coerce_scalar_to_string(evaluate_value_expression(right, state, record, locals_scope))
                    )
                case BinaryOp.MATCH:
                    return make_numeric_value(
                        1.0 if evaluate_match_expression(left, right, state, record, locals_scope) else 0.0
                    )
                case BinaryOp.NOT_MATCH:
                    return make_numeric_value(
                        0.0 if evaluate_match_expression(left, right, state, record, locals_scope) else 1.0
                    )
                case BinaryOp.IN:
                    return make_numeric_value(
                        1.0 if evaluate_in_expression(left, right, state, record, locals_scope) else 0.0
                    )
                case _:
                    raise RuntimeError(f"unsupported binary operator in current runtime: {op.name}")
        case RegexLiteralExpr(raw_text=raw_text):
            return make_string_value(raw_text)
        case _:
            raise RuntimeError("unsupported expression in current runtime")


def evaluate_numeric_expression(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> float:
    """Evaluate a numeric expression in the current host-runtime subset."""
    return coerce_scalar_to_number(evaluate_value_expression(expression, state, record, locals_scope))


def evaluate_condition(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> bool:
    """Evaluate a condition expression using the supported truthiness rules."""
    return coerce_scalar_to_truthy(evaluate_value_expression(expression, state, record, locals_scope))


def call_function(
    expression: CallExpr,
    state: RuntimeState,
    record: RecordContext | None,
    caller_locals: LocalScope | None,
) -> AwkValue:
    """Execute one user-defined function call in the current host runtime."""
    function_def = state.functions.get(expression.function)
    if function_def is None and is_builtin_function_name(expression.function):
        return call_builtin_function(expression, state, record, caller_locals)
    if function_def is None:
        raise RuntimeError(f"undefined function in current runtime: {expression.function}")
    if len(expression.args) != len(function_def.params):
        raise RuntimeError(
            f"function {expression.function} expects {len(function_def.params)} arguments, got {len(expression.args)}"
        )

    locals_scope: LocalScope = {
        param: evaluate_value_expression(argument, state, record, caller_locals)
        for param, argument in zip(function_def.params, expression.args, strict=True)
    }
    try:
        for statement in function_def.body.statements:
            execute_statement(statement, state, record, locals_scope)
    except ReturnSignal as signal:
        return signal.value
    return UNINITIALIZED_VALUE


def call_builtin_function(
    expression: CallExpr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Execute one supported builtin function call in the current host runtime."""
    match expression.function:
        case "length":
            return call_length_builtin(expression, state, record, locals_scope)
        case "split":
            return call_split_builtin(expression, state, record, locals_scope)
        case "substr":
            return call_substr_builtin(expression, state, record, locals_scope)
        case _:
            raise RuntimeError(f"unsupported builtin in current runtime: {expression.function}")


def call_length_builtin(
    expression: CallExpr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Execute the current subset's `length` builtin."""
    if len(expression.args) > 1:
        raise RuntimeError("builtin length expects zero or one argument")
    if not expression.args:
        return make_numeric_value(float(len(record.field0)) if record is not None else 0.0)

    argument = expression.args[0]
    if isinstance(argument, NameExpr):
        scalar_value = read_scalar_value(argument.name, state, locals_scope)
        if scalar_value.kind is ValueKind.UNINITIALIZED and argument.name in state.arrays:
            return make_numeric_value(float(len(state.arrays[argument.name])))
    return make_numeric_value(float(len(evaluate_string_expression(argument, state, record, locals_scope))))


def call_split_builtin(
    expression: CallExpr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Execute the current subset's `split` builtin."""
    if len(expression.args) not in {2, 3}:
        raise RuntimeError("builtin split expects two or three arguments")
    source_text = evaluate_string_expression(expression.args[0], state, record, locals_scope)
    target_expr = expression.args[1]
    if not isinstance(target_expr, NameExpr):
        raise RuntimeError("builtin split requires a named array target in the current runtime")

    separator = None
    if len(expression.args) == 3:
        separator = evaluate_string_expression(expression.args[2], state, record, locals_scope)

    parts = split_fields(source_text, separator if separator is not None else state.field_separator)
    target_array: dict[str, AwkValue] = {}
    for index, part in enumerate(parts, start=1):
        target_array[str(index)] = make_string_value(part)
    state.arrays[target_expr.name] = target_array
    return make_numeric_value(float(len(parts)))


def call_substr_builtin(
    expression: CallExpr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Execute the current subset's `substr` builtin."""
    if len(expression.args) not in {2, 3}:
        raise RuntimeError("builtin substr expects two or three arguments")
    source_text = evaluate_string_expression(expression.args[0], state, record, locals_scope)
    start = int(evaluate_numeric_expression(expression.args[1], state, record, locals_scope))
    start_index = max(start - 1, 0)
    if len(expression.args) == 2:
        return make_string_value(source_text[start_index:])

    length = int(evaluate_numeric_expression(expression.args[2], state, record, locals_scope))
    if length <= 0:
        return make_string_value("")
    return make_string_value(source_text[start_index : start_index + length])


def evaluate_array_index(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> str:
    """Evaluate one associative-array index using the current subset's coercions."""
    if isinstance(expression, FieldExpr):
        if record is None:
            raise RuntimeError("field expressions require an active input record")
        field_index = (
            expression.index
            if isinstance(expression.index, int)
            else evaluate_field_index(expression.index, state, record, locals_scope)
        )
        return resolve_field_value(field_index, record)
    return coerce_scalar_to_string(evaluate_value_expression(expression, state, record, locals_scope))


def evaluate_string_expression(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> str:
    """Evaluate an expression into the string view needed by string-oriented builtins."""
    return coerce_scalar_to_string(evaluate_value_expression(expression, state, record, locals_scope))


def read_scalar_value(
    name: str,
    state: RuntimeState,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Read one scalar from the active local scope first, then globals."""
    if locals_scope is not None and name in locals_scope:
        return locals_scope[name]
    if is_builtin_variable_name(name):
        return state.variables.get(name, UNINITIALIZED_VALUE)
    return state.variables.get(name, UNINITIALIZED_VALUE)


def assign_scalar_value(
    name: str,
    value: AwkValue,
    state: RuntimeState,
    locals_scope: LocalScope | None,
) -> None:
    """Assign one scalar value to the local scope when present, otherwise globals."""
    if locals_scope is not None and name in locals_scope:
        locals_scope[name] = value
        return
    state.variables[name] = value


def read_lvalue_value(
    target: NameLValue | ArrayLValue | FieldLValue,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Read one assignable target through the current runtime value model."""
    match target:
        case NameLValue(name=name):
            return read_scalar_value(name, state, locals_scope)
        case ArrayLValue(name=name, subscripts=subscripts):
            if len(subscripts) != 1:
                raise RuntimeError("multi-subscript assignments are not supported by the current runtime")
            key = evaluate_array_index(subscripts[0], state, record, locals_scope)
            array = state.arrays.get(name)
            if array is None:
                return UNINITIALIZED_VALUE
            return array.get(key, UNINITIALIZED_VALUE)
        case FieldLValue(index=index):
            if record is None:
                raise RuntimeError("field assignments require an active input record")
            field_index = evaluate_field_index(index, state, record, locals_scope)
            return make_string_value(resolve_field_value(field_index, record))


def assign_lvalue_value(
    target: NameLValue | ArrayLValue | FieldLValue,
    value: AwkValue,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> None:
    """Assign one runtime value through a validated lvalue target."""
    match target:
        case NameLValue(name=name):
            assign_scalar_value(name, value, state, locals_scope)
        case ArrayLValue(name=name, subscripts=subscripts):
            if len(subscripts) != 1:
                raise RuntimeError("multi-subscript assignments are not supported by the current runtime")
            key = evaluate_array_index(subscripts[0], state, record, locals_scope)
            state.arrays.setdefault(name, {})[key] = value
        case FieldLValue(index=index):
            if record is None:
                raise RuntimeError("field assignments require an active input record")
            assign_field_value(index, value, state, record, locals_scope)


def apply_numeric_assign_op(op: AssignOp, current: float, rhs: float) -> float:
    """Apply one numeric assignment operator."""
    match op:
        case AssignOp.PLAIN:
            return rhs
        case AssignOp.ADD:
            return current + rhs
        case AssignOp.SUB:
            return current - rhs
        case AssignOp.MUL:
            return current * rhs
        case AssignOp.DIV:
            return current / rhs
        case AssignOp.MOD:
            return current % rhs
        case AssignOp.POW:
            return current**rhs


def evaluate_assignment_expression(
    expression: AssignExpr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Evaluate one assignment expression and return the assigned value."""
    value = evaluate_value_expression(expression.value, state, record, locals_scope)
    if expression.op is AssignOp.PLAIN:
        assigned = value
    else:
        current = read_lvalue_value(expression.target, state, record, locals_scope)
        assigned = make_numeric_value(
            apply_numeric_assign_op(
                expression.op,
                coerce_scalar_to_number(current),
                coerce_scalar_to_number(value),
            )
        )
    assign_lvalue_value(expression.target, assigned, state, record, locals_scope)
    return assigned


def evaluate_increment_expression(
    operand: Expr,
    delta: float,
    *,
    return_old: bool,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> AwkValue:
    """Evaluate one pre/post increment or decrement expression."""
    target = expression_to_lvalue(operand)
    if target is None:
        raise RuntimeError("increment and decrement require an assignable expression")
    current = read_lvalue_value(target, state, record, locals_scope)
    current_number = coerce_scalar_to_number(current)
    updated = make_numeric_value(current_number + delta)
    assign_lvalue_value(target, updated, state, record, locals_scope)
    if return_old:
        return make_numeric_value(current_number)
    return updated


def coerce_scalar_to_number(value: AwkValue) -> float:
    """Coerce the current scalar subset into its numeric value."""
    match value.kind:
        case ValueKind.UNINITIALIZED:
            return 0.0
        case ValueKind.NUMBER:
            return value.number
        case ValueKind.STRING:
            return parse_awk_numeric_prefix(value.string)


def coerce_scalar_to_string(value: AwkValue) -> str:
    """Coerce one runtime value into its string view."""
    match value.kind:
        case ValueKind.UNINITIALIZED:
            return ""
        case ValueKind.NUMBER:
            return format_numeric_value(value.number)
        case ValueKind.STRING:
            return value.string


def coerce_scalar_to_truthy(value: AwkValue) -> bool:
    """Apply AWK-style truthiness to one runtime value."""
    match value.kind:
        case ValueKind.UNINITIALIZED:
            return False
        case ValueKind.NUMBER:
            return value.number != 0.0
        case ValueKind.STRING:
            return value.string != ""


def print_value(value: AwkValue) -> None:
    """Print one runtime value with the same formatting the LLVM path uses today."""
    print(coerce_scalar_to_string(value))


def initialize_builtin_variables(state: RuntimeState) -> None:
    """Seed the builtin variables tracked by the host runtime."""
    state.variables["NR"] = make_numeric_value(0.0)
    state.variables["FNR"] = make_numeric_value(0.0)
    state.variables["NF"] = make_numeric_value(0.0)
    state.variables["FILENAME"] = make_string_value(state.current_filename)


def update_record_builtin_variables(state: RuntimeState, record: RecordContext) -> None:
    """Refresh builtin variables for the active input record."""
    current_nr = coerce_scalar_to_number(state.variables.get("NR", make_numeric_value(0.0)))
    current_fnr = coerce_scalar_to_number(state.variables.get("FNR", make_numeric_value(0.0)))
    state.variables["NR"] = make_numeric_value(current_nr + 1.0)
    state.variables["FNR"] = make_numeric_value(current_fnr + 1.0)
    state.variables["NF"] = make_numeric_value(float(len(record.fields)))
    state.variables["FILENAME"] = make_string_value(state.current_filename)


def make_numeric_value(value: float) -> AwkValue:
    """Create one numeric runtime value."""
    return AwkValue(ValueKind.NUMBER, number=value)


def make_string_value(value: str) -> AwkValue:
    """Create one string runtime value."""
    return AwkValue(ValueKind.STRING, string=value)


def parse_awk_numeric_prefix(text: str) -> float:
    """Parse the numeric prefix AWK would use when coercing a string to a number."""
    match = NUMERIC_PREFIX_PATTERN.match(text)
    if match is None:
        return 0.0
    return float(match.group(1))


def compare_values(
    op: BinaryOp,
    left: Expr,
    right: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> bool:
    """Evaluate one comparison operator with AWK-style string/number coercions."""
    left_value = evaluate_value_expression(left, state, record, locals_scope)
    right_value = evaluate_value_expression(right, state, record, locals_scope)

    if left_value.kind is ValueKind.STRING or right_value.kind is ValueKind.STRING:
        left_string = coerce_scalar_to_string(left_value)
        right_string = coerce_scalar_to_string(right_value)
        match op:
            case BinaryOp.LESS:
                return left_string < right_string
            case BinaryOp.LESS_EQUAL:
                return left_string <= right_string
            case BinaryOp.GREATER:
                return left_string > right_string
            case BinaryOp.GREATER_EQUAL:
                return left_string >= right_string
            case BinaryOp.EQUAL:
                return left_string == right_string
            case BinaryOp.NOT_EQUAL:
                return left_string != right_string
            case _:
                raise RuntimeError(f"unsupported comparison operator in current runtime: {op.name}")

    left_number = coerce_scalar_to_number(left_value)
    right_number = coerce_scalar_to_number(right_value)
    match op:
        case BinaryOp.LESS:
            return left_number < right_number
        case BinaryOp.LESS_EQUAL:
            return left_number <= right_number
        case BinaryOp.GREATER:
            return left_number > right_number
        case BinaryOp.GREATER_EQUAL:
            return left_number >= right_number
        case BinaryOp.EQUAL:
            return left_number == right_number
        case BinaryOp.NOT_EQUAL:
            return left_number != right_number
        case _:
            raise RuntimeError(f"unsupported comparison operator in current runtime: {op.name}")


def evaluate_match_expression(
    left: Expr,
    right: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> bool:
    """Evaluate one string/regex match expression in the host runtime."""
    left_string = evaluate_string_expression(left, state, record, locals_scope)
    right_value = evaluate_value_expression(right, state, record, locals_scope)
    pattern_text = coerce_scalar_to_string(right_value)
    if isinstance(right, RegexLiteralExpr):
        pattern_text = right.raw_text[1:-1]
    return re.search(pattern_text, left_string) is not None


def evaluate_in_expression(
    left: Expr,
    right: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> bool:
    """Evaluate the current subset's array-membership operator."""
    if not isinstance(right, NameExpr):
        raise RuntimeError("the current runtime only supports `in` against a named array")
    key = coerce_scalar_to_string(evaluate_value_expression(left, state, record, locals_scope))
    return key in state.arrays.get(right.name, {})


def evaluate_field_index(
    expression: Expr,
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> int:
    """Evaluate one dynamic field reference into an integer field index."""
    return int(evaluate_numeric_expression(expression, state, record, locals_scope))


def assign_field_value(
    index_expression: Expr,
    value: AwkValue,
    state: RuntimeState,
    record: RecordContext,
    locals_scope: LocalScope | None,
) -> None:
    """Assign one value through a field lvalue and update `$0`/field views."""
    field_index = evaluate_field_index(index_expression, state, record, locals_scope)
    string_value = coerce_scalar_to_string(value)
    if field_index == 0:
        record.field0 = string_value
        record.fields = split_fields(string_value, state.field_separator)
        return
    if field_index < 0:
        raise RuntimeError("negative field indexes are not supported by the current runtime")

    while len(record.fields) < field_index:
        record.fields.append("")
    record.fields[field_index - 1] = string_value
    record.field0 = " ".join(record.fields)


def render_printf_output(
    arguments: tuple[Expr, ...],
    state: RuntimeState,
    record: RecordContext | None,
    locals_scope: LocalScope | None,
) -> str:
    """Render one `printf` call using the current subset's format support."""
    format_text = evaluate_string_expression(arguments[0], state, record, locals_scope)
    specifiers = [match.group(1) for match in PRINTF_SPEC_PATTERN.finditer(format_text) if match.group(1) != "%"]
    if len(specifiers) != len(arguments) - 1:
        raise RuntimeError("printf argument count does not match the format string in the current runtime")

    formatted_args: list[object] = []
    for specifier, argument in zip(specifiers, arguments[1:], strict=True):
        value = evaluate_value_expression(argument, state, record, locals_scope)
        if specifier in {"s"}:
            formatted_args.append(coerce_scalar_to_string(value))
            continue
        if specifier in {"d", "i", "o", "u", "x", "X"}:
            formatted_args.append(int(coerce_scalar_to_number(value)))
            continue
        formatted_args.append(coerce_scalar_to_number(value))

    if not formatted_args:
        return format_text % ()
    if len(formatted_args) == 1:
        return format_text % formatted_args[0]
    return format_text % tuple(formatted_args)


def format_numeric_value(value: float) -> str:
    """Render one numeric value using the current `%g`-style output shape."""
    return f"{value:g}"


def resolve_field_value(index: int, record: RecordContext) -> str:
    """Resolve the value of a supported field expression."""
    if index == 0:
        return record.field0
    field_position = index - 1
    if 0 <= field_position < len(record.fields):
        return record.fields[field_position]
    return ""


def static_field_index(expression: FieldExpr) -> int:
    """Return the current subset's literal field index or raise for dynamic fields."""
    if not isinstance(expression.index, int):
        raise RuntimeError("dynamic field expressions are not supported by the current execution path")
    return expression.index


def has_function_definitions(program: Program) -> bool:
    """Report whether `program` contains any top-level user-defined functions."""
    return any(isinstance(item, FunctionDef) for item in program.items)


def supports_direct_function_backend_subset(program: Program) -> bool:
    """Report whether `program` fits the direct LLVM-backed subset with user-defined functions."""
    if not has_function_definitions(program):
        return False

    direct_begin_statements = normalize_program_for_lowering(program).direct_begin_statements
    if direct_begin_statements is None:
        return False

    function_defs = {
        item.name: item
        for item in program.items
        if isinstance(item, FunctionDef)
    }

    def supports_expression(expression: Expr, local_names: frozenset[str] = frozenset()) -> bool:
        match expression:
            case NumericLiteralExpr():
                return True
            case NameExpr():
                return True
            case CallExpr(function=function_name, args=args):
                if function_name not in function_defs:
                    return False
                if len(args) != len(function_defs[function_name].params):
                    return False
                return all(supports_expression(argument, local_names) for argument in args)
            case BinaryExpr(op=BinaryOp.ADD | BinaryOp.LESS | BinaryOp.EQUAL | BinaryOp.LOGICAL_AND, left=left, right=right):
                return supports_expression(left, local_names) and supports_expression(right, local_names)
            case _:
                return False

    def supports_statement(statement: Stmt, *, in_function: bool, local_names: frozenset[str]) -> bool:
        match statement:
            case AssignStmt(op=AssignOp.PLAIN, target=NameLValue(), value=value):
                return supports_expression(value, local_names)
            case BlockStmt(statements=statements):
                return all(supports_statement(nested, in_function=in_function, local_names=local_names) for nested in statements)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                return supports_expression(condition, local_names) and supports_statement(
                    then_branch,
                    in_function=in_function,
                    local_names=local_names,
                ) and (
                    else_branch is None
                    or supports_statement(else_branch, in_function=in_function, local_names=local_names)
                )
            case WhileStmt(condition=condition, body=body):
                return supports_expression(condition, local_names) and supports_statement(
                    body,
                    in_function=in_function,
                    local_names=local_names,
                )
            case PrintStmt(arguments=arguments):
                return len(arguments) == 1 and (
                    isinstance(arguments[0], StringLiteralExpr) or supports_expression(arguments[0], local_names)
                )
            case ReturnStmt(value=value):
                return in_function and value is not None and supports_expression(value, local_names)
            case _:
                return False

    for function_def in function_defs.values():
        if not function_def.body.statements:
            return False
        if not isinstance(function_def.body.statements[-1], ReturnStmt):
            return False
        if any(isinstance(statement, ReturnStmt) for statement in function_def.body.statements[:-1]):
            return False
        local_names = frozenset(function_def.params)
        if not all(
            supports_statement(statement, in_function=True, local_names=local_names)
            for statement in function_def.body.statements
        ):
            return False

    return all(supports_statement(statement, in_function=False, local_names=frozenset()) for statement in direct_begin_statements)


def requires_host_runtime_execution(program: Program) -> bool:
    """Report whether execution must use the host runtime instead of LLVM lowering."""
    return (
        has_function_definitions(program)
        and not supports_direct_function_backend_subset(program)
    ) or (
        has_host_runtime_only_operations(program)
        and not supports_runtime_backend_subset(program)
        and not supports_direct_function_backend_subset(program)
    )


def requires_host_runtime_value_execution(program: Program) -> bool:
    """Report whether public execution needs the host runtime's richer value semantics."""
    if supports_runtime_backend_subset(program) or supports_direct_function_backend_subset(program):
        return False

    def expression_needs_value_runtime(expression: Expr, *, allow_string_literal: bool) -> bool:
        match expression:
            case NumericLiteralExpr():
                return False
            case StringLiteralExpr():
                return not allow_string_literal
            case NameExpr():
                return True
            case FieldExpr(index=index):
                return not isinstance(index, int)
            case ArrayIndexExpr() | CallExpr() | ConditionalExpr() | AssignExpr() | UnaryExpr() | PostfixExpr():
                return True
            case RegexLiteralExpr():
                return False
            case BinaryExpr(op=op, left=left, right=right):
                if op is BinaryOp.CONCAT:
                    return True
                return (
                    expression_needs_value_runtime(left, allow_string_literal=False)
                    or expression_needs_value_runtime(right, allow_string_literal=False)
                )
            case _:
                return True

    def statement_needs_value_runtime(statement: Stmt) -> bool:
        match statement:
            case AssignStmt(value=value):
                return expression_needs_value_runtime(value, allow_string_literal=False)
            case BlockStmt(statements=statements):
                return any(statement_needs_value_runtime(nested) for nested in statements)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                if expression_needs_value_runtime(condition, allow_string_literal=False):
                    return True
                if statement_needs_value_runtime(then_branch):
                    return True
                return else_branch is not None and statement_needs_value_runtime(else_branch)
            case WhileStmt(condition=condition, body=body):
                return (
                    expression_needs_value_runtime(condition, allow_string_literal=False)
                    or statement_needs_value_runtime(body)
                )
            case DoWhileStmt(body=body, condition=condition):
                return (
                    statement_needs_value_runtime(body)
                    or expression_needs_value_runtime(condition, allow_string_literal=False)
                )
            case PrintStmt(arguments=arguments):
                return any(
                    expression_needs_value_runtime(argument, allow_string_literal=True) for argument in arguments
                )
            case PrintfStmt(arguments=arguments):
                return any(
                    expression_needs_value_runtime(argument, allow_string_literal=False) for argument in arguments
                )
            case ExprStmt(value=value):
                return expression_needs_value_runtime(value, allow_string_literal=False)
            case ReturnStmt(value=value):
                return value is not None and expression_needs_value_runtime(value, allow_string_literal=False)
            case _:
                return False

    for item in program.items:
        if isinstance(item, FunctionDef):
            if any(statement_needs_value_runtime(statement) for statement in item.body.statements):
                return True
            continue
        if isinstance(item, PatternAction) and item.action is not None:
            if any(statement_needs_value_runtime(statement) for statement in item.action.statements):
                return True
        if isinstance(item, PatternAction) and item.action is None:
            return True
    return False


def supports_runtime_backend_subset(program: Program) -> bool:
    """Report whether `program` fits the reusable backend's current runtime-backed subset."""

    normalized_program = normalize_program_for_lowering(program)
    array_names = normalized_program.array_names

    def supports_string_expression(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        match expression:
            case StringLiteralExpr():
                return True
            case NameExpr(name=name):
                return name == "FILENAME" or name in string_bindings
            case NameExpr(name="FILENAME"):
                return True
            case FieldExpr():
                return True
            case ArrayIndexExpr(extra_indexes=()):
                return expression.array_name in array_names and supports_array_key(expression.index, string_bindings)
            case CallExpr(function="substr", args=args):
                return len(args) in {2, 3} and supports_string_expression(args[0], string_bindings) and all(
                    supports_numeric_expression(argument) for argument in args[1:]
                )
            case _:
                return False

    def supports_array_key(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        match expression:
            case NameExpr(name=name):
                return name in string_bindings
            case NumericLiteralExpr() | StringLiteralExpr():
                return True
            case _:
                return False

    def supports_numeric_expression(expression: Expr) -> bool:
        match expression:
            case NumericLiteralExpr():
                return True
            case NameExpr(name="NR" | "FNR" | "NF"):
                return True
            case NameExpr():
                return True
            case AssignExpr(op=AssignOp.PLAIN, target=target, value=value):
                match target:
                    case NameLValue() | FieldLValue():
                        return supports_numeric_expression(value)
                    case ArrayLValue(subscripts=subscripts):
                        return len(subscripts) == 1 and supports_array_key(subscripts[0]) and supports_numeric_expression(value)
                    case _:
                        return False
            case UnaryExpr(op=UnaryOp.UPLUS | UnaryOp.UMINUS | UnaryOp.NOT, operand=operand):
                return supports_numeric_expression(operand)
            case UnaryExpr(op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC, operand=NameExpr()):
                return True
            case PostfixExpr(op=PostfixOp.POST_INC | PostfixOp.POST_DEC, operand=NameExpr()):
                return True
            case BinaryExpr(
                op=BinaryOp.ADD | BinaryOp.LESS | BinaryOp.EQUAL | BinaryOp.LOGICAL_AND,
                left=left,
                right=right,
            ):
                return supports_numeric_expression(left) and supports_numeric_expression(right)
            case CallExpr(function="split", args=args):
                if len(args) not in {2, 3}:
                    return False
                if not supports_string_expression(args[0]):
                    return False
                if not isinstance(args[1], NameExpr):
                    return False
                return len(args) == 2 or supports_string_expression(args[2])
            case CallExpr(function="length", args=args):
                if len(args) > 1:
                    return False
                if not args:
                    return True
                argument = args[0]
                if isinstance(argument, NameExpr) and argument.name in array_names:
                    return True
                return supports_string_expression(argument)
            case _:
                return False

    def supports_pattern(pattern: ExprPattern | RangePattern | BeginPattern | EndPattern | None) -> bool:
        if pattern is None or isinstance(pattern, BeginPattern | EndPattern):
            return True
        if isinstance(pattern, ExprPattern):
            return isinstance(pattern.test, RegexLiteralExpr)
        if isinstance(pattern, RangePattern):
            return supports_pattern(pattern.left) and supports_pattern(pattern.right)
        return False

    def supports_side_effect_expression(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        return (
            supports_string_expression(expression, string_bindings)
            or supports_numeric_expression(expression)
            or (isinstance(expression, CallExpr) and expression.function == "split" and supports_numeric_expression(expression))
        )

    def supports_statement(statement: Stmt, string_bindings: frozenset[str] = frozenset()) -> bool:
        match statement:
            case AssignStmt(op=op, target=target, value=value):
                if op is not AssignOp.PLAIN:
                    return False
                match target:
                    case NameLValue():
                        return supports_numeric_expression(value)
                    case ArrayLValue(name=name, subscripts=subscripts):
                        return (
                            name in array_names
                            and len(subscripts) == 1
                            and supports_array_key(subscripts[0], string_bindings)
                            and supports_numeric_expression(value)
                        )
                    case FieldLValue(index=index):
                        return supports_numeric_expression(index) and supports_numeric_expression(value)
                    case _:
                        return False
            case BlockStmt(statements=statements):
                return all(supports_statement(nested, string_bindings) for nested in statements)
            case DeleteStmt():
                if statement.array_name is None or statement.array_name not in array_names or statement.extra_indexes:
                    return False
                return statement.index is None or supports_array_key(statement.index, string_bindings)
            case PrintStmt(arguments=arguments):
                if len(arguments) != 1:
                    return False
                argument = arguments[0]
                return (
                    supports_string_expression(argument, string_bindings)
                    or runtime_expression_has_string_result(argument)
                    or supports_numeric_expression(argument)
                )
            case PrintfStmt(arguments=arguments):
                if not arguments or not isinstance(arguments[0], StringLiteralExpr):
                    return False
                specifiers = [
                    match.group(1) for match in PRINTF_SPEC_PATTERN.finditer(arguments[0].value)
                    if match.group(1) != "%"
                ]
                if len(specifiers) != len(arguments) - 1:
                    return False
                for specifier, argument in zip(specifiers, arguments[1:], strict=True):
                    if specifier == "s":
                        if not supports_string_expression(argument, string_bindings):
                            return False
                        continue
                    if not supports_numeric_expression(argument):
                        return False
                return True
            case ExprStmt(value=value):
                return supports_side_effect_expression(value, string_bindings)
            case NextStmt():
                return True
            case ForStmt(init=init, condition=condition, update=update, body=body):
                return (
                    all(supports_side_effect_expression(expression, string_bindings) for expression in init)
                    and (condition is None or supports_numeric_expression(condition))
                    and all(supports_side_effect_expression(expression, string_bindings) for expression in update)
                    and supports_statement(body, string_bindings)
                )
            case ForInStmt(name=name, iterable=NameExpr(name=array_name), body=body):
                if array_name not in array_names:
                    return False
                return supports_statement(body, string_bindings | frozenset({name}))
            case _:
                return False

    found_supported_runtime_feature = False
    for item in program.items:
        if isinstance(item, FunctionDef):
            return False
        if not isinstance(item, PatternAction):
            return False
        if not supports_pattern(item.pattern):
            return False
        if item.action is None:
            if item.pattern is None:
                return False
            found_supported_runtime_feature = True
            continue
        if not all(supports_statement(statement) for statement in item.action.statements):
            return False
        if isinstance(item.pattern, RangePattern):
            found_supported_runtime_feature = True
        for statement in item.action.statements:
            if isinstance(statement, PrintfStmt):
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and statement.field_index is not None:
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and isinstance(statement.value, CallExpr):
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and isinstance(statement.target, ArrayLValue):
                found_supported_runtime_feature = True
            if isinstance(statement, DeleteStmt | ForStmt | ForInStmt):
                found_supported_runtime_feature = True
            if isinstance(statement, PrintStmt) and statement.arguments:
                argument = statement.arguments[0]
                if isinstance(argument, CallExpr) and argument.function == "length":
                    found_supported_runtime_feature = True
    return found_supported_runtime_feature


def has_host_runtime_only_operations(program: Program) -> bool:
    """Report whether `program` contains features not yet supported by LLVM lowering."""

    def expression_has_host_runtime_only_ops(expression: Expr) -> bool:
        match expression:
            case ArrayIndexExpr():
                return True
            case ConditionalExpr() | AssignExpr() | UnaryExpr() | PostfixExpr():
                return True
            case FieldExpr(index=index):
                if isinstance(index, int):
                    return False
                return True
            case BinaryExpr(op=op, left=left, right=right):
                if op not in {BinaryOp.ADD, BinaryOp.LESS, BinaryOp.EQUAL, BinaryOp.LOGICAL_AND}:
                    return True
                return expression_has_host_runtime_only_ops(left) or expression_has_host_runtime_only_ops(right)
            case CallExpr(function=function_name, args=args):
                if is_builtin_function_name(function_name):
                    return True
                return any(expression_has_host_runtime_only_ops(argument) for argument in args)
            case _:
                return False

    def statement_has_host_runtime_only_ops(statement: Stmt) -> bool:
        match statement:
            case AssignStmt(value=value):
                if statement.op is not statement.op.PLAIN:
                    return True
                if statement.name is None:
                    return True
                if statement.extra_indexes:
                    return True
                index = statement.index
                if index is not None:
                    return True
                return expression_has_host_runtime_only_ops(value)
            case BlockStmt(statements=statements):
                return any(statement_has_host_runtime_only_ops(nested) for nested in statements)
            case DeleteStmt():
                return True
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                if expression_has_host_runtime_only_ops(condition) or statement_has_host_runtime_only_ops(then_branch):
                    return True
                if else_branch is None:
                    return False
                return statement_has_host_runtime_only_ops(else_branch)
            case DoWhileStmt():
                return True
            case WhileStmt(condition=condition, body=body):
                return expression_has_host_runtime_only_ops(condition) or statement_has_host_runtime_only_ops(body)
            case ForStmt():
                return True
            case ForInStmt():
                return True
            case PrintStmt(arguments=arguments):
                return any(expression_has_host_runtime_only_ops(argument) for argument in arguments)
            case PrintfStmt():
                return True
            case ExprStmt():
                return True
            case NextStmt() | NextFileStmt() | ExitStmt():
                return True
            case ReturnStmt(value=value):
                if value is None:
                    return False
                return expression_has_host_runtime_only_ops(value)
            case _:
                return False

    for item in program.items:
        if isinstance(item, FunctionDef):
            if any(statement_has_host_runtime_only_ops(statement) for statement in item.body.statements):
                return True
            continue
        if isinstance(item, PatternAction):
            if item.action is None or isinstance(item.pattern, RangePattern):
                return True
            if isinstance(item.pattern, ExprPattern) and expression_has_host_runtime_only_ops(item.pattern.test):
                return True
            if item.action is not None and any(
                statement_has_host_runtime_only_ops(statement) for statement in item.action.statements
            ):
                return True
    return False


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
            *state.allocas,
            *state.instructions,
            "  ret void",
            "}",
        ]
    )


def render_user_function(function_def: FunctionDef, state: LoweringState) -> str:
    """Render one lowered direct-backend user-defined function."""
    arguments = ", ".join(["ptr %state", *(f"double %arg.{index}" for index, _ in enumerate(function_def.params))])
    return "\n".join(
        [
            f"define double @qk_fn_{function_def.name}({arguments}) {{",
            "entry:",
            *state.allocas,
            *state.instructions,
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
