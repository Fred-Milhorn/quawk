from __future__ import annotations

from typing import Mapping

from ..ast import EndPattern, ExprPattern, FunctionDef, PatternAction, Program, RangePattern
from ..builtins import is_builtin_variable_name
from ..normalization import normalize_program_for_lowering
from ..slot_allocation import SlotAllocation
from ..type_inference import LatticeType, infer_variable_types
from .runtime_abi import (
    awk_numeric_prefix,
    declare_bytes,
    emit_gep_constant,
    emit_gep_inline,
    execution_driver_declarations,
    extract_state_type_declaration,
    format_double_literal,
)
from .state import InitialVariables


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
    state_storage_indexes = dict(
        sorted((state_variable_indexes | numeric_slot_variable_indexes).items(), key=lambda item: item[1])
    )

    globals_block = render_driver_globals(input_files, field_separator, initial_variables or [])
    state_setup = render_driver_state_setup(state_storage_indexes, initial_variables or [])
    scalar_preassignments = render_driver_scalar_preassignments(
        state_storage_indexes,
        slot_variable_indexes,
        string_slot_variable_indexes,
        initial_variables or [],
    )
    record_loop = render_driver_record_loop(consumes_main_input, has_record_phase)

    declarations = execution_driver_declarations(state_type)
    return "\n".join(
        [
            *declarations,
            "",
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
                globals_block.append(
                    declare_bytes(driver_scalar_value_global(index), value.encode("utf-8") + b"\x00")
                )
            continue
        seen_scalars.add(name)
        global_name, _ = driver_scalar_name_global(name)
        globals_block.append(declare_bytes(global_name, name.encode("utf-8") + b"\x00"))
        if isinstance(value, str):
            globals_block.append(
                declare_bytes(driver_scalar_value_global(index), value.encode("utf-8") + b"\x00")
            )

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
        numeric_value = (
            format_double_literal(awk_numeric_prefix(value))
            if isinstance(value, str)
            else format_double_literal(value)
        )
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
                    (
                        f"  call void @qk_scalar_set_string("
                        f"ptr %rt, ptr %preassign.name.{index}, ptr %preassign.value.{index})"
                    ),
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
            (
                f"  call void @qk_scalar_set_number_inline("
                f"ptr %rt, ptr %preassign.name.{index}, double {format_double_literal(value)})"
            )
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
