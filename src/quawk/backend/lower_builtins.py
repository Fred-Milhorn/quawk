from __future__ import annotations

from ..ast import (
    ArrayLValue,
    CallExpr,
    Expr,
    FieldExpr,
    FieldLValue,
    NameExpr,
    NameLValue,
    StringLiteralExpr,
    expression_to_lvalue,
)
from .lower_lvalue import (
    lower_runtime_argument_string,
    lower_runtime_assign_string_lvalue,
    lower_runtime_captured_string_expression,
    lower_runtime_constant_string,
    lower_runtime_string_expression,
)
from .state import LoweringState


def lower_runtime_unary_numeric_builtin(
    expression: CallExpr,
    state: LoweringState,
    runtime_function: str,
    builtin_name: str,
) -> str:
    """Lower one one-argument numeric builtin in the runtime-backed backend subset."""
    from .lower_expr import lower_runtime_numeric_expression

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
    from .lower_expr import lower_runtime_numeric_expression

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
    from .lower_expr import lower_runtime_numeric_expression

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


def lower_runtime_index_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `index` builtin call in the runtime-backed backend subset."""
    assert state.runtime_param is not None
    if len(expression.args) != 2:
        raise RuntimeError("builtin index expects two arguments")
    text_ptr = lower_runtime_captured_string_expression(expression.args[0], state)
    search_ptr = lower_runtime_captured_string_expression(expression.args[1], state)
    result = state.next_temp("index")
    state.instructions.append(
        f"  {result} = call double @qk_index(ptr {state.runtime_param}, ptr {text_ptr}, ptr {search_ptr})"
    )
    return result


def lower_runtime_match_builtin(expression: CallExpr, state: LoweringState) -> str:
    """Lower one `match` builtin call in the runtime-backed backend subset."""
    from .lower_expr import lower_runtime_regex_pattern

    assert state.runtime_param is not None
    if len(expression.args) != 2:
        raise RuntimeError("builtin match expects two arguments")
    text_ptr = lower_runtime_captured_string_expression(expression.args[0], state)
    pattern_ptr = lower_runtime_regex_pattern(expression.args[1], state)
    result = state.next_temp("match")
    state.instructions.append(
        f"  {result} = call double @qk_match(ptr {state.runtime_param}, ptr {text_ptr}, ptr {pattern_ptr})"
    )
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
    from .lower_expr import lower_runtime_numeric_expression

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


def lower_runtime_substitute_builtin(expression: CallExpr, state: LoweringState, *, global_replace: bool) -> str:
    """Lower one `sub` or `gsub` builtin call in the runtime-backed backend subset."""
    from .lower_expr import lower_runtime_regex_pattern

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
                target_value = lower_runtime_captured_string_expression(
                    NameExpr(name=name, span=target_expr.span), state
                )
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
    captured_result = state.next_temp("sub.result.capture")
    state.instructions.append(
        f"  {captured_result} = call ptr @qk_capture_string_arg_inline(ptr {state.runtime_param}, ptr {result_ptr})"
    )
    lower_runtime_assign_string_lvalue(target_lvalue, captured_result, state)
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
    from .lower_expr import lower_runtime_numeric_expression
    from .lower_lvalue import runtime_expression_has_string_result

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


def lower_runtime_user_function_call(function_name: str, args: tuple[Expr, ...], state: LoweringState) -> str:
    """Lower one runtime-backed user-defined function call to a string result pointer."""
    function_def = state.function_defs.get(function_name)
    if function_def is None:
        raise RuntimeError(f"unsupported function call in runtime-backed backend: {function_name}")
    if len(args) > len(function_def.params):
        raise RuntimeError(
            f"function {function_name} expects at most {len(function_def.params)} arguments, got {len(args)}"
        )
    call_args = [f"ptr {state.runtime_param}", f"ptr {state.state_param or 'null'}"]
    for argument in args:
        call_args.append(f"ptr {lower_runtime_argument_string(argument, state)}")
    missing_args = len(function_def.params) - len(args)
    for _ in range(missing_args):
        call_args.append(f"ptr {lower_runtime_constant_string('', state)}")
    result = state.next_temp("fncall")
    state.instructions.append(f"  {result} = call ptr @qk_fn_{function_name}({', '.join(call_args)})")
    return result
