from __future__ import annotations

import re

from ..ast import FunctionDef
from .state import LoweringState

FULL_NUMERIC_PATTERN = re.compile(r"^[ \t\r\n\f\v]*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[ \t\r\n\f\v]*$")
NUMERIC_PREFIX_PATTERN = re.compile(r"^[ \t\r\n\f\v]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")

REUSABLE_PROGRAM_DECLARATIONS: tuple[str, ...] = (
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
)

EXECUTION_DRIVER_DECLARATIONS: tuple[str, ...] = (
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
)


def awk_string_is_numeric(text: str) -> bool:
    """Report whether one string is fully numeric under AWK comparison rules."""
    return FULL_NUMERIC_PATTERN.fullmatch(text) is not None


def awk_numeric_prefix(text: str) -> float:
    """Parse one AWK numeric prefix, returning `0.0` when none is present."""
    match = NUMERIC_PREFIX_PATTERN.match(text)
    if match is None:
        return 0.0
    return float(match.group(1))


def reusable_program_declarations(state_type: str | None) -> list[str]:
    """Return the reusable-program declaration block, including `%quawk.state` when present."""
    declarations = list(REUSABLE_PROGRAM_DECLARATIONS)
    if state_type is not None:
        declarations.append(state_type)
    return declarations


def execution_driver_declarations(state_type: str | None) -> list[str]:
    """Return the driver declaration block, including `%quawk.state` when present."""
    declarations = list(EXECUTION_DRIVER_DECLARATIONS)
    if state_type is not None:
        declarations.append(state_type)
    return declarations


def extract_state_type_declaration(program_llvm_ir: str) -> str | None:
    """Extract the reusable state-type declaration from one lowered program module."""
    for line in program_llvm_ir.splitlines():
        if line.startswith("%quawk.state = type "):
            return line
    return None


def render_reusable_function(name: str, state: LoweringState) -> str:
    """Render one reusable BEGIN/record/END function body."""
    if state.phase_exit_label is None:
        raise RuntimeError("reusable lowering requires a precomputed phase exit label")
    return "\n".join(
        [
            f"define void @{name}(ptr %rt, ptr %state) {{",
            "entry:",
            *state.allocas,
            *state.entry_instructions,
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
            *state.entry_instructions,
            *state.instructions,
            "}",
        ]
    )


def render_runtime_user_function(function_def: FunctionDef, state: LoweringState) -> str:
    """Render one lowered runtime-backed user-defined function."""
    arguments = ", ".join(
        ["ptr %rt", "ptr %state", *(f"ptr %arg.{index}" for index, _ in enumerate(function_def.params))]
    )
    return "\n".join(
        [
            f"define ptr @qk_fn_{function_def.name}({arguments}) {{",
            "entry:",
            *state.allocas,
            *state.entry_instructions,
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


def format_double_literal(value: float) -> str:
    """Format a Python float as a stable LLVM IR double literal."""
    return f"{value:.15e}"
