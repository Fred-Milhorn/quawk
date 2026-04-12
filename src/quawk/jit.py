# Lowering and execution backend for the currently supported subset.
# This module converts the currently supported AST subset into LLVM IR text and
# shells out to LLVM tools for assembly emission and execution.

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Callable, Mapping, TextIO

from . import runtime_support
from .builtins import BUILTIN_ARRAY_NAMES, is_builtin_function_name, is_builtin_variable_name
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
    GetlineExpr,
    IfStmt,
    NameExpr,
    NameLValue,
    NextFileStmt,
    NextStmt,
    NumericLiteralExpr,
    OutputRedirect,
    OutputRedirectKind,
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
from .slot_allocation import SlotAllocation
from .type_inference import LatticeType, infer_variable_types

DEFAULT_OFMT = "%.6g"
DEFAULT_CONVFMT = "%.6g"
RUNTIME_TEXT_ENCODING = "utf-8"
RUNTIME_TEXT_ERRORS = "surrogateescape"
OUTPUT_REDIRECT_WRITE = 1
OUTPUT_REDIRECT_APPEND = 2
OUTPUT_REDIRECT_PIPE = 3
RAND_MODULUS = 2_147_483_648.0
RAND_MASK = 0x7FFFFFFF
RAND_MULTIPLIER = 1103515245
RAND_INCREMENT = 12345
FULL_NUMERIC_PATTERN = re.compile(r"^[ \t\r\n\f\v]*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[ \t\r\n\f\v]*$")
NUMERIC_PREFIX_PATTERN = re.compile(r"^[ \t\r\n\f\v]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")


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
    runtime_param: str | None = None
    state_param: str | None = None
    variable_indexes: dict[str, int] = field(default_factory=dict)
    slot_allocation: SlotAllocation | None = None
    type_info: dict[str, LatticeType] = field(default_factory=dict)
    action_exit_label: str | None = None
    phase_exit_label: str | None = None
    break_label: str | None = None
    continue_label: str | None = None
    array_names: frozenset[str] = field(default_factory=frozenset)
    loop_string_bindings: dict[str, str] = field(default_factory=dict)
    function_defs: dict[str, FunctionDef] = field(default_factory=dict)
    return_slot: str | None = None
    return_string_slot: str | None = None
    return_label: str | None = None
    initial_string_values: dict[str, str] = field(default_factory=dict)
    local_names: frozenset[str] = field(default_factory=frozenset)
    function_param_strings: dict[str, str] = field(default_factory=dict)

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


InitialVariableValue = float | str
InitialVariables = list[tuple[str, InitialVariableValue]]
PRINTF_SPEC_PATTERN = re.compile(r"%(?:[-+ #0]*\d*(?:\.\d+)?)([%aAcdeEfgGiosuxX])")


def initial_variables_require_string_runtime(initial_variables: InitialVariables | None) -> bool:
    """Report whether one initial-variable set needs runtime string storage."""
    if initial_variables is None:
        return False
    return any(isinstance(value, str) for _, value in initial_variables)


def awk_string_is_numeric(text: str) -> bool:
    """Report whether one string is fully numeric under AWK comparison rules."""
    return FULL_NUMERIC_PATTERN.fullmatch(text) is not None


def awk_numeric_prefix(text: str) -> float:
    """Parse one AWK numeric prefix, returning `0.0` when none is present."""
    match = NUMERIC_PREFIX_PATTERN.match(text)
    if match is None:
        return 0.0
    return float(match.group(1))


def decode_regex_literal(raw_text: str) -> str:
    """Decode one AWK regex literal body to the runtime regex text."""
    inner = raw_text[1:-1]
    result: list[str] = []
    index = 0

    while index < len(inner):
        char = inner[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        index += 1
        if index >= len(inner):
            result.append("\\")
            break

        escaped = inner[index]
        match escaped:
            case "\\" | "/":
                result.append(escaped)
            case "n":
                result.append("\n")
            case "t":
                result.append("\t")
            case _:
                result.append("\\")
                result.append(escaped)
        index += 1

    return "".join(result)


def emit_assembly(llvm_ir: str) -> str:
    """Run `llc` on LLVM IR and return the emitted assembly text."""
    llc_path = shutil.which("llc")
    if llc_path is None:
        raise RuntimeError("LLVM code generation tool 'llc' is not available on PATH")
    pruned_ir = prune_ir_for_assembly(llvm_ir)

    result = subprocess.run(
        [llc_path, "-o", "-", "-"],
        input=pruned_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "llc failed to produce assembly output")
    return result.stdout


def execute(program: Program, initial_variables: InitialVariables | None = None, *, optimize: bool = False) -> int:
    """Lower `program` to IR, run it with `lli`, and return the process status."""
    ensure_public_execution_supported(program, initial_variables)
    llvm_ir = build_public_execution_llvm_ir(program, [], None, initial_variables, optimize=optimize)
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
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
    return result.returncode


def lower_to_llvm_ir(program: Program, initial_variables: InitialVariables | None = None) -> str:
    """Lower the currently supported AST subset to LLVM IR text."""
    has_functions = has_function_definitions(program)
    direct_function_subset = has_functions and supports_direct_function_backend_subset(program)
    if has_functions and not direct_function_subset:
        normalized_program = normalize_program_for_lowering(program)
        type_info = infer_variable_types(program)
        return lower_reusable_program_to_llvm_ir(program, normalized_program, type_info)
    if has_host_runtime_only_operations(program) and not (
        supports_runtime_backend_subset(program) or supports_direct_function_backend_subset(program)
    ):
        raise RuntimeError("host-runtime-only operations are not supported by the LLVM-backed backend")
    normalized_program = normalize_program_for_lowering(program)
    type_info = infer_variable_types(program)
    if direct_function_subset:
        return lower_direct_function_program_to_llvm_ir(program, normalized_program, type_info, initial_variables)
    if initial_variables_require_string_runtime(initial_variables):
        return lower_reusable_program_to_llvm_ir(program, normalized_program, type_info)
    if supports_runtime_backend_subset(program):
        return lower_reusable_program_to_llvm_ir(program, normalized_program, type_info)
    if requires_input_aware_execution(program):
        return lower_reusable_program_to_llvm_ir(program, normalized_program, type_info)

    state = LoweringState(type_info=type_info)
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
    type_info: dict[str, LatticeType],
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
    state_type = render_state_type(normalized_program.slot_allocation)
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
            type_info=type_info,
            function_defs=function_defs,
            string_index=string_index,
            numeric_format_declared=numeric_format_declared,
            initial_string_values={
                name: value for name, value in (initial_variables or []) if isinstance(value, str)
            },
            local_names=frozenset(function_def.params),
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
        type_info=type_info,
        function_defs=function_defs,
        string_index=string_index,
        uses_printf=uses_printf,
        numeric_format_declared=numeric_format_declared,
        initial_string_values={
            name: value for name, value in (initial_variables or []) if isinstance(value, str)
        },
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
    *,
    optimize: bool = False,
) -> str:
    """Build the IR module used by public execution and inspection paths."""
    llvm_ir = lower_to_llvm_ir(program, initial_variables=initial_variables)
    if program_requires_linked_execution_module(program, initial_variables):
        llvm_ir = link_reusable_execution_module(llvm_ir, program, input_files, field_separator, initial_variables)
    if optimize:
        return optimize_ir(llvm_ir)
    return llvm_ir


def build_public_inspection_llvm_ir(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    optimize: bool = False,
) -> str:
    """Build the IR module used by public inspection modes."""
    llvm_ir = lower_to_llvm_ir(program, initial_variables=initial_variables)
    if program_requires_linked_execution_module(program, initial_variables):
        llvm_ir = link_reusable_inspection_module(llvm_ir, program, input_files, field_separator, initial_variables)
    if optimize:
        return optimize_ir(llvm_ir)
    return llvm_ir


OPTIMIZATION_PASS_PIPELINES: dict[int, tuple[str, ...]] = {
    1: ("-passes=mem2reg,instcombine,simplifycfg,gvn",),
    2: ("-O2", "-vectorize-loops"),
}
ASSEMBLY_PRUNE_FLAGS: tuple[str, ...] = (
    "-passes=internalize,globaldce",
    "-internalize-public-api-list=quawk_main",
)


def optimization_passes_for_level(level: int) -> list[str]:
    """Return the LLVM `opt` flags for one supported optimization level."""
    return list(OPTIMIZATION_PASS_PIPELINES.get(level, OPTIMIZATION_PASS_PIPELINES[1]))


def optimize_ir(llvm_ir: str, level: int = 1) -> str:
    """Run LLVM `opt` over one generated IR module and return optimized text."""
    try:
        opt_path = runtime_support.find_llvm_opt()
    except RuntimeError as exc:
        warnings.warn(str(exc), RuntimeWarning)
        return llvm_ir
    result = subprocess.run(
        [opt_path, *optimization_passes_for_level(level), "-S"],
        input=llvm_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "opt failed to optimize generated IR")
    return result.stdout


def prune_ir_for_assembly(llvm_ir: str) -> str:
    """Drop unreachable linked helpers before lowering one module to assembly."""
    try:
        opt_path = runtime_support.find_llvm_opt()
    except RuntimeError:
        return llvm_ir
    result = subprocess.run(
        [opt_path, *ASSEMBLY_PRUNE_FLAGS, "-S"],
        input=llvm_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "opt failed to prune generated assembly IR")
    return result.stdout


def program_requires_linked_execution_module(
    program: Program,
    initial_variables: InitialVariables | None = None,
) -> bool:
    """Report whether public execution/inspection needs the reusable driver module."""
    direct_function_subset = supports_direct_function_backend_subset(program)
    return (
        (supports_runtime_backend_subset(program) and not direct_function_subset)
        or requires_input_aware_execution(program)
        or (initial_variables_require_string_runtime(initial_variables) and not direct_function_subset)
    )


def lower_runtime_user_functions_to_ir(
    program: Program,
    variable_indexes: dict[str, int],
    slot_allocation: SlotAllocation,
    type_info: dict[str, LatticeType],
    array_names: frozenset[str],
) -> tuple[list[str], list[str], int]:
    """Lower supported runtime-backed user-defined functions."""
    function_defs = {
        item.name: item
        for item in program.items
        if isinstance(item, FunctionDef)
    }
    if not function_defs:
        return [], [], 0

    globals_out: list[str] = []
    bodies: list[str] = []
    string_index = 0

    for function_def in function_defs.values():
        function_state = LoweringState(
            runtime_param="%rt",
            state_param="%state",
            variable_indexes=variable_indexes,
            slot_allocation=slot_allocation,
            type_info=type_info,
            array_names=array_names,
            function_defs=function_defs,
            string_index=string_index,
            function_param_strings={param: f"%arg.{index}" for index, param in enumerate(function_def.params)},
            local_names=frozenset(function_def.params),
        )
        return_slot = function_state.next_temp("retval")
        function_state.allocas.append(f"  {return_slot} = alloca ptr")
        empty_value = lower_runtime_constant_string("", function_state)
        function_state.instructions.append(f"  store ptr {empty_value}, ptr {return_slot}")
        function_state.return_string_slot = return_slot
        function_state.return_label = function_state.next_label("return")
        terminated = False
        for statement in function_def.body.statements:
            lower_statement(statement, function_state)
            if isinstance(statement, ReturnStmt | ExitStmt):
                terminated = True
                break
        if not terminated:
            function_state.instructions.append(f"  br label %{function_state.return_label}")
        function_state.instructions.extend(
            [
                f"{function_state.return_label}:",
                f"  %retval.load = load ptr, ptr {return_slot}",
                "  ret ptr %retval.load",
            ]
        )
        bodies.append(render_runtime_user_function(function_def, function_state))
        globals_out.extend(function_state.globals)
        string_index = function_state.string_index

    return globals_out, bodies, string_index


def lower_reusable_program_to_llvm_ir(
    program: Program,
    normalized_program: NormalizedLoweringProgram,
    type_info: dict[str, LatticeType],
) -> str:
    """Lower a record-driven program into reusable BEGIN/record/END LLVM IR."""
    begin_actions = normalized_program.begin_actions
    record_items = normalized_program.record_items
    end_actions = normalized_program.end_actions
    variable_indexes = normalized_program.variable_indexes
    array_names = normalized_program.array_names
    state_type = render_state_type(normalized_program.slot_allocation)

    declarations = [
        "declare ptr @qk_get_field_inline(ptr, i64)",
        "declare void @qk_set_field_string(ptr, i64, ptr)",
        "declare void @qk_set_field_number(ptr, i64, double)",
        "declare void @qk_print_string(ptr, ptr)",
        "declare void @qk_print_number(ptr, double)",
        "declare void @qk_print_string_fragment(ptr, ptr)",
        "declare void @qk_print_number_fragment(ptr, double)",
        "declare void @qk_print_output_separator(ptr)",
        "declare void @qk_print_output_record_separator(ptr)",
        "declare ptr @qk_open_output(ptr, ptr, i32)",
        "declare double @qk_close_output(ptr, ptr)",
        "declare void @qk_write_output_string(ptr, ptr)",
        "declare void @qk_write_output_number(ptr, ptr, double)",
        "declare void @qk_write_output_separator(ptr, ptr)",
        "declare void @qk_write_output_record_separator(ptr, ptr)",
        "declare void @qk_nextfile(ptr)",
        "declare void @qk_request_exit(ptr, i32)",
        "declare i1 @qk_regex_match_current_record(ptr, ptr)",
        "declare i1 @qk_regex_match_text(ptr, ptr)",
        "declare ptr @qk_scalar_get_inline(ptr, ptr)",
        "declare double @qk_scalar_get_number_inline(ptr, ptr)",
        "declare i1 @qk_scalar_truthy(ptr, ptr)",
        "declare void @qk_scalar_set_string(ptr, ptr, ptr)",
        "declare void @qk_scalar_set_number_inline(ptr, ptr, double)",
        "declare void @qk_scalar_copy(ptr, ptr, ptr)",
        "declare double @qk_slot_get_number(ptr, i64)",
        "declare void @qk_slot_set_number(ptr, i64, double)",
        "declare ptr @qk_slot_get_string(ptr, i64)",
        "declare void @qk_slot_set_string(ptr, i64, ptr)",
        "declare ptr @qk_capture_string_arg_inline(ptr, ptr)",
        "declare double @qk_parse_number_text(ptr)",
        "declare ptr @qk_format_number(ptr, double)",
        "declare ptr @qk_concat(ptr, ptr, ptr)",
        "declare double @qk_index(ptr, ptr, ptr)",
        "declare double @qk_match(ptr, ptr, ptr)",
        "declare double @qk_substitute(ptr, ptr, ptr, ptr, i1, ptr)",
        "declare ptr @qk_sprintf(ptr, ptr, i32, ptr, ptr)",
        "declare ptr @qk_tolower(ptr, ptr)",
        "declare ptr @qk_toupper(ptr, ptr)",
        "declare double @qk_atan2(double, double)",
        "declare double @qk_cos(double)",
        "declare double @qk_exp(double)",
        "declare double @qk_int_builtin(double)",
        "declare double @qk_log(double)",
        "declare double @qk_rand(ptr)",
        "declare double @qk_sin(double)",
        "declare double @qk_sqrt(double)",
        "declare double @qk_srand0(ptr)",
        "declare double @qk_srand1(ptr, double)",
        "declare double @qk_system(ptr, ptr)",
        "declare double @qk_getline_main_record(ptr)",
        "declare double @qk_getline_main_string(ptr, ptr)",
        "declare double @qk_getline_file_record(ptr, ptr)",
        "declare double @qk_getline_file_string(ptr, ptr, ptr)",
        "declare double @qk_get_nr_inline(ptr)",
        "declare double @qk_get_fnr_inline(ptr)",
        "declare double @qk_get_nf_inline(ptr)",
        "declare ptr @qk_get_filename_inline(ptr)",
        "declare double @qk_split_into_array(ptr, ptr, ptr, ptr)",
        "declare ptr @qk_array_get(ptr, ptr, ptr)",
        "declare i1 @qk_array_contains(ptr, ptr, ptr)",
        "declare void @qk_array_set_string(ptr, ptr, ptr, ptr)",
        "declare void @qk_array_set_number(ptr, ptr, ptr, double)",
        "declare void @qk_array_delete(ptr, ptr, ptr)",
        "declare void @qk_array_clear(ptr, ptr)",
        "declare double @qk_array_length(ptr, ptr)",
        "declare ptr @qk_array_first_key(ptr, ptr)",
        "declare ptr @qk_array_next_key(ptr, ptr, ptr)",
        "declare ptr @qk_substr2(ptr, ptr, i64)",
        "declare ptr @qk_substr3(ptr, ptr, i64, i64)",
        "declare i64 @strlen(ptr)",
        "declare double @llvm.pow.f64(double, double)",
        "declare double @llvm.trunc.f64(double)",
        "declare i1 @qk_compare_values_inline(ptr, double, i1, i1, ptr, double, i1, i1, i32)",
        "declare i32 @fprintf(ptr, ptr, ...)",
        "declare i32 @printf(ptr, ...)",
    ]
    if state_type is not None:
        declarations.append(state_type)

    function_globals, function_bodies, function_string_index = lower_runtime_user_functions_to_ir(
        program, variable_indexes, normalized_program.slot_allocation, type_info, array_names
    )

    begin_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        slot_allocation=normalized_program.slot_allocation,
        type_info=type_info,
        array_names=array_names,
        function_defs={item.name: item for item in program.items if isinstance(item, FunctionDef)},
        string_index=function_string_index,
    )
    begin_state.phase_exit_label = begin_state.next_label("phase.exit")
    for action in begin_actions:
        lower_action(action, begin_state)

    record_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        slot_allocation=normalized_program.slot_allocation,
        type_info=type_info,
        string_index=begin_state.string_index,
        array_names=array_names,
        function_defs={item.name: item for item in program.items if isinstance(item, FunctionDef)},
    )
    record_state.phase_exit_label = record_state.next_label("phase.exit")
    for record_item in record_items:
        lower_runtime_record_item(record_item.pattern, record_item.action, record_state, record_item.range_state_name)

    end_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        slot_allocation=normalized_program.slot_allocation,
        type_info=type_info,
        string_index=record_state.string_index,
        array_names=array_names,
        function_defs={item.name: item for item in program.items if isinstance(item, FunctionDef)},
    )
    end_state.phase_exit_label = end_state.next_label("phase.exit")
    for action in end_actions:
        lower_action(action, end_state)

    return "\n".join(
        [
            *declarations,
            "",
            *function_globals,
            *begin_state.globals,
            *record_state.globals,
            *end_state.globals,
            "",
            *function_bodies,
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
            if state.break_label is None:
                raise RuntimeError("break statements are not supported by the current backend")
            state.instructions.append(f"  br label %{state.break_label}")
        case ContinueStmt():
            if state.continue_label is None:
                raise RuntimeError("continue statements are not supported by the current backend")
            state.instructions.append(f"  br label %{state.continue_label}")
        case DeleteStmt():
            if state.runtime_param is None:
                raise RuntimeError("delete statements are not supported by the direct LLVM-backed backend")
            lower_runtime_delete_statement(statement, state)
        case IfStmt():
            lower_if_statement(statement, state)
        case DoWhileStmt():
            lower_do_while_statement(statement, state)
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
            if state.return_label is None:
                raise RuntimeError("return statements are not supported by the LLVM-backed backend")
            if state.return_string_slot is not None:
                if statement.value is None:
                    return_value = lower_runtime_constant_string("", state)
                elif runtime_expression_has_string_result(statement.value, state):
                    return_value = lower_runtime_string_expression(statement.value, state)
                else:
                    return_value = lower_runtime_string_from_numeric_value(
                        lower_runtime_numeric_expression(statement.value, state), state
                    )
                state.instructions.extend(
                    [
                        f"  store ptr {return_value}, ptr {state.return_string_slot}",
                        f"  br label %{state.return_label}",
                    ]
                )
                return
            if state.return_slot is None:
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
            if state.runtime_param is not None:
                lower_runtime_print_statement(statement, state)
            else:
                if len(arguments) != 1:
                    raise RuntimeError("the direct LLVM-backed backend only supports print with one argument")
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
            if state.runtime_param is None or state.phase_exit_label is None:
                raise RuntimeError("next is not supported by the direct LLVM-backed backend")
            state.instructions.append(f"  br label %{state.phase_exit_label}")
        case NextFileStmt():
            if state.runtime_param is None or state.phase_exit_label is None:
                raise RuntimeError("nextfile is not supported by the direct LLVM-backed backend")
            state.instructions.extend(
                [
                    f"  call void @qk_nextfile(ptr {state.runtime_param})",
                    f"  br label %{state.phase_exit_label}",
                ]
            )
        case ExitStmt(value=value):
            if state.runtime_param is None:
                raise RuntimeError("exit is not supported by the direct LLVM-backed backend")
            status_value = "0"
            if value is not None:
                numeric_value = lower_runtime_numeric_expression(value, state)
                status_temp = state.next_temp("exit.status")
                state.instructions.append(f"  {status_temp} = fptosi double {numeric_value} to i32")
                status_value = status_temp
            state.instructions.append(f"  call void @qk_request_exit(ptr {state.runtime_param}, i32 {status_value})")
            if state.phase_exit_label is not None:
                state.instructions.append(f"  br label %{state.phase_exit_label}")
            elif state.return_string_slot is not None and state.return_label is not None:
                empty_value = lower_runtime_constant_string("", state)
                state.instructions.extend(
                    [
                        f"  store ptr {empty_value}, ptr {state.return_string_slot}",
                        f"  br label %{state.return_label}",
                    ]
                )
            else:
                raise RuntimeError("exit is not supported in this LLVM-backed backend context")
        case _:
            raise RuntimeError("the current backend only supports print, assignment, block, if, and while statements")


def lower_record_item(pattern: ExprPattern | None, action: Action, state: LoweringState) -> None:
    """Lower one record-phase item in the reusable runtime model."""
    if pattern is None:
        lower_action(action, state)
        return

    condition = lower_record_pattern(pattern, state)
    then_label = state.next_label("record.match")
    end_label = state.next_label("record.next")
    state.instructions.append(f"  br i1 {condition}, label %{then_label}, label %{end_label}")
    state.instructions.append(f"{then_label}:")
    lower_action(action, state)
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
                f"  {field_ptr} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 0)",
                f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {field_ptr})",
            ]
        )
        return
    lower_action(action, state)


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
    active_value = state.next_temp("range.activeval")
    active_flag = state.next_temp("range.activeflag")
    active_label = state.next_label("range.active.label")
    inactive_label = state.next_label("range.inactive.label")
    end_label = state.next_label("range.end.label")
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
    keep_active = state.next_temp("range.keepflag")
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
    matched_label = state.next_label("range.matched.label")
    state.instructions.append(f"  br i1 {left_matches}, label %{matched_label}, label %{end_label}")
    state.instructions.append(f"{matched_label}:")
    lower_runtime_action_or_default(action, state)
    right_after_start = lower_record_pattern(pattern.right, state)
    start_keep_active = state.next_temp("range.start.keepflag")
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


def lower_action(action: Action, state: LoweringState) -> None:
    """Lower one action block."""
    previous_exit_label = state.action_exit_label
    if state.runtime_param is not None:
        state.action_exit_label = state.next_label("action.exit")
    try:
        terminated = False
        for statement in action.statements:
            lower_statement(statement, state)
            if state.runtime_param is not None and isinstance(statement, NextStmt | NextFileStmt | ExitStmt):
                terminated = True
                break
        if state.runtime_param is not None and state.action_exit_label is not None:
            if not terminated:
                state.instructions.append(f"  br label %{state.action_exit_label}")
            state.instructions.append(f"{state.action_exit_label}:")
    finally:
        state.action_exit_label = previous_exit_label


def lower_if_statement(statement: IfStmt, state: LoweringState) -> None:
    """Lower an `if` statement with a single then-branch."""
    then_label = state.next_label("if.then")
    else_label = state.next_label("if.else") if statement.else_branch is not None else None
    end_label = state.next_label("if.end")
    condition = lower_condition_expression(statement.condition, state)
    false_target = end_label if else_label is None else else_label
    state.instructions.append(f"  br i1 {condition}, label %{then_label}, label %{false_target}")
    state.instructions.append(f"{then_label}:")
    lower_statement(statement.then_branch, state)
    state.instructions.append(f"  br label %{end_label}")
    if statement.else_branch is not None and else_label is not None:
        state.instructions.append(f"{else_label}:")
        lower_statement(statement.else_branch, state)
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
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = cond_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{end_label}:")


def lower_do_while_statement(statement: DoWhileStmt, state: LoweringState) -> None:
    """Lower a `do ... while` loop in the current backend subset."""
    body_label = state.next_label("dowhile.body")
    cond_label = state.next_label("dowhile.cond")
    end_label = state.next_label("dowhile.end")
    state.instructions.append(f"  br label %{body_label}")
    state.instructions.append(f"{body_label}:")
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = cond_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{cond_label}:")
    condition = lower_condition_expression(statement.condition, state)
    state.instructions.append(f"  br i1 {condition}, label %{body_label}, label %{end_label}")
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
    state.initial_string_values.pop(statement.name, None)
    numeric_value = lower_numeric_expression(statement.value, state)
    state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")


def lower_runtime_assignment_statement(statement: AssignStmt, state: LoweringState) -> None:
    """Lower one runtime-backed assignment in the reusable backend subset."""
    assert state.runtime_param is not None

    def combine_numeric_assignment(current_value: str, update_value: str) -> str:
        if statement.op is AssignOp.PLAIN:
            return update_value
        result = state.next_temp("assign.op")
        if statement.op is AssignOp.ADD:
            state.instructions.append(f"  {result} = fadd double {current_value}, {update_value}")
            return result
        if statement.op is AssignOp.SUB:
            state.instructions.append(f"  {result} = fsub double {current_value}, {update_value}")
            return result
        if statement.op is AssignOp.MUL:
            state.instructions.append(f"  {result} = fmul double {current_value}, {update_value}")
            return result
        if statement.op is AssignOp.DIV:
            state.instructions.append(f"  {result} = fdiv double {current_value}, {update_value}")
            return result
        if statement.op is AssignOp.MOD:
            quotient = state.next_temp("assign.mod.div")
            truncated = state.next_temp("assign.mod.trunc")
            product = state.next_temp("assign.mod.mul")
            state.instructions.extend(
                [
                    f"  {quotient} = fdiv double {current_value}, {update_value}",
                    f"  {truncated} = call double @llvm.trunc.f64(double {quotient})",
                    f"  {product} = fmul double {truncated}, {update_value}",
                    f"  {result} = fsub double {current_value}, {product}",
                ]
            )
            return result
        state.instructions.append(
            f"  {result} = call double @llvm.pow.f64(double {current_value}, double {update_value})"
        )
        return result

    field_index = statement.field_index
    if field_index is not None:
        index_value = lower_runtime_field_index(field_index, state)
        if statement.op is AssignOp.PLAIN and runtime_assignment_preserves_string(statement.value, state):
            string_value = lower_runtime_string_expression(statement.value, state)
            state.instructions.append(
                f"  call void @qk_set_field_string(ptr {state.runtime_param}, i64 {index_value}, ptr {string_value})"
            )
        else:
            current_field = state.next_temp("field.current")
            current_value = state.next_temp("field.current.num")
            state.instructions.extend(
                [
                    f"  {current_field} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 {index_value})",
                    f"  {current_value} = call double @qk_parse_number_text(ptr {current_field})",
                ]
            )
            numeric_value = lower_runtime_numeric_expression(statement.value, state)
            numeric_value = combine_numeric_assignment(current_value, numeric_value)
            state.instructions.append(
                f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {index_value}, double {numeric_value})"
            )
        return

    if statement.name is None:
        raise RuntimeError("non-scalar assignments are not supported by the runtime-backed backend")
    if statement.index is not None:
        array_name_ptr = lower_runtime_constant_string(statement.name, state)
        key_ptr = lower_runtime_array_subscripts((statement.index, *statement.extra_indexes), state)
        if statement.op is AssignOp.PLAIN and runtime_assignment_preserves_string(statement.value, state):
            string_value = lower_runtime_string_expression(statement.value, state)
            state.instructions.append(
                (
                    f"  call void @qk_array_set_string("
                    f"ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, ptr {string_value})"
                )
            )
        else:
            current_entry = state.next_temp("array.current")
            current_value = state.next_temp("array.current.num")
            state.instructions.extend(
                [
                    f"  {current_entry} = call ptr @qk_array_get(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})",
                    f"  {current_value} = call double @qk_parse_number_text(ptr {current_entry})",
                ]
            )
            numeric_value = lower_runtime_numeric_expression(statement.value, state)
            numeric_value = combine_numeric_assignment(current_value, numeric_value)
            state.instructions.append(
                (
                    f"  call void @qk_array_set_number("
                    f"ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {numeric_value})"
                )
            )
        return
    if is_reusable_runtime_state_name(statement.name):
        slot_name = variable_address(statement.name, state)
        numeric_value = lower_runtime_numeric_expression(statement.value, state)
        if statement.op is not AssignOp.PLAIN:
            current_value = state.next_temp("state.current")
            state.instructions.append(f"  {current_value} = load double, ptr {slot_name}")
            numeric_value = combine_numeric_assignment(current_value, numeric_value)
        state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
        return
    if runtime_name_uses_numeric_slot_state(statement.name, state):
        slot_name = variable_address(statement.name, state)
        numeric_value = lower_runtime_numeric_expression(statement.value, state)
        if statement.op is not AssignOp.PLAIN:
            current_value = state.next_temp("state.current")
            state.instructions.append(f"  {current_value} = load double, ptr {slot_name}")
            numeric_value = combine_numeric_assignment(current_value, numeric_value)
        state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
        return

    slot_index = runtime_name_slot_index(statement.name, state)
    target_name = lower_runtime_scalar_name(statement.name, state)
    if (
        statement.op is AssignOp.PLAIN
        and isinstance(statement.value, NameExpr)
        and runtime_name_uses_scalar_runtime(statement.value.name, state)
        and not runtime_name_uses_string_slot_runtime(statement.name, state)
    ):
        source_name = lower_runtime_scalar_name(statement.value.name, state)
        state.instructions.append(
            f"  call void @qk_scalar_copy(ptr {state.runtime_param}, ptr {target_name}, ptr {source_name})"
        )
        source_slot_index = runtime_name_slot_index(statement.value.name, state)
        if slot_index is not None and source_slot_index is not None:
            source_numeric = state.next_temp("slot.copy.src")
            state.instructions.append(
                f"  {source_numeric} = call double @qk_slot_get_number(ptr {state.runtime_param}, i64 {source_slot_index})"
            )
            state.instructions.append(
                f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {source_numeric})"
            )
        return
    if statement.op is AssignOp.PLAIN and runtime_assignment_preserves_string(statement.value, state):
        string_value = lower_runtime_string_expression(statement.value, state)
        if runtime_name_uses_string_slot_runtime(statement.name, state):
            assert slot_index is not None
            numeric_value = state.next_temp("slot.assign.str")
            state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
            state.instructions.append(
                f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
            )
            state.instructions.append(
                f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
            )
            return
        state.instructions.append(
            f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {target_name}, ptr {string_value})"
        )
        if slot_index is not None:
            numeric_value = state.next_temp("slot.assign.str")
            state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
            state.instructions.append(
                f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
            )
        return

    current_value = state.next_temp("scalar.current")
    if runtime_name_uses_string_slot_runtime(statement.name, state):
        assert slot_index is not None
        state.instructions.append(
            f"  {current_value} = call double @qk_slot_get_number(ptr {state.runtime_param}, i64 {slot_index})"
        )
    else:
        state.instructions.append(
            f"  {current_value} = call double @qk_scalar_get_number_inline(ptr {state.runtime_param}, ptr {target_name})"
        )
    numeric_value = lower_runtime_numeric_expression(statement.value, state)
    numeric_value = combine_numeric_assignment(current_value, numeric_value)
    if runtime_name_uses_string_slot_runtime(statement.name, state):
        assert slot_index is not None
        state.instructions.append(
            f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
        )
    state.instructions.append(
        f"  call void @qk_scalar_set_number_inline(ptr {state.runtime_param}, ptr {target_name}, double {numeric_value})"
    )


def lower_runtime_delete_statement(statement: DeleteStmt, state: LoweringState) -> None:
    """Lower one `delete` statement in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    array_name = statement.array_name
    if array_name is None:
        raise RuntimeError("non-array delete targets are not supported by the runtime-backed backend")

    array_name_ptr = lower_runtime_constant_string(array_name, state)
    if statement.index is None:
        state.instructions.append(f"  call void @qk_array_clear(ptr {state.runtime_param}, ptr {array_name_ptr})")
        return
    key_ptr = lower_runtime_array_subscripts((statement.index, *statement.extra_indexes), state)
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
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = update_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
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
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = step_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
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
    """Seed ordered preassignments before user statements execute."""
    for name, value in initial_variables:
        slot_name = variable_address(name, state)
        if isinstance(value, str):
            state.initial_string_values[name] = value
            state.instructions.append(f"  store double 0.000000000000000e+00, ptr {slot_name}")
            continue
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
    if (
        isinstance(expression, NameExpr)
        and expression.name in state.initial_string_values
        and expression.name not in state.local_names
    ):
        state.uses_puts = True
        global_name, byte_length = declare_string(state, state.initial_string_values[expression.name])
        string_ptr = state.next_temp("strptr")
        call_temp = state.next_temp("call")
        state.instructions.extend(
            [
                emit_gep(string_ptr, byte_length, global_name),
                f"  {call_temp} = call i32 @puts(ptr {string_ptr})",
            ]
        )
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
        raise RuntimeError("field expressions require the reusable runtime backend")

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


def lower_runtime_print_fragment(expression: Expr, state: LoweringState) -> None:
    """Lower one runtime-backed print argument without separators or terminator."""
    assert state.runtime_param is not None
    if runtime_expression_has_string_result(expression, state):
        string_value = lower_runtime_string_expression(expression, state)
        state.instructions.append(f"  call void @qk_print_string_fragment(ptr {state.runtime_param}, ptr {string_value})")
        return

    numeric_value = lower_runtime_numeric_expression(expression, state)
    state.instructions.append(f"  call void @qk_print_number_fragment(ptr {state.runtime_param}, double {numeric_value})")


def output_redirect_mode_value(kind: OutputRedirectKind) -> int:
    """Map one redirect kind to the runtime ABI mode integer."""
    match kind:
        case OutputRedirectKind.WRITE:
            return OUTPUT_REDIRECT_WRITE
        case OutputRedirectKind.APPEND:
            return OUTPUT_REDIRECT_APPEND
        case OutputRedirectKind.PIPE:
            return OUTPUT_REDIRECT_PIPE
    raise AssertionError(f"unhandled redirect kind: {kind!r}")


def lower_runtime_output_target(redirect: OutputRedirect, state: LoweringState) -> str:
    """Lower one redirect target expression to the runtime string ABI."""
    if runtime_expression_has_string_result(redirect.target, state):
        return lower_runtime_string_expression(redirect.target, state)
    return lower_runtime_string_expression(redirect.target, state)


def lower_runtime_print_statement(statement: PrintStmt, state: LoweringState) -> None:
    """Lower one `print` statement against the reusable runtime ABI."""
    assert state.runtime_param is not None
    arguments = statement.arguments
    redirect = statement.redirect
    if redirect is not None:
        target_ptr = lower_runtime_output_target(redirect, state)
        output_handle = state.next_temp("print.output")
        state.instructions.append(
            f"  {output_handle} = call ptr @qk_open_output(ptr {state.runtime_param}, ptr {target_ptr}, i32 {output_redirect_mode_value(redirect.kind)})"
        )
        if not arguments:
            field_ptr = state.next_temp("print.field0")
            state.instructions.extend(
                [
                    f"  {field_ptr} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 0)",
                    f"  call void @qk_write_output_string(ptr {output_handle}, ptr {field_ptr})",
                    f"  call void @qk_write_output_record_separator(ptr {state.runtime_param}, ptr {output_handle})",
                ]
            )
            return

        for index, argument in enumerate(arguments):
            if index > 0:
                state.instructions.append(
                    f"  call void @qk_write_output_separator(ptr {state.runtime_param}, ptr {output_handle})"
                )
            if runtime_expression_has_string_result(argument, state):
                string_value = lower_runtime_string_expression(argument, state)
                state.instructions.append(f"  call void @qk_write_output_string(ptr {output_handle}, ptr {string_value})")
            else:
                numeric_value = lower_runtime_numeric_expression(argument, state)
                state.instructions.append(
                    f"  call void @qk_write_output_number(ptr {state.runtime_param}, ptr {output_handle}, double {numeric_value})"
                )
        state.instructions.append(
            f"  call void @qk_write_output_record_separator(ptr {state.runtime_param}, ptr {output_handle})"
        )
        return

    if not arguments:
        field_ptr = state.next_temp("print.field0")
        state.instructions.extend(
            [
                f"  {field_ptr} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 0)",
                f"  call void @qk_print_string(ptr {state.runtime_param}, ptr {field_ptr})",
            ]
        )
        return

    for index, argument in enumerate(arguments):
        if index > 0:
            state.instructions.append(f"  call void @qk_print_output_separator(ptr {state.runtime_param})")
        lower_runtime_print_fragment(argument, state)
    state.instructions.append(f"  call void @qk_print_output_record_separator(ptr {state.runtime_param})")


def lower_runtime_printf_statement(statement: PrintfStmt, state: LoweringState) -> None:
    """Lower one runtime-backed `printf` statement."""
    arguments = statement.arguments
    if not arguments:
        raise RuntimeError("printf requires at least a format string")
    format_expression = arguments[0]
    if isinstance(format_expression, StringLiteralExpr):
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
            if specifier in {"c", "d", "i", "o", "u", "x", "X"}:
                integer_value = state.next_temp("printf.int")
                numeric_value = lower_runtime_numeric_expression(argument, state)
                state.instructions.append(f"  {integer_value} = fptosi double {numeric_value} to i32")
                operands.append(f"i32 {integer_value}")
                continue
            operands.append(f"double {lower_runtime_numeric_expression(argument, state)}")

        redirect = statement.redirect
        state.instructions.append(emit_gep(format_ptr, format_length, format_name))
        if redirect is None:
            call_args = ", ".join([f"ptr {format_ptr}", *operands])
            state.instructions.append(f"  call i32 (ptr, ...) @printf({call_args})")
            return

        target_ptr = lower_runtime_output_target(redirect, state)
        output_handle = state.next_temp("printf.output")
        call_args = ", ".join([f"ptr {output_handle}", f"ptr {format_ptr}", *operands])
        state.instructions.extend(
            [
                f"  {output_handle} = call ptr @qk_open_output(ptr {state.runtime_param}, ptr {target_ptr}, i32 {output_redirect_mode_value(redirect.kind)})",
                f"  call i32 (ptr, ptr, ...) @fprintf({call_args})",
            ]
        )
        return

    format_ptr = lower_runtime_captured_string_expression(format_expression, state)
    arg_count = len(arguments) - 1
    if arg_count == 0:
        result = state.next_temp("printf")
        state.instructions.append(
            f"  {result} = call ptr @qk_sprintf(ptr {state.runtime_param}, ptr {format_ptr}, i32 0, ptr null, ptr null)"
        )
    else:
        numbers_slot = state.next_temp("printf.numbers")
        strings_slot = state.next_temp("printf.strings")
        state.allocas.append(f"  {numbers_slot} = alloca [{arg_count} x double]")
        state.allocas.append(f"  {strings_slot} = alloca [{arg_count} x ptr]")
        for index, argument in enumerate(arguments[1:]):
            number_ptr = state.next_temp("printf.number.ptr")
            string_ptr = state.next_temp("printf.string.ptr")
            string_value = lower_runtime_captured_string_expression(argument, state)
            try:
                numeric_value = lower_runtime_numeric_expression(argument, state)
            except RuntimeError:
                if not runtime_expression_has_string_result(argument, state):
                    raise
                numeric_value = state.next_temp("printf.num.coerce")
                state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
            state.instructions.extend(
                [
                    f"  {number_ptr} = getelementptr inbounds [{arg_count} x double], ptr {numbers_slot}, i32 0, i32 {index}",
                    f"  store double {numeric_value}, ptr {number_ptr}",
                    f"  {string_ptr} = getelementptr inbounds [{arg_count} x ptr], ptr {strings_slot}, i32 0, i32 {index}",
                    f"  store ptr {string_value}, ptr {string_ptr}",
                ]
            )
        result = state.next_temp("printf")
        state.instructions.append(
            f"  {result} = call ptr @qk_sprintf(ptr {state.runtime_param}, ptr {format_ptr}, i32 {arg_count}, ptr {numbers_slot}, ptr {strings_slot})"
        )

    redirect = statement.redirect
    if redirect is None:
        state.instructions.append(f"  call void @qk_print_string_fragment(ptr {state.runtime_param}, ptr {result})")
        return

    target_ptr = lower_runtime_output_target(redirect, state)
    output_handle = state.next_temp("printf.output")
    state.instructions.extend(
        [
            f"  {output_handle} = call ptr @qk_open_output(ptr {state.runtime_param}, ptr {target_ptr}, i32 {output_redirect_mode_value(redirect.kind)})",
            f"  call void @qk_write_output_string(ptr {output_handle}, ptr {result})",
        ]
    )


def lower_runtime_side_effect_expression(expression: Expr, state: LoweringState) -> None:
    """Lower one expression statement for the runtime-backed backend subset."""
    if runtime_expression_has_string_result(expression, state):
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

    if isinstance(expression, StringLiteralExpr):
        return format_double_literal(awk_numeric_prefix(expression.value))

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
        if expression.op is BinaryOp.SUB:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("sub")
            state.instructions.append(f"  {temp} = fsub double {left_operand}, {right_operand}")
            return temp
        if expression.op is BinaryOp.MUL:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("mul")
            state.instructions.append(f"  {temp} = fmul double {left_operand}, {right_operand}")
            return temp
        if expression.op is BinaryOp.DIV:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("div")
            state.instructions.append(f"  {temp} = fdiv double {left_operand}, {right_operand}")
            return temp
        if expression.op is BinaryOp.MOD:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            quotient = state.next_temp("mod.div")
            truncated = state.next_temp("mod.trunc")
            product = state.next_temp("mod.mul")
            remainder = state.next_temp("mod")
            state.instructions.extend(
                [
                    f"  {quotient} = fdiv double {left_operand}, {right_operand}",
                    f"  {truncated} = call double @llvm.trunc.f64(double {quotient})",
                    f"  {product} = fmul double {truncated}, {right_operand}",
                    f"  {remainder} = fsub double {left_operand}, {product}",
                ]
            )
            return remainder
        if expression.op is BinaryOp.POW:
            left_operand = lower_numeric_expression(expression.left, state)
            right_operand = lower_numeric_expression(expression.right, state)
            temp = state.next_temp("pow")
            state.instructions.append(f"  {temp} = call double @llvm.pow.f64(double {left_operand}, double {right_operand})")
            return temp
        if expression.op in {
            BinaryOp.LESS,
            BinaryOp.LESS_EQUAL,
            BinaryOp.GREATER,
            BinaryOp.GREATER_EQUAL,
            BinaryOp.EQUAL,
            BinaryOp.NOT_EQUAL,
            BinaryOp.LOGICAL_AND,
            BinaryOp.LOGICAL_OR,
        }:
            condition_value = lower_condition_expression(expression, state)
            temp = state.next_temp("boolnum")
            state.instructions.append(f"  {temp} = uitofp i1 {condition_value} to double")
            return temp
        raise RuntimeError(f"unsupported binary operator in numeric expression: {expression.op.name}")

    if isinstance(expression, ConditionalExpr):
        test_value = lower_condition_expression(expression.test, state)
        true_operand = lower_numeric_expression(expression.if_true, state)
        false_operand = lower_numeric_expression(expression.if_false, state)
        select_value = state.next_temp("ternary.num")
        state.instructions.append(f"  {select_value} = select i1 {test_value}, double {true_operand}, double {false_operand}")
        return select_value

    raise RuntimeError(
        "the current backend only supports numeric literals, variable reads, and the current arithmetic/boolean subset"
    )


def lower_runtime_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower one numeric expression in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    match expression:
        case NumericLiteralExpr(value=value):
            return format_double_literal(value)
        case StringLiteralExpr(value=value):
            return format_double_literal(awk_numeric_prefix(value))
        case NameExpr(name="NR"):
            temp = state.next_temp("nr")
            state.instructions.append(f"  {temp} = call double @qk_get_nr_inline(ptr {state.runtime_param})")
            return temp
        case NameExpr(name="FNR"):
            temp = state.next_temp("fnr")
            state.instructions.append(f"  {temp} = call double @qk_get_fnr_inline(ptr {state.runtime_param})")
            return temp
        case NameExpr(name="NF"):
            temp = state.next_temp("nf")
            state.instructions.append(f"  {temp} = call double @qk_get_nf_inline(ptr {state.runtime_param})")
            return temp
        case NameExpr(name=name):
            if name in state.function_param_strings:
                temp = state.next_temp("param.num")
                state.instructions.append(
                    f"  {temp} = call double @qk_parse_number_text(ptr {state.function_param_strings[name]})"
                )
                return temp
            if is_reusable_runtime_state_name(name):
                slot_name = variable_address(name, state)
                temp = state.next_temp("load")
                state.instructions.append(f"  {temp} = load double, ptr {slot_name}")
                return temp
            if runtime_name_uses_numeric_slot_state(name, state):
                slot_name = variable_address(name, state)
                temp = state.next_temp("slot.num")
                state.instructions.append(f"  {temp} = load double, ptr {slot_name}")
                return temp
            slot_index = runtime_name_slot_index(name, state)
            if runtime_name_uses_string_slot_runtime(name, state):
                assert slot_index is not None
                temp = state.next_temp("slot.num")
                state.instructions.append(
                    f"  {temp} = call double @qk_slot_get_number(ptr {state.runtime_param}, i64 {slot_index})"
                )
                return temp
            scalar_name = lower_runtime_scalar_name(name, state)
            temp = state.next_temp("scalar.num")
            state.instructions.append(
                f"  {temp} = call double @qk_scalar_get_number_inline(ptr {state.runtime_param}, ptr {scalar_name})"
            )
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
        case UnaryExpr(op=UnaryOp.PRE_INC, operand=operand):
            return lower_runtime_increment_expression(operand, 1.0, return_old=False, state=state)
        case UnaryExpr(op=UnaryOp.PRE_DEC, operand=operand):
            return lower_runtime_increment_expression(operand, -1.0, return_old=False, state=state)
        case PostfixExpr(op=PostfixOp.POST_INC, operand=operand):
            return lower_runtime_increment_expression(operand, 1.0, return_old=True, state=state)
        case PostfixExpr(op=PostfixOp.POST_DEC, operand=operand):
            return lower_runtime_increment_expression(operand, -1.0, return_old=True, state=state)
        case CallExpr(function="split"):
            return lower_runtime_split_builtin(expression, state)
        case CallExpr(function="close"):
            return lower_runtime_close_builtin(expression, state)
        case CallExpr(function="gsub"):
            return lower_runtime_substitute_builtin(expression, state, global_replace=True)
        case CallExpr(function="index"):
            return lower_runtime_index_builtin(expression, state)
        case CallExpr(function="int"):
            return lower_runtime_unary_numeric_builtin(expression, state, "@qk_int_builtin", "int")
        case CallExpr(function="length"):
            return lower_runtime_length_builtin(expression, state)
        case CallExpr(function="log"):
            return lower_runtime_unary_numeric_builtin(expression, state, "@qk_log", "log")
        case CallExpr(function="match"):
            return lower_runtime_match_builtin(expression, state)
        case CallExpr(function="rand"):
            return lower_runtime_rand_builtin(expression, state)
        case CallExpr(function="sin"):
            return lower_runtime_unary_numeric_builtin(expression, state, "@qk_sin", "sin")
        case CallExpr(function="sqrt"):
            return lower_runtime_unary_numeric_builtin(expression, state, "@qk_sqrt", "sqrt")
        case CallExpr(function="srand"):
            return lower_runtime_srand_builtin(expression, state)
        case CallExpr(function="sub"):
            return lower_runtime_substitute_builtin(expression, state, global_replace=False)
        case CallExpr(function="system"):
            return lower_runtime_system_builtin(expression, state)
        case CallExpr(function=function_name, args=args) if function_name in state.function_defs:
            string_value = lower_runtime_user_function_call(function_name, args, state)
            temp = state.next_temp("fncall.num")
            state.instructions.append(f"  {temp} = call double @qk_parse_number_text(ptr {string_value})")
            return temp
        case CallExpr(function="atan2"):
            return lower_runtime_binary_numeric_builtin(expression, state, "@qk_atan2", "atan2")
        case CallExpr(function="cos"):
            return lower_runtime_unary_numeric_builtin(expression, state, "@qk_cos", "cos")
        case CallExpr(function="exp"):
            return lower_runtime_unary_numeric_builtin(expression, state, "@qk_exp", "exp")
        case GetlineExpr():
            return lower_runtime_getline_expression(expression, state)
        case BinaryExpr(op=BinaryOp.ADD, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            temp = state.next_temp("add")
            state.instructions.append(f"  {temp} = fadd double {left_operand}, {right_operand}")
            return temp
        case BinaryExpr(op=BinaryOp.SUB, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            temp = state.next_temp("sub")
            state.instructions.append(f"  {temp} = fsub double {left_operand}, {right_operand}")
            return temp
        case BinaryExpr(op=BinaryOp.MUL, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            temp = state.next_temp("mul")
            state.instructions.append(f"  {temp} = fmul double {left_operand}, {right_operand}")
            return temp
        case BinaryExpr(op=BinaryOp.DIV, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            temp = state.next_temp("div")
            state.instructions.append(f"  {temp} = fdiv double {left_operand}, {right_operand}")
            return temp
        case BinaryExpr(op=BinaryOp.MOD, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            quotient = state.next_temp("mod.div")
            truncated = state.next_temp("mod.trunc")
            product = state.next_temp("mod.mul")
            remainder = state.next_temp("mod")
            state.instructions.extend(
                [
                    f"  {quotient} = fdiv double {left_operand}, {right_operand}",
                    f"  {truncated} = call double @llvm.trunc.f64(double {quotient})",
                    f"  {product} = fmul double {truncated}, {right_operand}",
                    f"  {remainder} = fsub double {left_operand}, {product}",
                ]
            )
            return remainder
        case BinaryExpr(op=BinaryOp.POW, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            temp = state.next_temp("pow")
            state.instructions.append(f"  {temp} = call double @llvm.pow.f64(double {left_operand}, double {right_operand})")
            return temp
        case BinaryExpr(
            op=BinaryOp.LESS
            | BinaryOp.LESS_EQUAL
            | BinaryOp.GREATER
            | BinaryOp.GREATER_EQUAL
            | BinaryOp.EQUAL
            | BinaryOp.NOT_EQUAL
            | BinaryOp.LOGICAL_AND
            | BinaryOp.LOGICAL_OR
            | BinaryOp.MATCH
            | BinaryOp.NOT_MATCH
            | BinaryOp.IN
        ):
            condition_value = lower_condition_expression(expression, state)
            temp = state.next_temp("boolnum")
            state.instructions.append(f"  {temp} = uitofp i1 {condition_value} to double")
            return temp
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            if runtime_expression_has_side_effects(if_true, state) or runtime_expression_has_side_effects(if_false, state):
                return lower_runtime_numeric_conditional_expression(expression, state)
            test_value = lower_condition_expression(test, state)
            true_operand = lower_runtime_numeric_expression(if_true, state)
            false_operand = lower_runtime_numeric_expression(if_false, state)
            select_value = state.next_temp("ternary.num")
            state.instructions.append(
                f"  {select_value} = select i1 {test_value}, double {true_operand}, double {false_operand}"
            )
            return select_value
        case _:
            if runtime_expression_has_string_result(expression, state):
                string_value = lower_runtime_captured_string_expression(expression, state)
                temp = state.next_temp("num.coerce")
                state.instructions.append(f"  {temp} = call double @qk_parse_number_text(ptr {string_value})")
                return temp
            raise RuntimeError("unsupported numeric expression in runtime-backed backend")


def lower_runtime_assignment_expression(expression: AssignExpr, state: LoweringState) -> str:
    """Lower one numeric assignment expression in the runtime-backed backend subset."""
    if expression.op is not AssignOp.PLAIN:
        raise RuntimeError("compound assignment expressions are not supported by the runtime-backed backend")

    target = expression.target
    match target:
        case FieldLValue(index=index):
            index_value = lower_runtime_field_index(index, state)
            assert state.runtime_param is not None
            if runtime_assignment_preserves_string(expression.value, state):
                raise RuntimeError("string-valued field assignment expressions are not supported yet in runtime-backed backend")
            numeric_value = lower_runtime_numeric_expression(expression.value, state)
            state.instructions.append(
                f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {index_value}, double {numeric_value})"
            )
        case ArrayLValue(name=name, subscripts=subscripts):
            assert state.runtime_param is not None
            array_name_ptr = lower_runtime_constant_string(name, state)
            key_ptr = lower_runtime_array_subscripts(subscripts, state)
            if runtime_assignment_preserves_string(expression.value, state):
                raise RuntimeError("string-valued array assignment expressions are not supported yet in runtime-backed backend")
            numeric_value = lower_runtime_numeric_expression(expression.value, state)
            state.instructions.append(
                f"  call void @qk_array_set_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {numeric_value})"
            )
        case NameLValue(name=name):
            if is_reusable_runtime_state_name(name):
                numeric_value = lower_runtime_numeric_expression(expression.value, state)
                slot_name = variable_address(name, state)
                state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
            elif runtime_name_uses_numeric_slot_state(name, state):
                numeric_value = lower_runtime_numeric_expression(expression.value, state)
                slot_name = variable_address(name, state)
                state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
            else:
                slot_index = runtime_name_slot_index(name, state)
                scalar_name = lower_runtime_scalar_name(name, state)
                if (
                    isinstance(expression.value, NameExpr)
                    and runtime_name_uses_scalar_runtime(expression.value.name, state)
                    and not runtime_name_uses_string_slot_runtime(name, state)
                ):
                    source_name = lower_runtime_scalar_name(expression.value.name, state)
                    state.instructions.append(
                        f"  call void @qk_scalar_copy(ptr {state.runtime_param}, ptr {scalar_name}, ptr {source_name})"
                    )
                    source_slot_index = runtime_name_slot_index(expression.value.name, state)
                    if slot_index is not None and source_slot_index is not None:
                        numeric_value = state.next_temp("assign.copy.slot")
                        state.instructions.append(
                            (
                                f"  {numeric_value} = call double @qk_slot_get_number("
                                f"ptr {state.runtime_param}, i64 {source_slot_index})"
                            )
                        )
                        state.instructions.append(
                            (
                                f"  call void @qk_slot_set_number(ptr {state.runtime_param}, "
                                f"i64 {slot_index}, double {numeric_value})"
                            )
                        )
                    else:
                        numeric_value = state.next_temp("assign.copy.num")
                        state.instructions.append(
                            (
                                f"  {numeric_value} = call double @qk_scalar_get_number_inline("
                                f"ptr {state.runtime_param}, ptr {scalar_name})"
                            )
                        )
                elif runtime_assignment_preserves_string(expression.value, state):
                    string_value = lower_runtime_string_expression(expression.value, state)
                    if runtime_name_uses_string_slot_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                        )
                        numeric_value = state.next_temp("assign.str.num")
                        state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
                        state.instructions.append(
                            f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
                        )
                    else:
                        state.instructions.append(
                            f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {scalar_name}, ptr {string_value})"
                        )
                        if slot_index is not None:
                            numeric_value = state.next_temp("assign.str.slot")
                            state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
                            state.instructions.append(
                                (
                                    f"  call void @qk_slot_set_number(ptr {state.runtime_param}, "
                                    f"i64 {slot_index}, double {numeric_value})"
                                )
                            )
                        else:
                            numeric_value = state.next_temp("assign.str.num")
                            state.instructions.append(
                                (
                                    f"  {numeric_value} = call double @qk_scalar_get_number_inline("
                                    f"ptr {state.runtime_param}, ptr {scalar_name})"
                                )
                            )
                else:
                    numeric_value = lower_runtime_numeric_expression(expression.value, state)
                    if runtime_name_uses_string_slot_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            (
                                f"  call void @qk_slot_set_number(ptr {state.runtime_param}, "
                                f"i64 {slot_index}, double {numeric_value})"
                            )
                        )
                    state.instructions.append(
                        f"  call void @qk_scalar_set_number_inline(ptr {state.runtime_param}, ptr {scalar_name}, double {numeric_value})"
                    )
        case _:
            raise RuntimeError("unsupported assignment expression in the runtime-backed backend")
    return numeric_value


def lower_runtime_increment_expression(operand: Expr, delta: float, *, return_old: bool, state: LoweringState) -> str:
    """Lower one runtime-backed pre/post increment or decrement expression."""
    opcode = "fadd" if delta >= 0 else "fsub"
    amount = format_double_literal(abs(delta))

    match operand:
        case NameExpr(name=name):
            if is_reusable_runtime_state_name(name):
                slot_name = variable_address(name, state)
                old_value = state.next_temp("inc.old")
                new_value = state.next_temp("inc.new")
                state.instructions.append(f"  {old_value} = load double, ptr {slot_name}")
                state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
                state.instructions.append(f"  store double {new_value}, ptr {slot_name}")
                return old_value if return_old else new_value
            if runtime_name_uses_numeric_slot_state(name, state):
                slot_name = variable_address(name, state)
                old_value = state.next_temp("inc.old")
                new_value = state.next_temp("inc.new")
                state.instructions.append(f"  {old_value} = load double, ptr {slot_name}")
                state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
                state.instructions.append(f"  store double {new_value}, ptr {slot_name}")
                return old_value if return_old else new_value

            slot_index = runtime_name_slot_index(name, state)
            scalar_name = lower_runtime_scalar_name(name, state)
            old_value = state.next_temp("inc.old")
            new_value = state.next_temp("inc.new")
            if runtime_name_uses_string_slot_runtime(name, state):
                assert slot_index is not None
                state.instructions.append(
                    f"  {old_value} = call double @qk_slot_get_number(ptr {state.runtime_param}, i64 {slot_index})"
                )
            else:
                state.instructions.append(
                    f"  {old_value} = call double @qk_scalar_get_number_inline(ptr {state.runtime_param}, ptr {scalar_name})"
                )
            state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
            if runtime_name_uses_string_slot_runtime(name, state):
                assert slot_index is not None
                state.instructions.append(
                    f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {new_value})"
                )
            state.instructions.append(
                f"  call void @qk_scalar_set_number_inline(ptr {state.runtime_param}, ptr {scalar_name}, double {new_value})"
            )
            return old_value if return_old else new_value
        case FieldExpr(index=index):
            field_index = lower_runtime_field_index(index, state)
            field_ptr = state.next_temp("inc.field.ptr")
            old_value = state.next_temp("inc.old")
            new_value = state.next_temp("inc.new")
            state.instructions.append(f"  {field_ptr} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 {field_index})")
            state.instructions.append(f"  {old_value} = call double @qk_parse_number_text(ptr {field_ptr})")
            state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
            state.instructions.append(
                f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {field_index}, double {new_value})"
            )
            return old_value if return_old else new_value
        case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
            array_name_ptr = lower_runtime_constant_string(array_name, state)
            key_ptr = lower_runtime_array_subscripts((index, *extra_indexes), state)
            entry_ptr = state.next_temp("inc.array.ptr")
            old_value = state.next_temp("inc.old")
            new_value = state.next_temp("inc.new")
            state.instructions.append(
                f"  {entry_ptr} = call ptr @qk_array_get(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
            )
            state.instructions.append(f"  {old_value} = call double @qk_parse_number_text(ptr {entry_ptr})")
            state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
            state.instructions.append(
                f"  call void @qk_array_set_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {new_value})"
            )
            return old_value if return_old else new_value
        case _:
            raise RuntimeError("unsupported increment expression in runtime-backed backend")


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
        case NameExpr(name=name) if name in state.function_param_strings:
            return state.function_param_strings[name]
        case NameExpr(name="FILENAME"):
            temp = state.next_temp("filename")
            state.instructions.append(f"  {temp} = call ptr @qk_get_filename_inline(ptr {state.runtime_param})")
            return temp
        case NameExpr(name=name):
            if runtime_name_uses_string_slot_runtime(name, state):
                slot_index = runtime_name_slot_index(name, state)
                assert slot_index is not None
                temp = state.next_temp("slot.str")
                state.instructions.append(
                    f"  {temp} = call ptr @qk_slot_get_string(ptr {state.runtime_param}, i64 {slot_index})"
                )
                return temp
            if runtime_name_uses_only_scalar_runtime(name, state):
                scalar_name = lower_runtime_scalar_name(name, state)
                temp = state.next_temp("scalar.str")
                state.instructions.append(
                    f"  {temp} = call ptr @qk_scalar_get_inline(ptr {state.runtime_param}, ptr {scalar_name})"
                )
                return temp
            numeric_value = lower_runtime_numeric_expression(expression, state)
            temp = state.next_temp("numstr")
            state.instructions.append(
                f"  {temp} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})"
            )
            return temp
        case FieldExpr(index=index):
            field_index = lower_runtime_field_index(index, state)
            temp = state.next_temp("field")
            state.instructions.append(
                f"  {temp} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 {field_index})"
            )
            return temp
        case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
            array_name_ptr = lower_runtime_constant_string(array_name, state)
            key_ptr = lower_runtime_array_subscripts((index, *extra_indexes), state)
            temp = state.next_temp("array.get")
            state.instructions.append(
                f"  {temp} = call ptr @qk_array_get(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
            )
            return temp
        case AssignExpr(op=AssignOp.PLAIN, target=target, value=value):
            match target:
                case FieldLValue(index=index) if runtime_assignment_preserves_string(value, state):
                    field_index = lower_runtime_field_index(index, state)
                    string_value = lower_runtime_string_expression(value, state)
                    state.instructions.append(
                        f"  call void @qk_set_field_string(ptr {state.runtime_param}, i64 {field_index}, ptr {string_value})"
                    )
                    return string_value
                case ArrayLValue(name=name, subscripts=subscripts) if runtime_assignment_preserves_string(value, state):
                    array_name_ptr = lower_runtime_constant_string(name, state)
                    key_ptr = lower_runtime_array_subscripts(subscripts, state)
                    string_value = lower_runtime_string_expression(value, state)
                    state.instructions.append(
                        f"  call void @qk_array_set_string(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, ptr {string_value})"
                    )
                    return string_value
                case NameLValue(name=name) if runtime_assignment_preserves_string(value, state):
                    if is_reusable_runtime_state_name(name):
                        raise RuntimeError(
                            "string-valued assignment expressions are not supported for reusable numeric state"
                        )
                    slot_index = runtime_name_slot_index(name, state)
                    string_value = lower_runtime_string_expression(value, state)
                    if runtime_name_uses_string_slot_runtime(name, state):
                        assert slot_index is not None
                        numeric_value = state.next_temp("assign.str.slot")
                        state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
                        state.instructions.append(
                            f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                        )
                        state.instructions.append(
                            f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
                        )
                        stored_value = state.next_temp("assign.str")
                        state.instructions.append(
                            f"  {stored_value} = call ptr @qk_slot_get_string(ptr {state.runtime_param}, i64 {slot_index})"
                        )
                        return stored_value
                    scalar_name = lower_runtime_scalar_name(name, state)
                    state.instructions.append(
                        f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {scalar_name}, ptr {string_value})"
                    )
                    if slot_index is not None:
                        numeric_value = state.next_temp("assign.str.slot")
                        state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
                        state.instructions.append(
                            (
                                f"  call void @qk_slot_set_number(ptr {state.runtime_param}, "
                                f"i64 {slot_index}, double {numeric_value})"
                            )
                        )
                    stored_value = state.next_temp("assign.str")
                    state.instructions.append(
                        f"  {stored_value} = call ptr @qk_scalar_get_inline(ptr {state.runtime_param}, ptr {scalar_name})"
                    )
                    return stored_value
        case CallExpr(function="substr"):
            return lower_runtime_substr_builtin(expression, state)
        case CallExpr(function="sprintf"):
            return lower_runtime_sprintf_builtin(expression, state)
        case CallExpr(function="length"):
            numeric_value = lower_runtime_numeric_expression(expression, state)
            temp = state.next_temp("numstr")
            state.instructions.append(
                f"  {temp} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})"
            )
            return temp
        case CallExpr(function=function_name, args=args) if function_name in state.function_defs:
            return lower_runtime_user_function_call(function_name, args, state)
        case CallExpr(function="tolower"):
            return lower_runtime_case_builtin(expression, state, upper=False)
        case CallExpr(function="toupper"):
            return lower_runtime_case_builtin(expression, state, upper=True)
        case BinaryExpr(op=BinaryOp.CONCAT, left=left, right=right):
            if (
                runtime_expression_is_known_string(left, state)
                and runtime_expression_is_known_string(right, state)
                and not isinstance(left, BinaryExpr)
                and not isinstance(right, BinaryExpr)
            ):
                left_value = lower_runtime_string_expression(left, state)
                right_value = lower_runtime_string_expression(right, state)
            else:
                left_value = lower_runtime_captured_string_expression(left, state)
                right_value = lower_runtime_captured_string_expression(right, state)
            temp = state.next_temp("concat")
            state.instructions.append(
                f"  {temp} = call ptr @qk_concat(ptr {state.runtime_param}, ptr {left_value}, ptr {right_value})"
            )
            return temp
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            return lower_runtime_string_conditional_expression(expression, state)
        case _:
            numeric_value = lower_runtime_numeric_expression(expression, state)
            temp = state.next_temp("numstr")
            state.instructions.append(f"  {temp} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})")
    return temp


def lower_runtime_unary_numeric_builtin(
    expression: CallExpr,
    state: LoweringState,
    runtime_function: str,
    builtin_name: str,
) -> str:
    """Lower one one-argument numeric builtin in the runtime-backed backend subset."""
    if len(expression.args) != 1:
        raise RuntimeError(f"builtin {builtin_name} expects one argument")
    operand = lower_runtime_numeric_expression(expression.args[0], state)
    result = state.next_temp(f"{builtin_name}.num")
    state.instructions.append(f"  {result} = call double {runtime_function}(double {operand})")
    return result


def lower_runtime_binary_numeric_builtin(
    expression: CallExpr,
    state: LoweringState,
    runtime_function: str,
    builtin_name: str,
) -> str:
    """Lower one two-argument numeric builtin in the runtime-backed backend subset."""
    if len(expression.args) != 2:
        raise RuntimeError(f"builtin {builtin_name} expects two arguments")
    left = lower_runtime_numeric_expression(expression.args[0], state)
    right = lower_runtime_numeric_expression(expression.args[1], state)
    result = state.next_temp(f"{builtin_name}.num")
    state.instructions.append(f"  {result} = call double {runtime_function}(double {left}, double {right})")
    return result


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
                f"  {field_ptr} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 0)",
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


def lower_runtime_close_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `close` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) != 1:
        raise RuntimeError("builtin close expects one argument")
    target_ptr = lower_runtime_string_expression(expression.args[0], state)
    result = state.next_temp("close")
    state.instructions.append(f"  {result} = call double @qk_close_output(ptr {state.runtime_param}, ptr {target_ptr})")
    return result


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


def lower_runtime_captured_string_expression(expression: Expr, state: LoweringState) -> str:
    """Lower one string expression and capture a stable copy for multi-arg runtime calls."""
    assert state.runtime_param is not None
    string_value = lower_runtime_string_expression(expression, state)
    captured = state.next_temp("str.capture")
    state.instructions.append(f"  {captured} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {string_value})")
    return captured


def lower_runtime_regex_pattern(expression: Expr, state: LoweringState) -> str:
    """Lower one regex-oriented builtin pattern argument to a runtime string pointer."""
    if isinstance(expression, RegexLiteralExpr):
        return lower_runtime_constant_string(decode_regex_literal(expression.raw_text), state)
    return lower_runtime_captured_string_expression(expression, state)


def lower_runtime_match_operator(expression: BinaryExpr, state: LoweringState) -> str:
    """Lower one `~` / `!~` expression to an `i1` match result."""
    assert state.runtime_param is not None
    left_ptr = lower_runtime_captured_string_expression(expression.left, state)
    pattern_ptr = lower_runtime_regex_pattern(expression.right, state)
    match_result = state.next_temp("match")
    state.instructions.append(f"  {match_result} = call i1 @qk_regex_match_text(ptr {left_ptr}, ptr {pattern_ptr})")
    if expression.op is BinaryOp.MATCH:
        return match_result
    inverted = state.next_temp("notmatch")
    state.instructions.append(f"  {inverted} = xor i1 {match_result}, true")
    return inverted


def lower_runtime_in_expression(expression: BinaryExpr, state: LoweringState) -> str:
    """Lower one `expr in array` membership expression to an `i1` result."""
    assert state.runtime_param is not None
    if not isinstance(expression.right, NameExpr):
        raise RuntimeError("the runtime-backed backend only supports `in` against a named array")
    array_name_ptr = lower_runtime_constant_string(expression.right.name, state)
    key_ptr = lower_runtime_captured_string_expression(expression.left, state)
    contains_result = state.next_temp("contains")
    state.instructions.append(
        f"  {contains_result} = call i1 @qk_array_contains(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
    )
    return contains_result


def lower_runtime_index_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `index` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) != 2:
        raise RuntimeError("builtin index expects two arguments")
    text_ptr = lower_runtime_captured_string_expression(expression.args[0], state)
    search_ptr = lower_runtime_captured_string_expression(expression.args[1], state)
    result = state.next_temp("index")
    state.instructions.append(f"  {result} = call double @qk_index(ptr {state.runtime_param}, ptr {text_ptr}, ptr {search_ptr})")
    return result


def lower_runtime_match_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `match` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) != 2:
        raise RuntimeError("builtin match expects two arguments")
    text_ptr = lower_runtime_captured_string_expression(expression.args[0], state)
    pattern_ptr = lower_runtime_regex_pattern(expression.args[1], state)
    result = state.next_temp("match")
    state.instructions.append(f"  {result} = call double @qk_match(ptr {state.runtime_param}, ptr {text_ptr}, ptr {pattern_ptr})")
    return result


def lower_runtime_rand_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `rand` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if expression.args:
        raise RuntimeError("builtin rand expects zero arguments")
    result = state.next_temp("rand")
    state.instructions.append(f"  {result} = call double @qk_rand(ptr {state.runtime_param})")
    return result


def lower_runtime_srand_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `srand` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) > 1:
        raise RuntimeError("builtin srand expects zero or one argument")
    result = state.next_temp("srand")
    if not expression.args:
        state.instructions.append(f"  {result} = call double @qk_srand0(ptr {state.runtime_param})")
        return result
    seed = lower_runtime_numeric_expression(expression.args[0], state)
    state.instructions.append(f"  {result} = call double @qk_srand1(ptr {state.runtime_param}, double {seed})")
    return result


def lower_runtime_system_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `system` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) != 1:
        raise RuntimeError("builtin system expects one argument")
    command = lower_runtime_captured_string_expression(expression.args[0], state)
    result = state.next_temp("system")
    state.instructions.append(f"  {result} = call double @qk_system(ptr {state.runtime_param}, ptr {command})")
    return result


def lower_runtime_getline_expression(expression: GetlineExpr, state: LoweringState) -> str:
    """Lower one currently claimed `getline` expression in the runtime-backed backend."""
    assert state.runtime_param is not None
    if expression.source is None and expression.target is None:
        result = state.next_temp("getline")
        state.instructions.append(f"  {result} = call double @qk_getline_main_record(ptr {state.runtime_param})")
        return result
    if expression.source is not None and expression.target is None:
        source_ptr = lower_runtime_captured_string_expression(expression.source, state)
        result = state.next_temp("getline")
        state.instructions.append(
            f"  {result} = call double @qk_getline_file_record(ptr {state.runtime_param}, ptr {source_ptr})"
        )
        return result

    result_slot = state.next_temp("getline.result.slot")
    state.allocas.append(f"  {result_slot} = alloca ptr")
    if expression.source is None:
        result = state.next_temp("getline")
        state.instructions.append(f"  {result} = call double @qk_getline_main_string(ptr {state.runtime_param}, ptr {result_slot})")
    else:
        source_ptr = lower_runtime_captured_string_expression(expression.source, state)
        result = state.next_temp("getline")
        state.instructions.append(
            f"  {result} = call double @qk_getline_file_string(ptr {state.runtime_param}, ptr {source_ptr}, ptr {result_slot})"
        )
    assign_condition = state.next_temp("getline.assign")
    assign_label = state.next_label("getline.assign.block")
    done_label = state.next_label("getline.done")
    state.instructions.append(
        f"  {assign_condition} = fcmp ogt double {result}, 0.000000000000000e+00"
    )
    state.instructions.append(f"  br i1 {assign_condition}, label %{assign_label}, label %{done_label}")
    state.instructions.append(f"{assign_label}:")
    result_ptr = state.next_temp("getline.result.ptr")
    state.instructions.append(f"  {result_ptr} = load ptr, ptr {result_slot}")
    lower_runtime_assign_string_lvalue(expression.target, result_ptr, state)
    state.instructions.append(f"  br label %{done_label}")
    state.instructions.append(f"{done_label}:")
    return result


def lower_runtime_assign_string_lvalue(target: NameLValue | ArrayLValue | FieldLValue, string_value: str, state: LoweringState) -> None:
    """Assign one runtime string result back through a supported lvalue."""
    assert state.runtime_param is not None
    match target:
        case NameLValue(name=name):
            slot_index = runtime_name_slot_index(name, state)
            if runtime_name_uses_string_slot_runtime(name, state):
                assert slot_index is not None
                numeric_value = state.next_temp("assign.str.slot")
                state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
                state.instructions.append(
                    f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                )
                state.instructions.append(
                    f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
                )
            else:
                scalar_name = lower_runtime_scalar_name(name, state)
                state.instructions.append(
                    f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {scalar_name}, ptr {string_value})"
                )
        case FieldLValue(index=index):
            index_value = lower_runtime_field_index(index, state)
            state.instructions.append(
                f"  call void @qk_set_field_string(ptr {state.runtime_param}, i64 {index_value}, ptr {string_value})"
            )
        case ArrayLValue(name=name, subscripts=(subscript,)):
            array_name_ptr = lower_runtime_constant_string(name, state)
            key_ptr = lower_runtime_array_key(subscript, state)
            state.instructions.append(
                f"  call void @qk_array_set_string(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, ptr {string_value})"
            )
        case _:
            raise RuntimeError("unsupported string assignment target in the runtime-backed backend")


def lower_runtime_substitute_builtin(expression: CallExpr, state: LoweringState, *, global_replace: bool) -> str:
    """Lower one `sub` or `gsub` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    builtin_name = "gsub" if global_replace else "sub"
    if len(expression.args) not in {2, 3}:
        raise RuntimeError(f"builtin {builtin_name} expects two or three arguments")

    pattern_ptr = lower_runtime_regex_pattern(expression.args[0], state)
    if isinstance(expression.args[1], StringLiteralExpr):
        replacement_ptr = lower_runtime_string_expression(expression.args[1], state)
    else:
        replacement_ptr = lower_runtime_captured_string_expression(expression.args[1], state)
    target_expr: Expr = expression.args[2] if len(expression.args) == 3 else FieldExpr(index=0, span=expression.span)
    target_lvalue = expression_to_lvalue(target_expr)
    if target_lvalue is None:
        raise RuntimeError(f"builtin {builtin_name} requires an assignable third argument")

    if len(expression.args) == 2:
        target_value = state.next_temp("sub.field0")
        state.instructions.append(f"  {target_value} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 0)")
    else:
        match target_lvalue:
            case NameLValue(name=name):
                target_value = lower_runtime_captured_string_expression(NameExpr(name=name, span=target_expr.span), state)
            case FieldLValue() | ArrayLValue():
                target_value = lower_runtime_captured_string_expression(target_expr, state)
            case _:
                raise RuntimeError(f"builtin {builtin_name} requires an assignable third argument")

    result_slot = state.next_temp("sub.result.slot")
    result_ptr = state.next_temp("sub.result.ptr")
    count_value = state.next_temp("sub.count")
    state.allocas.append(f"  {result_slot} = alloca ptr")
    state.instructions.extend(
        [
            f"  {count_value} = call double @qk_substitute(ptr {state.runtime_param}, ptr {pattern_ptr}, ptr {replacement_ptr}, ptr {target_value}, i1 {'true' if global_replace else 'false'}, ptr {result_slot})",
            f"  {result_ptr} = load ptr, ptr {result_slot}",
        ]
    )
    lower_runtime_assign_string_lvalue(target_lvalue, result_ptr, state)
    return count_value


def lower_runtime_case_builtin(expression: CallExpr, state: LoweringState, *, upper: bool) -> str:
    """Lower one `tolower` or `toupper` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    builtin_name = "toupper" if upper else "tolower"
    if len(expression.args) != 1:
        raise RuntimeError(f"builtin {builtin_name} expects one argument")
    text_ptr = lower_runtime_captured_string_expression(expression.args[0], state)
    result = state.next_temp("case")
    runtime_function = "@qk_toupper" if upper else "@qk_tolower"
    state.instructions.append(f"  {result} = call ptr {runtime_function}(ptr {state.runtime_param}, ptr {text_ptr})")
    return result


def lower_runtime_sprintf_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `sprintf` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if not expression.args:
        raise RuntimeError("builtin sprintf expects at least a format argument")

    format_ptr = lower_runtime_captured_string_expression(expression.args[0], state)
    arg_count = len(expression.args) - 1
    if arg_count == 0:
        result = state.next_temp("sprintf")
        state.instructions.append(
            f"  {result} = call ptr @qk_sprintf(ptr {state.runtime_param}, ptr {format_ptr}, i32 0, ptr null, ptr null)"
        )
        return result

    numbers_slot = state.next_temp("sprintf.numbers")
    strings_slot = state.next_temp("sprintf.strings")
    state.allocas.append(f"  {numbers_slot} = alloca [{arg_count} x double]")
    state.allocas.append(f"  {strings_slot} = alloca [{arg_count} x ptr]")
    for index, argument in enumerate(expression.args[1:]):
        number_ptr = state.next_temp("sprintf.number.ptr")
        string_ptr = state.next_temp("sprintf.string.ptr")
        string_value = lower_runtime_captured_string_expression(argument, state)
        try:
            numeric_value = lower_runtime_numeric_expression(argument, state)
        except RuntimeError:
            if not runtime_expression_has_string_result(argument, state):
                raise
            numeric_value = state.next_temp("sprintf.num.coerce")
            state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})")
        state.instructions.extend(
            [
                f"  {number_ptr} = getelementptr inbounds [{arg_count} x double], ptr {numbers_slot}, i32 0, i32 {index}",
                f"  store double {numeric_value}, ptr {number_ptr}",
                f"  {string_ptr} = getelementptr inbounds [{arg_count} x ptr], ptr {strings_slot}, i32 0, i32 {index}",
                f"  store ptr {string_value}, ptr {string_ptr}",
            ]
        )

    result = state.next_temp("sprintf")
    state.instructions.append(
        f"  {result} = call ptr @qk_sprintf(ptr {state.runtime_param}, ptr {format_ptr}, i32 {arg_count}, ptr {numbers_slot}, ptr {strings_slot})"
    )
    return result


def lower_runtime_constant_string(value: str, state: LoweringState) -> str:
    """Lower one compile-time string constant to a runtime pointer."""
    global_name, byte_length = declare_string(state, value)
    string_ptr = state.next_temp("strptr")
    state.instructions.append(emit_gep(string_ptr, byte_length, global_name))
    return string_ptr


def lower_runtime_scalar_name(name: str, state: LoweringState) -> str:
    """Lower one scalar variable name to a runtime string pointer."""
    return lower_runtime_constant_string(name, state)


def lower_runtime_string_from_numeric_value(numeric_value: str, state: LoweringState) -> str:
    """Format one numeric runtime value as a captured string pointer."""
    formatted = state.next_temp("numstr")
    captured = state.next_temp("numstr.capture")
    state.instructions.append(f"  {formatted} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})")
    state.instructions.append(f"  {captured} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {formatted})")
    return captured


def lower_runtime_argument_string(expression: Expr, state: LoweringState) -> str:
    """Lower one runtime-backed call argument to a captured string pointer."""
    if runtime_expression_has_string_result(expression, state):
        return lower_runtime_captured_string_expression(expression, state)
    return lower_runtime_string_from_numeric_value(lower_runtime_numeric_expression(expression, state), state)


def lower_runtime_user_function_call(function_name: str, args: tuple[Expr, ...], state: LoweringState) -> str:
    """Lower one runtime-backed user-defined function call to a string result pointer."""
    function_def = state.function_defs.get(function_name)
    if function_def is None:
        raise RuntimeError(f"unsupported function call in runtime-backed backend: {function_name}")
    if len(args) != len(function_def.params):
        raise RuntimeError(f"function {function_name} expects {len(function_def.params)} arguments, got {len(args)}")
    call_args = [f"ptr {state.runtime_param}", f"ptr {state.state_param or 'null'}"]
    for argument in args:
        call_args.append(f"ptr {lower_runtime_argument_string(argument, state)}")
    result = state.next_temp("fncall")
    state.instructions.append(f"  {result} = call ptr @qk_fn_{function_name}({', '.join(call_args)})")
    return result


def runtime_name_slot_index(name: str, state: LoweringState) -> int | None:
    """Return the runtime numeric-slot index for one known scalar variable name."""
    if (
        is_builtin_variable_name(name)
        or name in state.loop_string_bindings
        or name in state.function_param_strings
        or is_reusable_runtime_state_name(name)
    ):
        return None
    if state.slot_allocation is not None:
        slot = state.slot_allocation.get_slot(name)
        if slot is None or slot.storage != "slot":
            return None
        return slot.index
    return state.variable_indexes.get(name)


def runtime_name_uses_scalar_runtime(name: str, state: LoweringState) -> bool:
    """Report whether one `NameExpr` should route through the runtime scalar ABI."""
    return (
        name not in {"NR", "FNR", "NF", "FILENAME"}
        and name not in state.loop_string_bindings
        and name not in state.function_param_strings
        and not is_reusable_runtime_state_name(name)
    )


def runtime_name_is_inferred_numeric(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name is inferred numeric in the current lowering state."""
    return state.type_info.get(name) is LatticeType.NUMERIC


def runtime_name_is_inferred_string(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name is inferred string in the current lowering state."""
    return state.type_info.get(name) is LatticeType.STRING


def runtime_name_uses_numeric_slot_state(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use direct `%quawk.state` numeric slot access."""
    return (
        state.state_param is not None
        and runtime_name_uses_scalar_runtime(name, state)
        and runtime_name_is_inferred_numeric(name, state)
        and runtime_name_slot_index(name, state) is not None
    )


def runtime_name_uses_string_slot_runtime(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use runtime string-slot access."""
    return (
        runtime_name_uses_scalar_runtime(name, state)
        and runtime_name_is_inferred_string(name, state)
        and runtime_name_slot_index(name, state) is not None
    )


def runtime_name_uses_only_scalar_runtime(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use scalar runtime helpers only."""
    return (
        runtime_name_uses_scalar_runtime(name, state)
        and not runtime_name_uses_numeric_slot_state(name, state)
        and not runtime_name_uses_string_slot_runtime(name, state)
    )


def runtime_expression_is_known_string(expression: Expr, state: LoweringState) -> bool:
    """Report whether one runtime-backed expression has string truthiness semantics."""
    match expression:
        case StringLiteralExpr() | FieldExpr() | ArrayIndexExpr():
            return True
        case NameExpr(name="FILENAME"):
            return True
        case NameExpr(name=name):
            return (
                name in state.loop_string_bindings
                or name in state.function_param_strings
                or runtime_name_is_inferred_string(name, state)
            )
        case CallExpr(function="sprintf" | "substr" | "tolower" | "toupper"):
            return True
        case BinaryExpr(op=BinaryOp.CONCAT):
            return True
        case AssignExpr(op=AssignOp.PLAIN, target=_, value=value):
            return runtime_assignment_preserves_string(value, state)
        case _:
            return False


def runtime_expression_is_definitely_numeric(expression: Expr, state: LoweringState) -> bool:
    """Report whether one runtime expression is known numeric without string semantics."""
    match expression:
        case NumericLiteralExpr():
            return True
        case StringLiteralExpr(value=value):
            return awk_string_is_numeric(value)
        case NameExpr(name="NR" | "FNR" | "NF"):
            return True
        case NameExpr(name=name):
            if is_reusable_runtime_state_name(name):
                return True
            inferred_type = state.type_info.get(name)
            return inferred_type is LatticeType.NUMERIC and runtime_name_uses_scalar_runtime(name, state)
        case AssignExpr(op=AssignOp.PLAIN, target=NameLValue(name=name), value=value):
            return is_reusable_runtime_state_name(name) and runtime_expression_is_definitely_numeric(value, state)
        case UnaryExpr(op=UnaryOp.UPLUS | UnaryOp.UMINUS | UnaryOp.NOT, operand=operand):
            return runtime_expression_is_definitely_numeric(operand, state)
        case UnaryExpr(op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC, operand=NameExpr() | FieldExpr() | ArrayIndexExpr(extra_indexes=())):
            return True
        case PostfixExpr(op=PostfixOp.POST_INC | PostfixOp.POST_DEC, operand=NameExpr() | FieldExpr() | ArrayIndexExpr(extra_indexes=())):
            return True
        case BinaryExpr(
            op=BinaryOp.ADD
            | BinaryOp.SUB
            | BinaryOp.MUL
            | BinaryOp.DIV
            | BinaryOp.MOD
            | BinaryOp.POW,
            left=left,
            right=right,
        ):
            return runtime_expression_is_definitely_numeric(left, state) and runtime_expression_is_definitely_numeric(
                right, state
            )
        case CallExpr(
            function="int" | "length" | "rand" | "srand" | "atan2" | "cos" | "exp" | "log" | "match" | "sin" | "sqrt" | "split" | "sub" | "gsub" | "system",
            args=args,
        ):
            return all(runtime_expression_is_definitely_numeric(argument, state) for argument in args)
        case _:
            return False


def lower_runtime_string_truthiness(expression: Expr, state: LoweringState) -> str:
    """Lower AWK string truthiness for one runtime-backed string expression."""
    string_value = lower_runtime_string_expression(expression, state)
    first_char = state.next_temp("strtruth.char")
    truthy = state.next_temp("strtruth")
    state.instructions.extend(
        [
            f"  {first_char} = load i8, ptr {string_value}",
            f"  {truthy} = icmp ne i8 {first_char}, 0",
        ]
    )
    return truthy


def runtime_assignment_preserves_string(expression: Expr, state: LoweringState) -> bool:
    """Report whether a scalar assignment should keep the runtime string view."""
    match expression:
        case NameExpr(name="FILENAME"):
            return True
        case NameExpr(name=name) if name in state.loop_string_bindings:
            return True
        case NameExpr(name=name):
            return runtime_name_uses_only_scalar_runtime(name, state) or runtime_name_uses_string_slot_runtime(name, state)
        case _:
            return runtime_expression_is_known_string(expression, state)


def lower_runtime_array_key(expression: Expr, state: LoweringState) -> str:
    """Lower one array key expression to a string pointer."""
    match expression:
        case NameExpr(name=name) if name in state.loop_string_bindings:
            return state.loop_string_bindings[name]
        case NumericLiteralExpr(value=value):
            temp = state.next_temp("array.key.num")
            captured = state.next_temp("array.key.capture")
            state.instructions.append(
                f"  {temp} = call ptr @qk_format_number(ptr {state.runtime_param}, double {format_double_literal(value)})"
            )
            state.instructions.append(
                f"  {captured} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {temp})"
            )
            return captured
        case StringLiteralExpr(value=value):
            return lower_runtime_constant_string(value, state)
        case _:
            if runtime_expression_has_string_result(expression, state):
                return lower_runtime_captured_string_expression(expression, state)
            numeric_value = lower_runtime_numeric_expression(expression, state)
            formatted = state.next_temp("array.key.num")
            captured = state.next_temp("array.key.capture")
            state.instructions.append(
                f"  {formatted} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})"
            )
            state.instructions.append(
                f"  {captured} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {formatted})"
            )
            return captured


def lower_runtime_array_subscripts(subscripts: tuple[Expr, ...], state: LoweringState) -> str:
    """Lower one array subscript tuple to the runtime's flat string key format."""
    if not subscripts:
        raise RuntimeError("empty array subscript lists are not supported by the runtime-backed backend")

    key_value = lower_runtime_array_key(subscripts[0], state)
    if len(subscripts) > 1:
        subsep_name = lower_runtime_scalar_name("SUBSEP", state)
        subsep_value = state.next_temp("array.subsep")
        state.instructions.append(
            f"  {subsep_value} = call ptr @qk_scalar_get_inline(ptr {state.runtime_param}, ptr {subsep_name})"
        )
        for subscript in subscripts[1:]:
            right_value = lower_runtime_array_key(subscript, state)
            joined_value = state.next_temp("array.key.join")
            next_key_value = state.next_temp("array.key.join")
            state.instructions.append(
                f"  {joined_value} = call ptr @qk_concat(ptr {state.runtime_param}, ptr {key_value}, ptr {subsep_value})"
            )
            state.instructions.append(
                f"  {next_key_value} = call ptr @qk_concat(ptr {state.runtime_param}, ptr {joined_value}, ptr {right_value})"
            )
            key_value = next_key_value
    captured_key = state.next_temp("array.key.capture")
    state.instructions.append(
        f"  {captured_key} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {key_value})"
    )
    return captured_key


def runtime_expression_has_side_effects(expression: Expr, state: LoweringState) -> bool:
    """Report whether lowering one expression may mutate runtime-visible state."""
    match expression:
        case AssignExpr():
            return True
        case UnaryExpr(op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC, operand=operand):
            return True
        case PostfixExpr(op=PostfixOp.POST_INC | PostfixOp.POST_DEC, operand=operand):
            return True
        case GetlineExpr():
            return True
        case CallExpr(function="split" | "sub" | "gsub" | "close" | "match" | "rand" | "srand" | "system"):
            return True
        case CallExpr(function=function_name) if function_name in state.function_defs:
            return True
        case BinaryExpr(left=left, right=right):
            return runtime_expression_has_side_effects(left, state) or runtime_expression_has_side_effects(right, state)
        case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
            return runtime_expression_has_side_effects(operand, state)
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            return (
                runtime_expression_has_side_effects(test, state)
                or runtime_expression_has_side_effects(if_true, state)
                or runtime_expression_has_side_effects(if_false, state)
            )
        case ArrayIndexExpr(index=index, extra_indexes=extra_indexes):
            return runtime_expression_has_side_effects(index, state) or any(
                runtime_expression_has_side_effects(extra_index, state) for extra_index in extra_indexes
            )
        case FieldExpr(index=index):
            return not isinstance(index, int) and runtime_expression_has_side_effects(index, state)
        case _:
            return False


def lower_runtime_field_index(index: int | Expr, state: LoweringState) -> str:
    """Lower one field index to an `i64` operand."""
    if isinstance(index, int):
        return str(index)
    numeric_value = lower_runtime_numeric_expression(index, state)
    integer_value = state.next_temp("field.index")
    state.instructions.append(f"  {integer_value} = fptosi double {numeric_value} to i64")
    return integer_value


def lower_runtime_numeric_conditional_expression(expression: ConditionalExpr, state: LoweringState) -> str:
    """Lower one runtime-backed numeric ternary expression with short-circuit control flow."""
    test_value = lower_condition_expression(expression.test, state)
    true_label = state.next_label("ternary.true")
    false_label = state.next_label("ternary.false")
    end_label = state.next_label("ternary.end")
    result = state.next_temp("ternary.num")

    state.instructions.append(f"  br i1 {test_value}, label %{true_label}, label %{false_label}")
    state.instructions.append(f"{true_label}:")
    true_operand = lower_runtime_numeric_expression(expression.if_true, state)
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{false_label}:")
    false_operand = lower_runtime_numeric_expression(expression.if_false, state)
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{end_label}:")
    state.instructions.append(f"  {result} = phi double [ {true_operand}, %{true_label} ], [ {false_operand}, %{false_label} ]")
    return result


def lower_runtime_condition_conditional_expression(expression: ConditionalExpr, state: LoweringState) -> str:
    """Lower one runtime-backed boolean ternary expression with short-circuit control flow."""
    test_value = lower_condition_expression(expression.test, state)
    true_label = state.next_label("cond.true")
    false_label = state.next_label("cond.false")
    end_label = state.next_label("cond.end")
    result = state.next_temp("cond")

    state.instructions.append(f"  br i1 {test_value}, label %{true_label}, label %{false_label}")
    state.instructions.append(f"{true_label}:")
    true_condition = lower_condition_expression(expression.if_true, state)
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{false_label}:")
    false_condition = lower_condition_expression(expression.if_false, state)
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{end_label}:")
    state.instructions.append(f"  {result} = phi i1 [ {true_condition}, %{true_label} ], [ {false_condition}, %{false_label} ]")
    return result


def lower_runtime_string_conditional_expression(expression: ConditionalExpr, state: LoweringState) -> str:
    """Lower one runtime-backed string ternary expression with short-circuit control flow."""
    assert state.runtime_param is not None
    test_value = lower_condition_expression(expression.test, state)
    true_label = state.next_label("ternary.true")
    false_label = state.next_label("ternary.false")
    end_label = state.next_label("ternary.end")
    result = state.next_temp("ternary.str")

    state.instructions.append(f"  br i1 {test_value}, label %{true_label}, label %{false_label}")
    state.instructions.append(f"{true_label}:")
    true_value = lower_runtime_string_expression(expression.if_true, state)
    true_capture = state.next_temp("ternary.str.capture")
    state.instructions.append(
        f"  {true_capture} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {true_value})"
    )
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{false_label}:")
    false_value = lower_runtime_string_expression(expression.if_false, state)
    false_capture = state.next_temp("ternary.str.capture")
    state.instructions.append(
        f"  {false_capture} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {false_value})"
    )
    state.instructions.append(f"  br label %{end_label}")
    state.instructions.append(f"{end_label}:")
    state.instructions.append(f"  {result} = phi ptr [ {true_capture}, %{true_label} ], [ {false_capture}, %{false_label} ]")
    return result


def runtime_expression_has_string_result(expression: Expr, state: LoweringState | None = None) -> bool:
    """Report whether one runtime-backed expression lowers as a string result."""
    match expression:
        case StringLiteralExpr() | FieldExpr() | ArrayIndexExpr():
            return True
        case NameExpr(name="FILENAME"):
            return True
        case NameExpr(name=name):
            return state is not None and (
                name in state.loop_string_bindings
                or name in state.function_param_strings
                or runtime_name_uses_only_scalar_runtime(name, state)
                or runtime_name_uses_string_slot_runtime(name, state)
            )
        case CallExpr(function="sprintf" | "substr" | "tolower" | "toupper"):
            return True
        case BinaryExpr(op=BinaryOp.CONCAT):
            return True
        case AssignExpr(op=AssignOp.PLAIN, target=_, value=value):
            return state is not None and runtime_assignment_preserves_string(value, state)
        case ConditionalExpr(test=_, if_true=if_true, if_false=if_false):
            return runtime_expression_has_string_result(if_true, state) and runtime_expression_has_string_result(
                if_false, state
            )
        case _:
            return False


def expression_forces_string_comparison(expression: Expr) -> bool:
    """Report whether one expression should force AWK string-comparison semantics."""
    match expression:
        case StringLiteralExpr(value=value):
            return not awk_string_is_numeric(value)
        case RegexLiteralExpr():
            return True
        case NameExpr(name="FILENAME"):
            return True
        case CallExpr(function="sprintf" | "substr" | "tolower" | "toupper"):
            return True
        case BinaryExpr(op=BinaryOp.CONCAT):
            return True
        case _:
            return False


def lower_condition_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a supported condition expression to an LLVM `i1` value."""
    if state.runtime_param is not None:
        match expression:
            case RegexLiteralExpr(raw_text=raw_text):
                pattern_text = decode_regex_literal(raw_text)
                global_name, byte_length = declare_string(state, pattern_text)
                string_ptr = state.next_temp("regexptr")
                match_result = state.next_temp("match")
                state.instructions.extend(
                    [
                        emit_gep(string_ptr, byte_length, global_name),
                        f"  {match_result} = call i1 @qk_regex_match_current_record(ptr {state.runtime_param}, ptr {string_ptr})",
                    ]
                )
                return match_result
            case NameExpr(name=name) if runtime_name_uses_only_scalar_runtime(name, state):
                scalar_name = lower_runtime_scalar_name(name, state)
                temp = state.next_temp("scalar.truthy")
                state.instructions.append(
                    f"  {temp} = call i1 @qk_scalar_truthy(ptr {state.runtime_param}, ptr {scalar_name})"
                )
                return temp
            case _ if runtime_expression_is_known_string(expression, state):
                return lower_runtime_string_truthiness(expression, state)

    numeric_lowerer = lower_runtime_numeric_expression if state.runtime_param is not None else lower_numeric_expression
    if isinstance(expression, BinaryExpr):
        if expression.op in {
            BinaryOp.LESS,
            BinaryOp.LESS_EQUAL,
            BinaryOp.GREATER,
            BinaryOp.GREATER_EQUAL,
            BinaryOp.EQUAL,
            BinaryOp.NOT_EQUAL,
        }:
            if state.runtime_param is not None:
                if (
                    not expression_forces_string_comparison(expression.left)
                    and not expression_forces_string_comparison(expression.right)
                    and runtime_expression_is_definitely_numeric(expression.left, state)
                    and runtime_expression_is_definitely_numeric(expression.right, state)
                ):
                    left_operand = lower_runtime_numeric_expression(expression.left, state)
                    right_operand = lower_runtime_numeric_expression(expression.right, state)
                    temp = state.next_temp("cmp")
                    predicate = {
                        BinaryOp.LESS: "olt",
                        BinaryOp.LESS_EQUAL: "ole",
                        BinaryOp.GREATER: "ogt",
                        BinaryOp.GREATER_EQUAL: "oge",
                        BinaryOp.EQUAL: "oeq",
                        BinaryOp.NOT_EQUAL: "one",
                    }[expression.op]
                    state.instructions.append(f"  {temp} = fcmp {predicate} double {left_operand}, {right_operand}")
                    return temp
                left_string = lower_runtime_captured_string_expression(expression.left, state)
                left_number = lower_runtime_numeric_expression(expression.left, state)
                right_string = lower_runtime_captured_string_expression(expression.right, state)
                right_number = lower_runtime_numeric_expression(expression.right, state)
                left_needs_check = str(runtime_expression_has_string_result(expression.left, state)).lower()
                right_needs_check = str(runtime_expression_has_string_result(expression.right, state)).lower()
                left_forces_string = str(expression_forces_string_comparison(expression.left)).lower()
                right_forces_string = str(expression_forces_string_comparison(expression.right)).lower()
                op_code = {
                    BinaryOp.LESS: 0,
                    BinaryOp.LESS_EQUAL: 1,
                    BinaryOp.GREATER: 2,
                    BinaryOp.GREATER_EQUAL: 3,
                    BinaryOp.EQUAL: 4,
                    BinaryOp.NOT_EQUAL: 5,
                }[expression.op]
                temp = state.next_temp("cmp")
                state.instructions.append(
                    f"  {temp} = call i1 @qk_compare_values_inline("
                    f"ptr {left_string}, double {left_number}, i1 {left_needs_check}, i1 {left_forces_string}, "
                    f"ptr {right_string}, double {right_number}, i1 {right_needs_check}, i1 {right_forces_string}, "
                    f"i32 {op_code})"
                )
                return temp

            left_operand = numeric_lowerer(expression.left, state)
            right_operand = numeric_lowerer(expression.right, state)
            temp = state.next_temp("cmp")
            predicate = {
                BinaryOp.LESS: "olt",
                BinaryOp.LESS_EQUAL: "ole",
                BinaryOp.GREATER: "ogt",
                BinaryOp.GREATER_EQUAL: "oge",
                BinaryOp.EQUAL: "oeq",
                BinaryOp.NOT_EQUAL: "one",
            }[expression.op]
            state.instructions.append(f"  {temp} = fcmp {predicate} double {left_operand}, {right_operand}")
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
        if expression.op is BinaryOp.LOGICAL_OR:
            left_condition = lower_condition_expression(expression.left, state)
            true_label = state.next_label("or.true")
            rhs_label = state.next_label("or.rhs")
            end_label = state.next_label("or.end")
            phi_temp = state.next_temp("or")

            state.instructions.append(f"  br i1 {left_condition}, label %{true_label}, label %{rhs_label}")
            state.instructions.append(f"{true_label}:")
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{rhs_label}:")
            right_condition = lower_condition_expression(expression.right, state)
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{end_label}:")
            state.instructions.append(
                f"  {phi_temp} = phi i1 [ true, %{true_label} ], [ {right_condition}, %{rhs_label} ]"
            )
            return phi_temp
        if state.runtime_param is not None and expression.op in {BinaryOp.MATCH, BinaryOp.NOT_MATCH}:
            return lower_runtime_match_operator(expression, state)
        if state.runtime_param is not None and expression.op is BinaryOp.IN:
            return lower_runtime_in_expression(expression, state)

    if isinstance(expression, ConditionalExpr):
        if runtime_expression_has_side_effects(expression.if_true, state) or runtime_expression_has_side_effects(
            expression.if_false, state
        ):
            return lower_runtime_condition_conditional_expression(expression, state)
        test_value = lower_condition_expression(expression.test, state)
        true_condition = lower_condition_expression(expression.if_true, state)
        false_condition = lower_condition_expression(expression.if_false, state)
        select_value = state.next_temp("cond")
        state.instructions.append(
            f"  {select_value} = select i1 {test_value}, i1 {true_condition}, i1 {false_condition}"
        )
        return select_value

    numeric_value = numeric_lowerer(expression, state)
    temp = state.next_temp("truthy")
    state.instructions.append(f"  {temp} = fcmp one double {numeric_value}, 0.000000000000000e+00")
    return temp


def lower_record_pattern(pattern: ExprPattern, state: LoweringState) -> str:
    """Lower one supported record-selection pattern in the reusable runtime model."""
    if isinstance(pattern.test, RegexLiteralExpr):
        pattern_text = decode_regex_literal(pattern.test.raw_text)
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
    return lower_condition_expression(pattern.test, state)


def execute_with_inputs(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    optimize: bool = False,
) -> int:
    """Execute the current program through the compiled backend/runtime path."""
    ensure_public_execution_supported(program, initial_variables)
    llvm_ir = build_public_execution_llvm_ir(
        program,
        input_files,
        field_separator,
        initial_variables,
        optimize=optimize,
    )
    return execute_llvm_ir(llvm_ir)


def ensure_public_execution_supported(
    program: Program,
    initial_variables: InitialVariables | None = None,
) -> None:
    """Reject public execution for programs the compiled backend cannot execute."""
    _ = initial_variables
    if has_function_definitions(program):
        return
    if has_host_runtime_only_operations(program) and not (
        supports_runtime_backend_subset(program) or supports_direct_function_backend_subset(program)
    ):
        raise RuntimeError("public execution does not support programs outside the compiled backend/runtime subset")


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


def link_reusable_inspection_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Link the program module and reusable driver without runtime implementations."""
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
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
            raise RuntimeError(result.stderr.strip() or "llvm-link failed to link the reusable inspection module")
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
    type_info = infer_variable_types(program)
    has_record_phase = bool(normalized_program.record_items)
    consumes_main_input = bool(normalized_program.record_items or normalized_program.end_actions)
    state_type = extract_state_type_declaration(program_llvm_ir)
    state_variable_indexes = reusable_runtime_state_indexes(normalized_program.variable_indexes)
    slot_variable_indexes = runtime_slot_indexes(
        normalized_program.variable_indexes, normalized_program.slot_allocation
    )
    numeric_slot_variable_indexes = runtime_numeric_slot_indexes(
        normalized_program.variable_indexes,
        type_info,
        normalized_program.slot_allocation,
    )
    string_slot_variable_indexes = runtime_string_slot_indexes(
        normalized_program.variable_indexes,
        type_info,
        normalized_program.slot_allocation,
    )
    state_storage_indexes = dict(sorted((state_variable_indexes | numeric_slot_variable_indexes).items(), key=lambda item: item[1]))

    globals_block = render_driver_globals(input_files, field_separator, initial_variables or [])
    state_setup = render_driver_state_setup(state_storage_indexes, initial_variables or [])
    scalar_preassignments = render_driver_scalar_preassignments(
        state_storage_indexes, slot_variable_indexes, string_slot_variable_indexes, initial_variables or []
    )
    record_loop = render_driver_record_loop(consumes_main_input, has_record_phase)

    return "\n".join(
        [
            "declare ptr @qk_runtime_create(i32, ptr, ptr)",
            "declare void @qk_runtime_destroy(ptr)",
            "declare i1 @qk_next_record_inline(ptr)",
            "declare i1 @qk_should_exit(ptr)",
            "declare i32 @qk_exit_status(ptr)",
            "declare void @qk_scalar_set_number_inline(ptr, ptr, double)",
            "declare void @qk_scalar_set_string(ptr, ptr, ptr)",
            "declare void @qk_slot_set_number(ptr, i64, double)",
            "declare void @qk_slot_set_string(ptr, i64, ptr)",
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
            *scalar_preassignments,
            "  call void @quawk_begin(ptr %rt, ptr %state)",
            *record_loop,
            "  call void @quawk_end(ptr %rt, ptr %state)",
            "  %exit.status = call i32 @qk_exit_status(ptr %rt)",
            "  call void @qk_runtime_destroy(ptr %rt)",
            "  ret i32 %exit.status",
            "}",
            "",
        ]
    )


def render_driver_globals(
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables,
) -> list[str]:
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

    seen_scalars: set[str] = set()
    for index, (name, value) in enumerate(initial_variables):
        if name in seen_scalars:
            if isinstance(value, str):
                globals_block.append(declare_bytes(driver_scalar_value_global(index), value.encode("utf-8") + b"\x00"))
            continue
        seen_scalars.add(name)
        global_name, _ = driver_scalar_name_global(name)
        globals_block.append(declare_bytes(global_name, name.encode("utf-8") + b"\x00"))
        if isinstance(value, str):
            globals_block.append(declare_bytes(driver_scalar_value_global(index), value.encode("utf-8") + b"\x00"))

    return globals_block


def driver_scalar_name_global(name: str) -> tuple[str, int]:
    """Return the global name and byte length for one driver scalar preassignment name."""
    return f"@.driver.scalar.{name}", len(name.encode("utf-8")) + 1


def driver_scalar_value_global(index: int) -> str:
    """Return the driver-global name for one string `-v` value."""
    return f"@.driver.scalar.value.{index}"


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
        numeric_value = format_double_literal(awk_numeric_prefix(value)) if isinstance(value, str) else format_double_literal(value)
        setup.extend(
            [
                (
                    f"  {slot_name} = getelementptr inbounds %quawk.state, ptr %state, "
                    f"i32 0, i32 {variable_index}"
                ),
                f"  store double {numeric_value}, ptr {slot_name}",
            ]
        )
    return setup


def render_driver_scalar_preassignments(
    state_variable_indexes: dict[str, int],
    slot_variable_indexes: dict[str, int],
    string_slot_variable_indexes: dict[str, int],
    initial_variables: InitialVariables,
) -> list[str]:
    """Render runtime scalar preassignments for names not stored in `%quawk.state`."""
    setup: list[str] = []
    for index, (name, value) in enumerate(initial_variables):
        if name in state_variable_indexes:
            continue
        slot_index = slot_variable_indexes.get(name)
        scalar_name, scalar_length = driver_scalar_name_global(name)
        setup.append(f"  %preassign.name.{index} = {emit_gep_inline(scalar_length, scalar_name)}")
        if isinstance(value, str):
            byte_length = len(value.encode("utf-8")) + 1
            setup.extend(
                [
                    f"  %preassign.value.{index} = {emit_gep_inline(byte_length, driver_scalar_value_global(index))}",
                    f"  call void @qk_scalar_set_string(ptr %rt, ptr %preassign.name.{index}, ptr %preassign.value.{index})",
                ]
            )
            string_slot_index = string_slot_variable_indexes.get(name)
            if string_slot_index is not None:
                setup.append(
                    f"  call void @qk_slot_set_string(ptr %rt, i64 {string_slot_index}, ptr %preassign.value.{index})"
                )
            if slot_index is not None:
                setup.append(
                    (
                        f"  call void @qk_slot_set_number("
                        f"ptr %rt, i64 {slot_index}, double {format_double_literal(awk_numeric_prefix(value))})"
                    )
                )
            continue
        setup.append(
            f"  call void @qk_scalar_set_number_inline(ptr %rt, ptr %preassign.name.{index}, double {format_double_literal(value)})"
        )
        if slot_index is not None:
            setup.append(
                f"  call void @qk_slot_set_number(ptr %rt, i64 {slot_index}, double {format_double_literal(value)})"
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


def render_driver_record_loop(consumes_main_input: bool, has_record_phase: bool) -> list[str]:
    """Render the per-record runtime loop in the execution driver."""
    if not consumes_main_input:
        return []
    body_lines = ["  call void @quawk_record(ptr %rt, ptr %state)"] if has_record_phase else []
    return [
        "  %should.exit.begin = call i1 @qk_should_exit(ptr %rt)",
        "  br i1 %should.exit.begin, label %record.done, label %record.cond",
        "record.cond:",
        "  %has.record = call i1 @qk_next_record_inline(ptr %rt)",
        "  br i1 %has.record, label %record.body, label %record.done",
        "record.body:",
        *body_lines,
        "  %should.exit.record = call i1 @qk_should_exit(ptr %rt)",
        "  br i1 %should.exit.record, label %record.done, label %record.cond",
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

    def supports_pure_expression(expression: Expr) -> bool:
        match expression:
            case NumericLiteralExpr() | NameExpr():
                return True
            case BinaryExpr(left=left, right=right):
                return supports_pure_expression(left) and supports_pure_expression(right)
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    supports_pure_expression(test)
                    and supports_pure_expression(if_true)
                    and supports_pure_expression(if_false)
                )
            case _:
                return False

    def supports_expression(expression: Expr, local_names: frozenset[str] = frozenset()) -> bool:
        match expression:
            case NumericLiteralExpr():
                return True
            case NameExpr():
                return True
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    supports_pure_expression(test)
                    and supports_pure_expression(if_true)
                    and supports_pure_expression(if_false)
                )
            case CallExpr(function=function_name, args=args):
                if function_name not in function_defs:
                    return False
                if len(args) != len(function_defs[function_name].params):
                    return False
                return all(supports_expression(argument, local_names) for argument in args)
            case BinaryExpr(
                op=BinaryOp.ADD
                | BinaryOp.SUB
                | BinaryOp.MUL
                | BinaryOp.DIV
                | BinaryOp.MOD
                | BinaryOp.POW
                | BinaryOp.LESS
                | BinaryOp.LESS_EQUAL
                | BinaryOp.GREATER
                | BinaryOp.GREATER_EQUAL
                | BinaryOp.EQUAL
                | BinaryOp.NOT_EQUAL
                | BinaryOp.LOGICAL_AND
                | BinaryOp.LOGICAL_OR,
                left=left,
                right=right,
            ):
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


def supports_runtime_backend_subset(program: Program) -> bool:
    """Report whether `program` fits the reusable backend's current runtime-backed subset."""

    normalized_program = normalize_program_for_lowering(program)
    array_names = normalized_program.array_names | frozenset({"ARGV", "ENVIRON"})
    function_defs = {
        item.name: item
        for item in program.items
        if isinstance(item, FunctionDef)
    }

    def supports_string_expression(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        match expression:
            case StringLiteralExpr():
                return True
            case NameExpr(name=name):
                return True
            case NameExpr(name="FILENAME"):
                return True
            case FieldExpr():
                return True
            case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
                return array_name in array_names and supports_array_key(index, string_bindings) and all(
                    supports_array_key(extra_index, string_bindings) for extra_index in extra_indexes
                )
            case CallExpr(function="sprintf", args=args):
                return bool(args) and supports_string_expression(args[0], string_bindings) and all(
                    supports_string_expression(argument, string_bindings) or supports_numeric_expression(argument)
                    for argument in args[1:]
                )
            case CallExpr(function=function_name, args=args) if function_name in function_defs:
                return all(
                    supports_string_expression(argument, string_bindings) or supports_numeric_expression(argument)
                    for argument in args
                )
            case CallExpr(function="substr", args=args):
                return len(args) in {2, 3} and supports_string_expression(args[0], string_bindings) and all(
                    supports_numeric_expression(argument) for argument in args[1:]
                )
            case CallExpr(function="tolower" | "toupper", args=args):
                return len(args) == 1 and (
                    supports_string_expression(args[0], string_bindings) or supports_numeric_expression(args[0])
                )
            case BinaryExpr(op=BinaryOp.CONCAT, left=left, right=right):
                return (
                    (supports_string_expression(left, string_bindings) or supports_numeric_expression(left))
                    and (supports_string_expression(right, string_bindings) or supports_numeric_expression(right))
                )
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    supports_condition_expression(test, string_bindings)
                    and supports_string_expression(if_true, string_bindings)
                    and supports_string_expression(if_false, string_bindings)
                )
            case _:
                return False

    def supports_array_key(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        match expression:
            case NameExpr():
                return True
            case NumericLiteralExpr() | StringLiteralExpr():
                return True
            case _:
                return supports_string_expression(expression, string_bindings) or supports_numeric_expression(expression)

    def supports_numeric_expression(expression: Expr) -> bool:
        match expression:
            case NumericLiteralExpr() | StringLiteralExpr():
                return True
            case NameExpr(name="NR" | "FNR" | "NF"):
                return True
            case NameExpr():
                return True
            case FieldExpr(index=index):
                return isinstance(index, int) or supports_numeric_expression(index)
            case AssignExpr(op=AssignOp.PLAIN, target=target, value=value):
                match target:
                    case NameLValue() | FieldLValue():
                        return supports_numeric_expression(value) or supports_string_expression(value)
                    case ArrayLValue(subscripts=subscripts):
                        return all(supports_array_key(subscript) for subscript in subscripts) and supports_numeric_expression(
                            value
                        )
                    case _:
                        return False
            case UnaryExpr(op=UnaryOp.UPLUS | UnaryOp.UMINUS | UnaryOp.NOT, operand=operand):
                return supports_numeric_expression(operand)
            case UnaryExpr(op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC, operand=NameExpr() | FieldExpr() | ArrayIndexExpr()):
                return True
            case PostfixExpr(op=PostfixOp.POST_INC | PostfixOp.POST_DEC, operand=NameExpr() | FieldExpr() | ArrayIndexExpr()):
                return True
            case BinaryExpr(
                op=BinaryOp.ADD
                | BinaryOp.SUB
                | BinaryOp.MUL
                | BinaryOp.DIV
                | BinaryOp.MOD
                | BinaryOp.POW,
                left=left,
                right=right,
            ):
                return supports_numeric_expression(left) and supports_numeric_expression(right)
            case BinaryExpr(
                op=BinaryOp.LESS
                | BinaryOp.LESS_EQUAL
                | BinaryOp.GREATER
                | BinaryOp.GREATER_EQUAL
                | BinaryOp.EQUAL
                | BinaryOp.NOT_EQUAL
                | BinaryOp.LOGICAL_AND
                | BinaryOp.LOGICAL_OR
                | BinaryOp.MATCH
                | BinaryOp.NOT_MATCH
                | BinaryOp.IN,
            ):
                return supports_condition_expression(expression)
            case CallExpr(function="split", args=args):
                if len(args) not in {2, 3}:
                    return False
                if not supports_string_expression(args[0]):
                    return False
                if not isinstance(args[1], NameExpr):
                    return False
                return len(args) == 2 or supports_string_expression(args[2])
            case CallExpr(function="close", args=args):
                return len(args) == 1 and (supports_string_expression(args[0]) or supports_numeric_expression(args[0]))
            case CallExpr(function="gsub" | "sub", args=args):
                if len(args) not in {2, 3}:
                    return False
                if not supports_string_expression(args[1]) and not supports_numeric_expression(args[1]):
                    return False
                if not (
                    isinstance(args[0], RegexLiteralExpr)
                    or supports_string_expression(args[0])
                    or supports_numeric_expression(args[0])
                ):
                    return False
                if len(args) == 2:
                    return True
                target = expression_to_lvalue(args[2])
                if target is None:
                    return False
                match target:
                    case NameLValue():
                        return True
                    case FieldLValue(index=index):
                        return supports_numeric_expression(index)
                    case ArrayLValue(subscripts=subscripts):
                        return bool(subscripts) and all(supports_array_key(subscript) for subscript in subscripts)
                    case _:
                        return False
            case CallExpr(function="index", args=args):
                return len(args) == 2 and all(
                    supports_string_expression(argument) or supports_numeric_expression(argument) for argument in args
                )
            case CallExpr(function="int" | "cos" | "exp" | "log" | "sin" | "sqrt", args=args):
                return len(args) == 1 and supports_numeric_expression(args[0])
            case CallExpr(function="length", args=args):
                if len(args) > 1:
                    return False
                if not args:
                    return True
                argument = args[0]
                if isinstance(argument, NameExpr) and argument.name in array_names:
                    return True
                return supports_string_expression(argument)
            case CallExpr(function="match", args=args):
                return len(args) == 2 and (
                    supports_string_expression(args[0]) or supports_numeric_expression(args[0])
                ) and (
                    isinstance(args[1], RegexLiteralExpr)
                    or supports_string_expression(args[1])
                    or supports_numeric_expression(args[1])
                )
            case CallExpr(function="rand", args=args):
                return len(args) == 0
            case CallExpr(function="srand", args=args):
                return len(args) in {0, 1} and (not args or supports_numeric_expression(args[0]))
            case CallExpr(function="system", args=args):
                return len(args) == 1 and (
                    supports_string_expression(args[0]) or supports_numeric_expression(args[0])
                )
            case CallExpr(function="atan2", args=args):
                return len(args) == 2 and all(supports_numeric_expression(argument) for argument in args)
            case CallExpr(function=function_name, args=args):
                return function_name in function_defs and all(
                    supports_string_expression(argument) or supports_numeric_expression(argument) for argument in args
                )
            case GetlineExpr(target=target, source=source):
                target_supported = True
                if target is not None:
                    match target:
                        case NameLValue():
                            target_supported = True
                        case FieldLValue(index=index):
                            target_supported = supports_numeric_expression(index)
                        case ArrayLValue(subscripts=subscripts):
                            target_supported = bool(subscripts) and all(supports_array_key(subscript) for subscript in subscripts)
                        case _:
                            target_supported = False
                return target_supported and (
                    source is None or supports_string_expression(source) or supports_numeric_expression(source)
                )
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    supports_condition_expression(test)
                    and supports_numeric_expression(if_true)
                    and supports_numeric_expression(if_false)
                )
            case _:
                return False

    def supports_pattern(pattern: ExprPattern | RangePattern | BeginPattern | EndPattern | None) -> bool:
        if pattern is None or isinstance(pattern, BeginPattern | EndPattern):
            return True
        if isinstance(pattern, ExprPattern):
            return isinstance(pattern.test, RegexLiteralExpr) or supports_condition_expression(pattern.test)
        if isinstance(pattern, RangePattern):
            return supports_pattern(pattern.left) and supports_pattern(pattern.right)
        return False

    def supports_side_effect_expression(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        return (
            supports_string_expression(expression, string_bindings)
            or supports_numeric_expression(expression)
            or (isinstance(expression, CallExpr) and expression.function == "split" and supports_numeric_expression(expression))
        )

    def supports_condition_expression(expression: Expr, string_bindings: frozenset[str] = frozenset()) -> bool:
        def supports_comparison_operand(operand: Expr) -> bool:
            return (
                supports_string_expression(operand, string_bindings)
                or runtime_expression_has_string_result(operand)
                or supports_numeric_expression(operand)
            )

        match expression:
            case RegexLiteralExpr():
                return True
            case BinaryExpr(
                op=BinaryOp.LESS
                | BinaryOp.LESS_EQUAL
                | BinaryOp.GREATER
                | BinaryOp.GREATER_EQUAL
                | BinaryOp.EQUAL
                | BinaryOp.NOT_EQUAL,
                left=left,
                right=right,
            ):
                return (
                    supports_comparison_operand(left)
                    and supports_comparison_operand(right)
                )
            case BinaryExpr(op=BinaryOp.LOGICAL_AND | BinaryOp.LOGICAL_OR, left=left, right=right):
                return supports_condition_expression(left, string_bindings) and supports_condition_expression(
                    right, string_bindings
                )
            case BinaryExpr(op=BinaryOp.MATCH | BinaryOp.NOT_MATCH, left=left, right=right):
                return (
                    (supports_string_expression(left, string_bindings) or supports_numeric_expression(left))
                    and (
                        isinstance(right, RegexLiteralExpr)
                        or supports_string_expression(right, string_bindings)
                        or supports_numeric_expression(right)
                    )
                )
            case BinaryExpr(op=BinaryOp.IN, left=left, right=NameExpr(name=array_name)):
                return (
                    array_name in array_names
                    and (supports_string_expression(left, string_bindings) or supports_numeric_expression(left))
                )
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    supports_condition_expression(test, string_bindings)
                    and supports_condition_expression(if_true, string_bindings)
                    and supports_condition_expression(if_false, string_bindings)
                )
            case _:
                return supports_numeric_expression(expression) or supports_string_expression(expression, string_bindings)

    def expression_contains_p21_or_p22_or_p23_or_p24_operator(expression: Expr) -> bool:
        match expression:
            case BinaryExpr(
                op=BinaryOp.LESS_EQUAL
                | BinaryOp.GREATER
                | BinaryOp.GREATER_EQUAL
                | BinaryOp.NOT_EQUAL
                | BinaryOp.LOGICAL_OR
                | BinaryOp.SUB
                | BinaryOp.MUL
                | BinaryOp.DIV
                | BinaryOp.MOD
                | BinaryOp.POW
                | BinaryOp.MATCH
                | BinaryOp.NOT_MATCH
                | BinaryOp.IN,
                left=left,
                right=right,
            ):
                return True
            case BinaryExpr(left=left, right=right):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(left) or expression_contains_p21_or_p22_or_p23_or_p24_operator(right)
            case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(operand)
            case ConditionalExpr():
                return True
            case AssignExpr(value=value):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(value)
            case ArrayIndexExpr(index=index, extra_indexes=extra_indexes):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(index) or any(
                    expression_contains_p21_or_p22_or_p23_or_p24_operator(extra_index) for extra_index in extra_indexes
                )
            case FieldExpr(index=index):
                return not isinstance(index, int) and expression_contains_p21_or_p22_or_p23_or_p24_operator(index)
            case CallExpr(args=args):
                return any(expression_contains_p21_or_p22_or_p23_or_p24_operator(argument) for argument in args)
            case GetlineExpr(source=source):
                return source is not None and expression_contains_p21_or_p22_or_p23_or_p24_operator(source)
            case _:
                return False

    def expression_contains_runtime_builtin(expression: Expr) -> bool:
        match expression:
            case CallExpr():
                return True
            case GetlineExpr():
                return True
            case BinaryExpr(left=left, right=right):
                return expression_contains_runtime_builtin(left) or expression_contains_runtime_builtin(right)
            case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
                return expression_contains_runtime_builtin(operand)
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    expression_contains_runtime_builtin(test)
                    or expression_contains_runtime_builtin(if_true)
                    or expression_contains_runtime_builtin(if_false)
                )
            case AssignExpr(value=value):
                return expression_contains_runtime_builtin(value)
            case ArrayIndexExpr(index=index, extra_indexes=extra_indexes):
                return expression_contains_runtime_builtin(index) or any(
                    expression_contains_runtime_builtin(extra_index) for extra_index in extra_indexes
                )
            case FieldExpr(index=index):
                return not isinstance(index, int) and expression_contains_runtime_builtin(index)
            case _:
                return False

    def statement_contains_runtime_builtin(statement: Stmt) -> bool:
        match statement:
            case AssignStmt(target=target, value=value):
                if expression_contains_runtime_builtin(value):
                    return True
                match target:
                    case ArrayLValue(subscripts=subscripts):
                        return any(expression_contains_runtime_builtin(subscript) for subscript in subscripts)
                    case FieldLValue(index=index):
                        return expression_contains_runtime_builtin(index)
                    case _:
                        return False
            case BlockStmt(statements=statements):
                return any(statement_contains_runtime_builtin(nested) for nested in statements)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                return (
                    expression_contains_runtime_builtin(condition)
                    or statement_contains_runtime_builtin(then_branch)
                    or (else_branch is not None and statement_contains_runtime_builtin(else_branch))
                )
            case WhileStmt(condition=condition, body=body):
                return expression_contains_runtime_builtin(condition) or statement_contains_runtime_builtin(body)
            case DoWhileStmt(body=body, condition=condition):
                return statement_contains_runtime_builtin(body) or expression_contains_runtime_builtin(condition)
            case PrintStmt(arguments=arguments, redirect=redirect):
                return any(expression_contains_runtime_builtin(argument) for argument in arguments) or (
                    redirect is not None and expression_contains_runtime_builtin(redirect.target)
                )
            case PrintfStmt(arguments=arguments, redirect=redirect):
                return any(expression_contains_runtime_builtin(argument) for argument in arguments) or (
                    redirect is not None and expression_contains_runtime_builtin(redirect.target)
                )
            case ExprStmt(value=value):
                return expression_contains_runtime_builtin(value)
            case ExitStmt(value=value) | ReturnStmt(value=value):
                return value is not None and expression_contains_runtime_builtin(value)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                return (
                    any(expression_contains_runtime_builtin(expression) for expression in init)
                    or (condition is not None and expression_contains_runtime_builtin(condition))
                    or any(expression_contains_runtime_builtin(expression) for expression in update)
                    or statement_contains_runtime_builtin(body)
                )
            case ForInStmt(iterable=iterable, body=body):
                return expression_contains_runtime_builtin(iterable) or statement_contains_runtime_builtin(body)
            case DeleteStmt(index=index, extra_indexes=extra_indexes):
                return (
                    (index is not None and expression_contains_runtime_builtin(index))
                    or any(expression_contains_runtime_builtin(extra_index) for extra_index in extra_indexes)
                )
            case _:
                return False

    def statement_contains_p21_or_p22_or_p23_or_p24_operator(statement: Stmt) -> bool:
        match statement:
            case AssignStmt(target=target, value=value):
                if expression_contains_p21_or_p22_or_p23_or_p24_operator(value):
                    return True
                match target:
                    case ArrayLValue(subscripts=subscripts):
                        return any(expression_contains_p21_or_p22_or_p23_or_p24_operator(subscript) for subscript in subscripts)
                    case FieldLValue(index=index):
                        return expression_contains_p21_or_p22_or_p23_or_p24_operator(index)
                    case _:
                        return False
            case BlockStmt(statements=statements):
                return any(statement_contains_p21_or_p22_or_p23_or_p24_operator(nested) for nested in statements)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                return (
                    expression_contains_p21_or_p22_or_p23_or_p24_operator(condition)
                    or statement_contains_p21_or_p22_or_p23_or_p24_operator(then_branch)
                    or (else_branch is not None and statement_contains_p21_or_p22_or_p23_or_p24_operator(else_branch))
                )
            case WhileStmt(condition=condition, body=body):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(condition) or statement_contains_p21_or_p22_or_p23_or_p24_operator(body)
            case DoWhileStmt(body=body, condition=condition):
                return statement_contains_p21_or_p22_or_p23_or_p24_operator(body) or expression_contains_p21_or_p22_or_p23_or_p24_operator(condition)
            case PrintStmt(arguments=arguments, redirect=redirect):
                return any(expression_contains_p21_or_p22_or_p23_or_p24_operator(argument) for argument in arguments) or (
                    redirect is not None and expression_contains_p21_or_p22_or_p23_or_p24_operator(redirect.target)
                )
            case PrintfStmt(arguments=arguments, redirect=redirect):
                return any(expression_contains_p21_or_p22_or_p23_or_p24_operator(argument) for argument in arguments) or (
                    redirect is not None and expression_contains_p21_or_p22_or_p23_or_p24_operator(redirect.target)
                )
            case ExprStmt(value=value):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(value)
            case ExitStmt(value=value) | ReturnStmt(value=value):
                return value is not None and expression_contains_p21_or_p22_or_p23_or_p24_operator(value)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                return (
                    any(expression_contains_p21_or_p22_or_p23_or_p24_operator(expression) for expression in init)
                    or (condition is not None and expression_contains_p21_or_p22_or_p23_or_p24_operator(condition))
                    or any(expression_contains_p21_or_p22_or_p23_or_p24_operator(expression) for expression in update)
                    or statement_contains_p21_or_p22_or_p23_or_p24_operator(body)
                )
            case ForInStmt(iterable=iterable, body=body):
                return expression_contains_p21_or_p22_or_p23_or_p24_operator(iterable) or statement_contains_p21_or_p22_or_p23_or_p24_operator(body)
            case DeleteStmt(index=index, extra_indexes=extra_indexes):
                return (
                    (index is not None and expression_contains_p21_or_p22_or_p23_or_p24_operator(index))
                    or any(expression_contains_p21_or_p22_or_p23_or_p24_operator(extra_index) for extra_index in extra_indexes)
                )
            case _:
                return False

    def supports_statement(statement: Stmt, string_bindings: frozenset[str] = frozenset()) -> bool:
        match statement:
            case AssignStmt(op=op, target=target, value=value):
                match target:
                    case NameLValue():
                        if op is AssignOp.PLAIN:
                            return supports_numeric_expression(value) or supports_string_expression(value)
                        return supports_numeric_expression(value)
                    case ArrayLValue(name=name, subscripts=subscripts):
                        if not (
                            subscripts
                            and name in array_names
                            and all(supports_array_key(subscript, string_bindings) for subscript in subscripts)
                        ):
                            return False
                        if op is AssignOp.PLAIN:
                            return supports_numeric_expression(value) or supports_string_expression(
                                value, string_bindings
                            )
                        return supports_numeric_expression(value)
                    case FieldLValue(index=index):
                        if not supports_numeric_expression(index):
                            return False
                        if op is AssignOp.PLAIN:
                            return supports_numeric_expression(value) or supports_string_expression(
                                value, string_bindings
                            )
                        return supports_numeric_expression(value)
                    case _:
                        return False
            case BlockStmt(statements=statements):
                return all(supports_statement(nested, string_bindings) for nested in statements)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                return supports_condition_expression(condition, string_bindings) and supports_statement(
                    then_branch, string_bindings
                ) and (
                    else_branch is None or supports_statement(else_branch, string_bindings)
                )
            case WhileStmt(condition=condition, body=body):
                return supports_condition_expression(condition, string_bindings) and supports_statement(body, string_bindings)
            case DoWhileStmt(body=body, condition=condition):
                return supports_statement(body, string_bindings) and supports_condition_expression(
                    condition, string_bindings
                )
            case BreakStmt() | ContinueStmt():
                return True
            case DeleteStmt():
                if statement.array_name is None or statement.array_name not in array_names:
                    return False
                return statement.index is None or all(
                    supports_array_key(subscript, string_bindings) for subscript in (statement.index, *statement.extra_indexes)
                )
            case PrintStmt(arguments=arguments, redirect=redirect):
                arguments_supported = not arguments or all(
                    supports_string_expression(argument, string_bindings)
                    or runtime_expression_has_string_result(argument)
                    or supports_numeric_expression(argument)
                    for argument in arguments
                )
                if not arguments_supported:
                    return False
                if redirect is None:
                    return True
                return supports_string_expression(redirect.target, string_bindings) or supports_numeric_expression(
                    redirect.target
                )
            case PrintfStmt(arguments=arguments, redirect=redirect):
                if not arguments:
                    return False
                format_expression = arguments[0]
                if isinstance(format_expression, StringLiteralExpr):
                    specifiers = [
                        match.group(1) for match in PRINTF_SPEC_PATTERN.finditer(format_expression.value)
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
                else:
                    if not (
                        supports_string_expression(format_expression, string_bindings)
                        or runtime_expression_has_string_result(format_expression)
                        or supports_numeric_expression(format_expression)
                    ):
                        return False
                    if not all(
                        supports_string_expression(argument, string_bindings)
                        or runtime_expression_has_string_result(argument)
                        or supports_numeric_expression(argument)
                        for argument in arguments[1:]
                    ):
                        return False
                if redirect is None:
                    return True
                return supports_string_expression(redirect.target, string_bindings) or supports_numeric_expression(
                    redirect.target
                )
            case ExprStmt(value=value):
                if isinstance(value, CallExpr) and value.function == "close":
                    return supports_numeric_expression(value)
                return supports_side_effect_expression(value, string_bindings)
            case NextStmt():
                return True
            case NextFileStmt():
                return True
            case ExitStmt(value=value):
                return value is None or supports_numeric_expression(value)
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

    def supports_runtime_function_statement(statement: Stmt, string_bindings: frozenset[str] = frozenset()) -> bool:
        match statement:
            case BlockStmt(statements=statements):
                return all(supports_runtime_function_statement(nested, string_bindings) for nested in statements)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                return supports_condition_expression(condition, string_bindings) and supports_runtime_function_statement(
                    then_branch, string_bindings
                ) and (
                    else_branch is None or supports_runtime_function_statement(else_branch, string_bindings)
                )
            case WhileStmt(condition=condition, body=body):
                return supports_condition_expression(condition, string_bindings) and supports_runtime_function_statement(
                    body, string_bindings
                )
            case DoWhileStmt(body=body, condition=condition):
                return supports_runtime_function_statement(body, string_bindings) and supports_condition_expression(
                    condition, string_bindings
                )
            case BreakStmt() | ContinueStmt():
                return True
            case DeleteStmt():
                return supports_statement(statement, string_bindings)
            case PrintStmt():
                return supports_statement(statement, string_bindings)
            case PrintfStmt():
                return supports_statement(statement, string_bindings)
            case ExprStmt():
                return supports_statement(statement, string_bindings)
            case ExitStmt():
                return supports_statement(statement, string_bindings)
            case ForStmt():
                return supports_statement(statement, string_bindings)
            case ForInStmt():
                return supports_statement(statement, string_bindings)
            case ReturnStmt():
                return supports_statement(statement, string_bindings)
            case _:
                return False

    found_supported_runtime_feature = False
    for item in program.items:
        if isinstance(item, FunctionDef):
            if not all(supports_runtime_function_statement(statement) for statement in item.body.statements):
                return False
            found_supported_runtime_feature = True
            continue
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
        if any(statement_contains_runtime_builtin(statement) for statement in item.action.statements):
            found_supported_runtime_feature = True
        if any(statement_contains_p21_or_p22_or_p23_or_p24_operator(statement) for statement in item.action.statements):
            found_supported_runtime_feature = True
        if isinstance(item.pattern, RangePattern):
            found_supported_runtime_feature = True
        if isinstance(item.pattern, ExprPattern) and not isinstance(item.pattern.test, RegexLiteralExpr):
            found_supported_runtime_feature = True
        for statement in item.action.statements:
            if isinstance(statement, PrintfStmt):
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and statement.field_index is not None:
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and isinstance(statement.target, NameLValue):
                if isinstance(statement.value, NameExpr):
                    found_supported_runtime_feature = True
                if isinstance(statement.value, StringLiteralExpr):
                    found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and isinstance(statement.value, CallExpr):
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and isinstance(statement.target, ArrayLValue):
                found_supported_runtime_feature = True
            if isinstance(statement, DeleteStmt | ForStmt | ForInStmt):
                found_supported_runtime_feature = True
            if isinstance(statement, PrintStmt) and statement.arguments:
                argument = statement.arguments[0]
                if isinstance(argument, NameExpr):
                    found_supported_runtime_feature = True
                if isinstance(argument, FieldExpr) and not isinstance(argument.index, int):
                    found_supported_runtime_feature = True
                if isinstance(argument, CallExpr) and argument.function == "length":
                    found_supported_runtime_feature = True
                if isinstance(argument, ArrayIndexExpr):
                    found_supported_runtime_feature = True
                if isinstance(argument, BinaryExpr) and argument.op is BinaryOp.CONCAT:
                    found_supported_runtime_feature = True
                if len(statement.arguments) != 1:
                    found_supported_runtime_feature = True
                if statement.redirect is not None:
                    found_supported_runtime_feature = True
            if isinstance(statement, PrintStmt) and not statement.arguments:
                found_supported_runtime_feature = True
            if isinstance(statement, PrintfStmt) and statement.redirect is not None:
                found_supported_runtime_feature = True
            if isinstance(statement, AssignStmt) and isinstance(statement.target, NameLValue):
                if isinstance(statement.value, StringLiteralExpr):
                    found_supported_runtime_feature = True
                if isinstance(statement.value, NameExpr) and statement.value.name == "FILENAME":
                    found_supported_runtime_feature = True
                if isinstance(statement.value, BinaryExpr) and statement.value.op is BinaryOp.CONCAT:
                    found_supported_runtime_feature = True
            if isinstance(statement, DoWhileStmt | BreakStmt | ContinueStmt | NextStmt):
                found_supported_runtime_feature = True
            if isinstance(statement, NextFileStmt | ExitStmt):
                found_supported_runtime_feature = True
            if isinstance(statement, ExprStmt) and isinstance(statement.value, CallExpr) and statement.value.function == "close":
                found_supported_runtime_feature = True
    return found_supported_runtime_feature


def has_host_runtime_only_operations(program: Program) -> bool:
    """Report whether `program` contains features not yet supported by LLVM lowering."""

    def expression_has_host_runtime_only_ops(expression: Expr) -> bool:
        match expression:
            case ArrayIndexExpr():
                return True
            case GetlineExpr():
                return True
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                return (
                    expression_has_host_runtime_only_ops(test)
                    or expression_has_host_runtime_only_ops(if_true)
                    or expression_has_host_runtime_only_ops(if_false)
                )
            case AssignExpr() | UnaryExpr() | PostfixExpr():
                return True
            case FieldExpr(index=index):
                if isinstance(index, int):
                    return False
                return True
            case BinaryExpr(op=op, left=left, right=right):
                if op not in {
                    BinaryOp.ADD,
                    BinaryOp.SUB,
                    BinaryOp.MUL,
                    BinaryOp.DIV,
                    BinaryOp.MOD,
                    BinaryOp.POW,
                    BinaryOp.LESS,
                    BinaryOp.LESS_EQUAL,
                    BinaryOp.GREATER,
                    BinaryOp.GREATER_EQUAL,
                    BinaryOp.EQUAL,
                    BinaryOp.NOT_EQUAL,
                    BinaryOp.LOGICAL_AND,
                    BinaryOp.LOGICAL_OR,
                    BinaryOp.MATCH,
                    BinaryOp.NOT_MATCH,
                    BinaryOp.IN,
                }:
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


def is_reusable_runtime_state_name(name: str) -> bool:
    """Report whether one lowering-only name should stay in `%quawk.state`."""
    return name.startswith("__range.")


def reusable_runtime_state_indexes(variable_indexes: dict[str, int]) -> dict[str, int]:
    """Return `%quawk.state` indexes for reusable runtime-only names."""
    return {
        name: index
        for name, index in sorted(variable_indexes.items(), key=lambda item: item[1])
        if is_reusable_runtime_state_name(name)
    }


def runtime_slot_indexes(
    variable_indexes: dict[str, int],
    slot_allocation: SlotAllocation | None = None,
) -> dict[str, int]:
    """Return runtime slot indexes for known scalar names tracked by lowering."""
    if slot_allocation is not None:
        return {
            slot.name: slot.index
            for slot in slot_allocation.slots
            if slot.storage == "slot"
            and not is_builtin_variable_name(slot.name)
            and not is_reusable_runtime_state_name(slot.name)
        }
    return {
        name: index
        for name, index in sorted(variable_indexes.items(), key=lambda item: item[1])
        if not is_builtin_variable_name(name) and not is_reusable_runtime_state_name(name)
    }


def runtime_numeric_slot_indexes(
    variable_indexes: dict[str, int],
    type_info: Mapping[str, LatticeType],
    slot_allocation: SlotAllocation | None = None,
) -> dict[str, int]:
    """Return runtime slot indexes for names inferred as numeric."""
    slot_indexes = runtime_slot_indexes(variable_indexes, slot_allocation)
    return {
        name: index
        for name, index in slot_indexes.items()
        if type_info.get(name) is LatticeType.NUMERIC
    }


def runtime_string_slot_indexes(
    variable_indexes: dict[str, int],
    type_info: Mapping[str, LatticeType],
    slot_allocation: SlotAllocation | None = None,
) -> dict[str, int]:
    """Return runtime slot indexes for names inferred as string."""
    slot_indexes = runtime_slot_indexes(variable_indexes, slot_allocation)
    return {
        name: index
        for name, index in slot_indexes.items()
        if type_info.get(name) is LatticeType.STRING
    }


def render_state_type(slot_allocation: SlotAllocation) -> str | None:
    """Render `%quawk.state` from slot-allocation metadata when slots exist."""
    if slot_allocation.variable_count == 0:
        return None
    return slot_allocation.state_struct_type


def render_reusable_function(name: str, state: LoweringState) -> str:
    """Render one reusable BEGIN/record/END function body."""
    if state.phase_exit_label is None:
        raise RuntimeError("reusable lowering requires a precomputed phase exit label")
    return "\n".join(
        [
            f"define void @{name}(ptr %rt, ptr %state) {{",
            "entry:",
            *state.allocas,
            *state.instructions,
            f"  br label %{state.phase_exit_label}",
            f"{state.phase_exit_label}:",
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


def render_runtime_user_function(function_def: FunctionDef, state: LoweringState) -> str:
    """Render one lowered runtime-backed user-defined function."""
    arguments = ", ".join(["ptr %rt", "ptr %state", *(f"ptr %arg.{index}" for index, _ in enumerate(function_def.params))])
    return "\n".join(
        [
            f"define ptr @qk_fn_{function_def.name}({arguments}) {{",
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
    data = b"%.6g\n\x00"
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


def run_process_with_current_stdin(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run one subprocess while forwarding the current stdin source when possible."""
    stdin_handle = current_stdin_handle()
    if stdin_handle is not None:
        return subprocess.run(
            command,
            stdin=stdin_handle,
            capture_output=True,
            check=False,
        )

    try:
        stdin_buffer = sys.stdin.buffer
    except AttributeError:
        try:
            stdin_text = sys.stdin.read()
        except OSError:
            stdin_bytes = b""
        else:
            stdin_bytes = stdin_text.encode("utf-8")
    else:
        try:
            stdin_bytes = stdin_buffer.read()
        except OSError:
            stdin_bytes = b""

    return subprocess.run(command, input=stdin_bytes, capture_output=True, check=False)


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
