from __future__ import annotations

from ..ast import (
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    BinaryExpr,
    BinaryOp,
    CallExpr,
    ConditionalExpr,
    Expr,
    FieldExpr,
    FieldLValue,
    NameExpr,
    NameLValue,
    NumericLiteralExpr,
    PostfixExpr,
    PostfixOp,
    RegexLiteralExpr,
    StringLiteralExpr,
    UnaryExpr,
    UnaryOp,
)
from ..builtins import is_builtin_variable_name
from ..type_inference import LatticeType
from .driver import is_reusable_runtime_state_name
from .ir_builder import LLVMIRBuilder
from .runtime_abi import awk_string_is_numeric, declare_string, format_double_literal
from .state import InitialVariables, LoweringState


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
        if runtime_name_uses_local_numeric_storage(name, state):
            slot_name = state.next_temp(f"localvar.{name}")
            state.allocas.append(f"  {slot_name} = alloca double")
            state.entry_instructions.append(f"  store double 0.000000000000000e+00, ptr {slot_name}")
            state.variable_slots[name] = slot_name
            return slot_name
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
    state.entry_instructions.append(f"  store double 0.000000000000000e+00, ptr {slot_name}")
    state.variable_slots[name] = slot_name
    return slot_name


def lower_runtime_constant_string(value: str, state: LoweringState) -> str:
    """Lower one compile-time string constant to a runtime pointer."""
    global_name, byte_length = declare_string(state, value)
    return LLVMIRBuilder(state).gep("strptr", byte_length, global_name)


def lower_runtime_scalar_name(name: str, state: LoweringState) -> str:
    """Lower one scalar variable name to a runtime string pointer."""
    return lower_runtime_constant_string(name, state)


def lower_runtime_string_from_numeric_value(numeric_value: str, state: LoweringState) -> str:
    """Format one numeric runtime value as a captured string pointer."""
    formatted = state.next_temp("numstr")
    captured = state.next_temp("numstr.capture")
    state.instructions.append(
        f"  {formatted} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})"
    )
    state.instructions.append(
        f"  {captured} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {formatted})"
    )
    return captured


def load_runtime_function_param_string(name: str, state: LoweringState) -> str:
    """Load one mutable runtime function parameter/local string value from its slot."""
    slot_name = state.function_param_strings[name]
    temp = state.next_temp("param.str")
    state.instructions.append(f"  {temp} = load ptr, ptr {slot_name}")
    return temp


def store_runtime_function_param_string(name: str, string_value: str, state: LoweringState) -> None:
    """Store one mutable runtime function parameter/local string value back to its slot."""
    slot_name = state.function_param_strings[name]
    captured_value = state.next_temp("param.str.capture")
    state.instructions.append(
        f"  {captured_value} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {string_value})"
    )
    state.instructions.append(f"  store ptr {captured_value}, ptr {slot_name}")


def lower_runtime_argument_string(expression: Expr, state: LoweringState) -> str:
    """Lower one runtime-backed call argument to a captured string pointer."""
    from .lower_expr import lower_runtime_numeric_expression

    if runtime_expression_has_string_result(expression, state):
        return lower_runtime_captured_string_expression(expression, state)
    return lower_runtime_string_from_numeric_value(lower_runtime_numeric_expression(expression, state), state)


def runtime_name_slot_index(name: str, state: LoweringState) -> int | None:
    """Return the runtime numeric-slot index for one known scalar variable name."""
    if (is_builtin_variable_name(name) or name in state.loop_string_bindings or name in state.function_param_strings
            or is_reusable_runtime_state_name(name)):
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
        name not in {"NR", "FNR", "NF", "FILENAME"} and name not in state.loop_string_bindings
        and name not in state.function_param_strings and not is_reusable_runtime_state_name(name)
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
        state.state_param is not None and runtime_name_uses_scalar_runtime(name, state)
        and runtime_name_is_inferred_numeric(name, state) and runtime_name_slot_index(name, state) is not None
    )


def runtime_name_uses_local_numeric_storage(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use function-local numeric storage."""
    return (
        state.state_param is not None and name in state.local_numeric_names
        and runtime_name_uses_scalar_runtime(name, state) and runtime_name_is_inferred_numeric(name, state)
    )


def runtime_name_uses_string_slot_runtime(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use runtime string-slot access."""
    return (
        runtime_name_uses_scalar_runtime(name, state) and runtime_name_is_inferred_string(name, state)
        and runtime_name_slot_index(name, state) is not None
    )


def runtime_name_uses_slot_cached_runtime(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use cached runtime slot access."""
    return (
        runtime_name_uses_scalar_runtime(name, state)
        and runtime_name_slot_index(name, state) is not None
        and not runtime_name_uses_numeric_slot_state(name, state)
        and not runtime_name_uses_local_numeric_storage(name, state)
    )


def runtime_name_uses_only_scalar_runtime(name: str, state: LoweringState) -> bool:
    """Report whether one scalar name should use scalar runtime helpers only."""
    return (
        runtime_name_uses_scalar_runtime(name, state) and not runtime_name_uses_numeric_slot_state(name, state)
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
                name in state.loop_string_bindings or name in state.function_param_strings
                or runtime_name_is_inferred_string(name, state)
            )
        case CallExpr(function=function_name) if function_name in state.function_defs:
            return True
        case CallExpr(function="sprintf" | "substr" | "tolower" | "toupper"):
            return True
        case BinaryExpr(op=BinaryOp.CONCAT):
            return True
        case AssignExpr(op=_, target=_, value=value):
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
        case AssignExpr(op=_, target=NameLValue(name=name), value=value):
            return is_reusable_runtime_state_name(name) and runtime_expression_is_definitely_numeric(value, state)
        case UnaryExpr(op=UnaryOp.UPLUS | UnaryOp.UMINUS | UnaryOp.NOT, operand=operand):
            return runtime_expression_is_definitely_numeric(operand, state)
        case UnaryExpr(
            op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC, operand=NameExpr() | FieldExpr() | ArrayIndexExpr(extra_indexes=())
        ):
            return True
        case PostfixExpr(
            op=PostfixOp.POST_INC | PostfixOp.POST_DEC,
            operand=NameExpr() | FieldExpr() | ArrayIndexExpr(extra_indexes=())
        ):
            return True
        case BinaryExpr(
            op=BinaryOp.ADD | BinaryOp.SUB | BinaryOp.MUL | BinaryOp.DIV | BinaryOp.MOD | BinaryOp.POW,
            left=left,
            right=right,
        ):
            return runtime_expression_is_definitely_numeric(left, state) and runtime_expression_is_definitely_numeric(
                right, state
            )
        case CallExpr(
            function="int" | "length" | "rand" | "srand" | "atan2" | "cos" | "exp" | "log" | "match" | "sin" | "sqrt"
            | "split" | "sub" | "gsub" | "system",
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
        case NameExpr(name=name) if name in state.function_param_strings:
            return True
        case NameExpr(name=name):
            return runtime_name_uses_only_scalar_runtime(name,
                                                         state) or runtime_name_uses_string_slot_runtime(name, state)
        case _:
            return runtime_expression_is_known_string(expression, state)


def runtime_expression_has_string_result(expression: Expr, state: LoweringState | None = None) -> bool:
    """Report whether one runtime-backed expression lowers as a string result."""
    match expression:
        case StringLiteralExpr() | FieldExpr() | ArrayIndexExpr():
            return True
        case NameExpr(name="FILENAME"):
            return True
        case NameExpr(name=name):
            return state is not None and (
                name in state.loop_string_bindings or name in state.function_param_strings
                or runtime_name_uses_only_scalar_runtime(name, state)
                or runtime_name_uses_string_slot_runtime(name, state)
            )
        case CallExpr(function=function_name) if state is not None and function_name in state.function_defs:
            return True
        case CallExpr(function="sprintf" | "substr" | "tolower" | "toupper"):
            return True
        case BinaryExpr(op=BinaryOp.CONCAT):
            return True
        case AssignExpr(op=_, target=_, value=value):
            return state is not None and runtime_assignment_preserves_string(value, state)
        case ConditionalExpr(test=_, if_true=if_true, if_false=if_false):
            return runtime_expression_has_string_result(if_true, state
                                                        ) and runtime_expression_has_string_result(if_false, state)
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


def runtime_expression_has_side_effects(expression: Expr, state: LoweringState) -> bool:
    """Report whether lowering one expression may mutate runtime-visible state."""
    match expression:
        case AssignExpr():
            return True
        case UnaryExpr(op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC):
            return True
        case PostfixExpr(op=PostfixOp.POST_INC | PostfixOp.POST_DEC):
            return True
        case CallExpr(function="split" | "sub" | "gsub" | "close" | "match" | "rand" | "srand" | "system"):
            return True
        case CallExpr(function=function_name) if function_name in state.function_defs:
            return True
        case BinaryExpr(left=left, right=right):
            return runtime_expression_has_side_effects(left, state) or runtime_expression_has_side_effects(right, state)
        case UnaryExpr(operand=operand):
            return runtime_expression_has_side_effects(operand, state)
        case PostfixExpr(operand=operand):
            return runtime_expression_has_side_effects(operand, state)
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            return (
                runtime_expression_has_side_effects(test, state) or runtime_expression_has_side_effects(if_true, state)
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


def lower_runtime_array_key(expression: Expr, state: LoweringState) -> str:
    """Lower one array key expression to a string pointer."""
    from .lower_expr import lower_runtime_numeric_expression

    match expression:
        case NameExpr(name=name) if name in state.loop_string_bindings:
            return state.loop_string_bindings[name]
        case NumericLiteralExpr(value=value):
            temp = state.next_temp("array.key.num")
            state.instructions.append(
                f"  {temp} = call ptr @qk_format_number(ptr {state.runtime_param}, double {format_double_literal(value)})"
            )
            return temp
        case StringLiteralExpr(value=value):
            return lower_runtime_constant_string(value, state)
        case _:
            if runtime_expression_has_string_result(expression, state):
                return lower_runtime_string_expression(expression, state)
            numeric_value = lower_runtime_numeric_expression(expression, state)
            formatted = state.next_temp("array.key.num")
            state.instructions.append(
                f"  {formatted} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})"
            )
            return formatted


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
    return key_value


def lower_runtime_field_index(index: int | Expr, state: LoweringState) -> str:
    """Lower one field index to an `i64` operand."""
    from .lower_expr import lower_runtime_numeric_expression

    if isinstance(index, int):
        return str(index)
    numeric_value = lower_runtime_numeric_expression(index, state)
    integer_value = state.next_temp("field.index")
    state.instructions.append(f"  {integer_value} = fptosi double {numeric_value} to i64")
    return integer_value


def lower_runtime_assign_string_lvalue(
    target: NameLValue | ArrayLValue | FieldLValue, string_value: str, state: LoweringState
) -> None:
    """Assign one runtime string result back through a supported lvalue."""
    assert state.runtime_param is not None
    match target:
        case NameLValue(name=name):
            if name in state.function_param_strings:
                store_runtime_function_param_string(name, string_value, state)
                return
            slot_index = runtime_name_slot_index(name, state)
            if runtime_name_uses_string_slot_runtime(name, state):
                assert slot_index is not None
                state.instructions.append(
                    f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                )
            else:
                scalar_name = lower_runtime_scalar_name(name, state)
                state.instructions.append(
                    f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {scalar_name}, ptr {string_value})"
                )
                if slot_index is not None:
                    state.instructions.append(
                        f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                    )
        case FieldLValue(index=index):
            index_value = lower_runtime_field_index(index, state)
            state.instructions.append(
                f"  call void @qk_set_field_string(ptr {state.runtime_param}, i64 {index_value}, ptr {string_value})"
            )
        case ArrayLValue(name=name, subscripts=subscripts):
            array_name_ptr = lower_runtime_constant_string(name, state)
            key_ptr = lower_runtime_array_subscripts(subscripts, state)
            state.instructions.append(
                f"  call void @qk_array_set_string(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, ptr {string_value})"
            )
        case _:
            raise RuntimeError("unsupported string assignment target in the runtime-backed backend")


def lower_runtime_captured_string_expression(expression: Expr, state: LoweringState) -> str:
    """Lower one string expression and capture a stable copy for multi-arg runtime calls."""
    string_value = lower_runtime_string_expression(expression, state)
    captured = state.next_temp("str.capture")
    state.instructions.append(
        f"  {captured} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {string_value})"
    )
    return captured


def lower_runtime_string_expression(expression: Expr, state: LoweringState) -> str:
    from .lower_expr import lower_runtime_string_expression as lower

    return lower(expression, state)
