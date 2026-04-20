from __future__ import annotations

from ..ast import Action, ExitStmt, ExprPattern, FunctionDef, NextFileStmt, NextStmt, Program, RangePattern, ReturnStmt
from ..local_scalar_residency import classify_local_numeric_scalar_residency
from ..normalization import NormalizedLoweringProgram
from ..slot_allocation import SlotAllocation
from ..type_inference import LatticeType
from .lower_expr import lower_record_pattern
from .lower_lvalue import lower_runtime_constant_string
from .lower_stmt import lower_statement
from .runtime_abi import render_reusable_function, render_runtime_user_function, reusable_program_declarations
from .state import LoweringState


def lower_runtime_user_functions_to_ir(
    program: Program,
    variable_indexes: dict[str, int],
    slot_allocation: SlotAllocation,
    type_info: dict[str, LatticeType],
    array_names: frozenset[str],
) -> tuple[list[str], list[str], int]:
    """Lower supported runtime-backed user-defined functions."""
    function_defs = {item.name: item for item in program.items if isinstance(item, FunctionDef)}
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
            function_param_strings={},
            local_names=frozenset(function_def.params),
        )
        for index, param in enumerate(function_def.params):
            param_slot = f"%arg.slot.{index}"
            function_state.allocas.append(f"  {param_slot} = alloca ptr")
            function_state.instructions.append(f"  store ptr %arg.{index}, ptr {param_slot}")
            function_state.function_param_strings[param] = param_slot
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
    local_scalar_residency = classify_local_numeric_scalar_residency(program, normalized_program, type_info)
    declarations = reusable_program_declarations(state_type)

    function_globals, function_bodies, function_string_index = lower_runtime_user_functions_to_ir(
        program, variable_indexes, normalized_program.slot_allocation, type_info, array_names
    )

    function_defs = {item.name: item for item in program.items if isinstance(item, FunctionDef)}
    begin_state = LoweringState(
        runtime_param="%rt",
        state_param="%state",
        variable_indexes=variable_indexes,
        slot_allocation=normalized_program.slot_allocation,
        type_info=type_info,
        array_names=array_names,
        function_defs=function_defs,
        string_index=function_string_index,
        local_numeric_names=local_scalar_residency.names_for_phase("begin"),
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
        function_defs=function_defs,
        local_numeric_names=local_scalar_residency.names_for_phase("record"),
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
        function_defs=function_defs,
        local_numeric_names=local_scalar_residency.names_for_phase("end"),
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
    from .lower_lvalue import variable_address

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


def render_state_type(slot_allocation: SlotAllocation) -> str | None:
    """Render `%quawk.state` from slot-allocation metadata when slots exist."""
    if slot_allocation.variable_count == 0:
        return None
    return slot_allocation.state_struct_type
