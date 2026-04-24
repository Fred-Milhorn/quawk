from __future__ import annotations

import re

from ..ast import (
    AssignOp,
    AssignStmt,
    BlockStmt,
    BreakStmt,
    ContinueStmt,
    DeleteStmt,
    DoWhileStmt,
    ExitStmt,
    Expr,
    ExprStmt,
    ForInStmt,
    ForStmt,
    IfStmt,
    NameExpr,
    NextFileStmt,
    NextStmt,
    OutputRedirect,
    OutputRedirectKind,
    PrintfStmt,
    PrintStmt,
    ReturnStmt,
    Stmt,
    StringLiteralExpr,
    WhileStmt,
)
from .driver import is_reusable_runtime_state_name
from .ir_builder import LLVMIRBuilder
from .lower_expr import (
    lower_condition_expression,
    lower_numeric_expression,
    lower_runtime_numeric_expression,
    lower_runtime_string_expression,
)
from .lower_lvalue import (
    load_runtime_function_param_string,
    lower_runtime_array_subscripts,
    lower_runtime_captured_string_expression,
    lower_runtime_constant_string,
    lower_runtime_field_index,
    lower_runtime_scalar_name,
    lower_runtime_string_from_numeric_value,
    runtime_assignment_preserves_string,
    runtime_expression_has_string_result,
    runtime_name_slot_index,
    runtime_name_uses_local_numeric_storage,
    runtime_name_uses_numeric_slot_state,
    runtime_name_uses_scalar_runtime,
    runtime_name_uses_slot_cached_runtime,
    runtime_name_uses_string_slot_runtime,
    store_runtime_function_param_string,
    variable_address,
)
from .runtime_abi import declare_string, emit_gep, ensure_numeric_format
from .state import LoweringState

OUTPUT_REDIRECT_WRITE = 1
OUTPUT_REDIRECT_APPEND = 2
OUTPUT_REDIRECT_PIPE = 3
PRINTF_SPEC_PATTERN = re.compile(r"%(?:[-+ #0]*\d*(?:\.\d+)?)([%aAcdeEfgGiosuxX])")


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
                raise RuntimeError("delete statements are not supported in the internal non-runtime lowering path")
            lower_runtime_delete_statement(statement, state)
        case IfStmt():
            lower_if_statement(statement, state)
        case DoWhileStmt():
            lower_do_while_statement(statement, state)
        case WhileStmt():
            lower_while_statement(statement, state)
        case ForStmt():
            if state.runtime_param is None:
                raise RuntimeError("for statements are not supported in the internal non-runtime lowering path")
            lower_runtime_for_statement(statement, state)
        case ForInStmt():
            if state.runtime_param is None:
                raise RuntimeError("for-in statements are not supported in the internal non-runtime lowering path")
            lower_runtime_for_in_statement(statement, state)
        case ReturnStmt():
            if state.return_label is None:
                raise RuntimeError("return statements are not supported in this lowering context")
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
                raise RuntimeError("return statements are not supported in this lowering context")
            return_value = (
                "0.000000000000000e+00"
                if statement.value is None else lower_numeric_expression(statement.value, state)
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
                    raise RuntimeError("the internal non-runtime lowering path only supports print with one argument")
                lower_print_expression(arguments[0], state)
        case PrintfStmt():
            if state.runtime_param is None:
                raise RuntimeError("printf statements are not supported in the internal non-runtime lowering path")
            lower_runtime_printf_statement(statement, state)
        case ExprStmt(value=value):
            if state.runtime_param is None:
                raise RuntimeError("expression statements are not supported in the internal non-runtime lowering path")
            lower_runtime_side_effect_expression(value, state)
        case NextStmt():
            if state.runtime_param is None or state.phase_exit_label is None:
                raise RuntimeError("next is not supported in the internal non-runtime lowering path")
            state.instructions.append(f"  br label %{state.phase_exit_label}")
        case NextFileStmt():
            if state.runtime_param is None or state.phase_exit_label is None:
                raise RuntimeError("nextfile is not supported in the internal non-runtime lowering path")
            state.instructions.extend(
                [
                    f"  call void @qk_nextfile(ptr {state.runtime_param})",
                    f"  br label %{state.phase_exit_label}",
                ]
            )
        case ExitStmt(value=value):
            if state.runtime_param is None:
                raise RuntimeError("exit is not supported in the internal non-runtime lowering path")
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
                raise RuntimeError("exit is not supported in this lowering context")
        case _:
            raise RuntimeError("the current backend only supports print, assignment, block, if, and while statements")


def lower_if_statement(statement: IfStmt, state: LoweringState) -> None:
    """Lower an `if` statement with a single then-branch."""
    builder = LLVMIRBuilder(state)
    then_label = builder.label("if.then")
    else_label = builder.label("if.else") if statement.else_branch is not None else None
    end_label = builder.label("if.end")
    condition = lower_condition_expression(statement.condition, state)
    false_target = end_label if else_label is None else else_label
    builder.cond_branch(condition, then_label, false_target)
    builder.mark_label(then_label)
    lower_statement(statement.then_branch, state)
    builder.branch(end_label)
    if statement.else_branch is not None and else_label is not None:
        builder.mark_label(else_label)
        lower_statement(statement.else_branch, state)
        builder.branch(end_label)
    builder.mark_label(end_label)


def lower_while_statement(statement: WhileStmt, state: LoweringState) -> None:
    """Lower a `while` loop over the current numeric condition subset."""
    builder = LLVMIRBuilder(state)
    cond_label = builder.label("while.cond")
    body_label = builder.label("while.body")
    end_label = builder.label("while.end")
    builder.branch(cond_label)
    builder.mark_label(cond_label)
    condition = lower_condition_expression(statement.condition, state)
    builder.cond_branch(condition, body_label, end_label)
    builder.mark_label(body_label)
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = cond_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
    builder.branch(cond_label)
    builder.mark_label(end_label)


def lower_do_while_statement(statement: DoWhileStmt, state: LoweringState) -> None:
    """Lower a `do ... while` loop in the current backend subset."""
    builder = LLVMIRBuilder(state)
    body_label = builder.label("dowhile.body")
    cond_label = builder.label("dowhile.cond")
    end_label = builder.label("dowhile.end")
    builder.branch(body_label)
    builder.mark_label(body_label)
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = cond_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
    builder.branch(cond_label)
    builder.mark_label(cond_label)
    condition = lower_condition_expression(statement.condition, state)
    builder.cond_branch(condition, body_label, end_label)
    builder.mark_label(end_label)


def lower_assignment_statement(statement: AssignStmt, state: LoweringState) -> None:
    """Lower a scalar numeric assignment."""
    if statement.op is not statement.op.PLAIN:
        raise RuntimeError("compound assignments are not supported in the internal non-runtime lowering path")
    if statement.name is None:
        raise RuntimeError("non-scalar assignments are not supported in the internal non-runtime lowering path")
    if statement.index is not None or statement.extra_indexes:
        raise RuntimeError("array assignments are not supported in the internal non-runtime lowering path")
    slot_name = variable_address(statement.name, state)
    state.initial_string_values.pop(statement.name, None)
    numeric_value = lower_numeric_expression(statement.value, state)
    LLVMIRBuilder(state).store("double", numeric_value, slot_name)


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
    if statement.name in state.function_param_strings:
        if statement.op is AssignOp.PLAIN and runtime_assignment_preserves_string(statement.value, state):
            store_runtime_function_param_string(
                statement.name, lower_runtime_string_expression(statement.value, state), state
            )
            return
        current_ptr = load_runtime_function_param_string(statement.name, state)
        current_value = state.next_temp("param.current.num")
        state.instructions.append(f"  {current_value} = call double @qk_parse_number_text(ptr {current_ptr})")
        numeric_value = lower_runtime_numeric_expression(statement.value, state)
        numeric_value = combine_numeric_assignment(current_value, numeric_value)
        store_runtime_function_param_string(
            statement.name, lower_runtime_string_from_numeric_value(numeric_value, state), state
        )
        return

    if statement.index is not None:
        array_name_ptr = lower_runtime_constant_string(statement.name, state)
        key_ptr = lower_runtime_array_subscripts((statement.index, *statement.extra_indexes), state)
        if statement.op is AssignOp.PLAIN and runtime_assignment_preserves_string(statement.value, state):
            string_value = lower_runtime_string_expression(statement.value, state)
            state.instructions.append(
                f"  call void @qk_array_set_string(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, ptr {string_value})"
            )
            return
        current_value = state.next_temp("array.current.num")
        state.instructions.append(
            f"  {current_value} = call double @qk_array_get_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
        )
        numeric_value = lower_runtime_numeric_expression(statement.value, state)
        numeric_value = combine_numeric_assignment(current_value, numeric_value)
        state.instructions.append(
            f"  call void @qk_array_set_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {numeric_value})"
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
        and not runtime_name_uses_local_numeric_storage(statement.value.name, state)
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
            state.instructions.append(
                f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
            )
            return
        state.instructions.append(
            f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {target_name}, ptr {string_value})"
        )
        if slot_index is not None:
            state.instructions.append(
                f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
            )
        return

    current_value = state.next_temp("scalar.current")
    if runtime_name_uses_slot_cached_runtime(statement.name, state):
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
    if runtime_name_uses_slot_cached_runtime(statement.name, state):
        assert slot_index is not None
        state.instructions.append(
            f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
        )
    state.instructions.append(
        f"  call void @qk_scalar_set_number_inline(ptr {state.runtime_param}, ptr {target_name}, double {numeric_value})"
    )


def lower_runtime_delete_statement(statement: DeleteStmt, state: LoweringState) -> None:
    """Lower one runtime-backed array delete statement."""
    assert state.runtime_param is not None
    array_name = statement.array_name
    if array_name is None:
        raise RuntimeError("delete requires a named array target in the runtime-backed backend")
    array_name_ptr = lower_runtime_constant_string(array_name, state)
    if statement.index is None:
        state.instructions.append(f"  call void @qk_array_clear(ptr {state.runtime_param}, ptr {array_name_ptr})")
        return
    key_ptr = lower_runtime_array_subscripts((statement.index, *statement.extra_indexes), state)
    state.instructions.append(
        f"  call void @qk_array_delete(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
    )


def lower_runtime_for_statement(statement: ForStmt, state: LoweringState) -> None:
    """Lower one runtime-backed classic `for` statement."""
    for init_expression in statement.init:
        lower_runtime_side_effect_expression(init_expression, state)
    cond_label = state.next_label("for.cond")
    body_label = state.next_label("for.body")
    step_label = state.next_label("for.step")
    end_label = state.next_label("for.end")
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{cond_label}:")
    condition = "true" if statement.condition is None else lower_condition_expression(statement.condition, state)
    state.instructions.append(f"  br i1 {condition}, label %{body_label}, label %{end_label}")
    state.instructions.append(f"{body_label}:")
    previous_break_label = state.break_label
    previous_continue_label = state.continue_label
    state.break_label = end_label
    state.continue_label = step_label
    try:
        lower_statement(statement.body, state)
    finally:
        state.break_label = previous_break_label
        state.continue_label = previous_continue_label
    state.instructions.append(f"  br label %{step_label}")
    state.instructions.append(f"{step_label}:")
    for update_expression in statement.update:
        lower_runtime_side_effect_expression(update_expression, state)
    state.instructions.append(f"  br label %{cond_label}")
    state.instructions.append(f"{end_label}:")


def lower_runtime_for_in_statement(statement: ForInStmt, state: LoweringState) -> None:
    """Lower one runtime-backed `for (name in array)` loop."""
    assert state.runtime_param is not None
    array_name = statement.array_name
    if array_name is None:
        raise RuntimeError("for-in iteration requires a named array in the runtime-backed backend")
    array_name_ptr = lower_runtime_constant_string(array_name, state)
    key_slot = state.next_temp("forin.slot")
    first_key = state.next_temp("forin.first")
    current_key = state.next_temp("forin.key")
    has_key = state.next_temp("forin.has")
    cond_label = state.next_label("forin.cond")
    body_label = state.next_label("forin.body")
    step_label = state.next_label("forin.step")
    end_label = state.next_label("forin.end")
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
    next_key = state.next_temp("forin.next")
    state.instructions.extend(
        [
            f"  br label %{step_label}",
            f"{step_label}:",
            f"  {next_key} = call ptr @qk_array_next_key(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {current_key})",
            f"  store ptr {next_key}, ptr {key_slot}",
            f"  br label %{cond_label}",
            f"{end_label}:",
        ]
    )


def lower_print_expression(expression: Expr, state: LoweringState) -> None:
    """Lower one supported `print` expression into side-effecting IR."""
    builder = LLVMIRBuilder(state)
    if (isinstance(expression, NameExpr) and expression.name in state.initial_string_values
            and expression.name not in state.local_names):
        state.uses_puts = True
        global_name, byte_length = declare_string(state, state.initial_string_values[expression.name])
        string_ptr = builder.gep("strptr", byte_length, global_name)
        builder.call("call", "i32", "@puts", [f"ptr {string_ptr}"])
        return
    if isinstance(expression, StringLiteralExpr):
        state.uses_puts = True
        global_name, byte_length = declare_string(state, expression.value)
        string_ptr = builder.gep("strptr", byte_length, global_name)
        builder.call("call", "i32", "@puts", [f"ptr {string_ptr}"])
        return
    state.uses_printf = True
    format_name, format_length = ensure_numeric_format(state)
    format_ptr = builder.gep("fmtptr", format_length, format_name)
    numeric_value = lower_numeric_expression(expression, state)
    builder.call("call", "i32", "@printf", [f"ptr {format_ptr}", f"double {numeric_value}"])


def lower_runtime_print_fragment(expression: Expr, state: LoweringState) -> None:
    """Lower one runtime-backed print argument fragment."""
    if runtime_expression_has_string_result(expression, state):
        string_value = lower_runtime_string_expression(expression, state)
        state.instructions.append(
            f"  call void @qk_print_string_fragment(ptr {state.runtime_param}, ptr {string_value})"
        )
        return
    numeric_value = lower_runtime_numeric_expression(expression, state)
    state.instructions.append(
        f"  call void @qk_print_number_fragment(ptr {state.runtime_param}, double {numeric_value})"
    )


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
                state.instructions.append(
                    f"  call void @qk_write_output_string(ptr {output_handle}, ptr {string_value})"
                )
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
                operands.append(f"ptr {lower_runtime_captured_string_expression(argument, state)}")
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

    format_ptr = lower_runtime_string_expression(format_expression, state)
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
