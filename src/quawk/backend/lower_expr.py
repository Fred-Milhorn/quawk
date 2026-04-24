from __future__ import annotations

from ..ast import (
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignOp,
    BinaryExpr,
    BinaryOp,
    CallExpr,
    ConditionalExpr,
    Expr,
    ExprPattern,
    FieldExpr,
    FieldLValue,
    GetlineExpr,
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
from .driver import is_reusable_runtime_state_name
from .ir_builder import LLVMIRBuilder
from .lower_builtins import (
    lower_runtime_binary_numeric_builtin,
    lower_runtime_case_builtin,
    lower_runtime_close_builtin,
    lower_runtime_index_builtin,
    lower_runtime_length_builtin,
    lower_runtime_match_builtin,
    lower_runtime_rand_builtin,
    lower_runtime_split_builtin,
    lower_runtime_sprintf_builtin,
    lower_runtime_srand_builtin,
    lower_runtime_substitute_builtin,
    lower_runtime_substr_builtin,
    lower_runtime_system_builtin,
    lower_runtime_unary_numeric_builtin,
    lower_runtime_user_function_call,
)
from .lower_lvalue import (
    expression_forces_string_comparison,
    load_runtime_function_param_string,
    lower_runtime_array_subscripts,
    lower_runtime_assign_string_lvalue,
    lower_runtime_captured_string_expression,
    lower_runtime_constant_string,
    lower_runtime_field_index,
    lower_runtime_scalar_name,
    lower_runtime_string_from_numeric_value,
    runtime_assignment_preserves_string,
    runtime_expression_has_side_effects,
    runtime_expression_has_string_result,
    runtime_expression_is_definitely_numeric,
    runtime_expression_is_known_string,
    runtime_name_slot_index,
    runtime_name_uses_local_numeric_storage,
    runtime_name_uses_numeric_slot_state,
    runtime_name_uses_only_scalar_runtime,
    runtime_name_uses_scalar_runtime,
    runtime_name_uses_slot_cached_runtime,
    runtime_name_uses_string_slot_runtime,
    store_runtime_function_param_string,
    variable_address,
)
from .runtime_abi import awk_numeric_prefix, declare_string, emit_gep, format_double_literal
from .state import LoweringState


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


def lower_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower a numeric expression and return the LLVM operand for its value."""
    if isinstance(expression, NumericLiteralExpr):
        return format_double_literal(expression.value)

    if isinstance(expression, StringLiteralExpr):
        return format_double_literal(awk_numeric_prefix(expression.value))

    if isinstance(expression, ArrayIndexExpr):
        raise RuntimeError("array reads are not supported in the internal non-runtime lowering path")

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
        if len(expression.args) > len(function_def.params):
            raise RuntimeError(
                f"function {expression.function} expects at most {len(function_def.params)} arguments, got {len(expression.args)}"
            )
        arguments = [f"ptr {state.state_param}"]
        for argument in expression.args:
            arguments.append(f"double {lower_numeric_expression(argument, state)}")
        missing_args = len(function_def.params) - len(expression.args)
        arguments.extend(["double 0.000000000000000e+00"] * missing_args)
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
            state.instructions.append(
                f"  {temp} = call double @llvm.pow.f64(double {left_operand}, double {right_operand})"
            )
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
        state.instructions.append(
            f"  {select_value} = select i1 {test_value}, double {true_operand}, double {false_operand}"
        )
        return select_value

    raise RuntimeError(
        "the internal non-runtime lowering path only supports numeric literals, variable reads, and the current arithmetic/boolean subset"
    )


def lower_runtime_numeric_expression(expression: Expr, state: LoweringState) -> str:
    """Lower one numeric expression in the runtime-backed backend subset."""
    builder = LLVMIRBuilder(state)
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
                current_ptr = load_runtime_function_param_string(name, state)
                temp = state.next_temp("param.num")
                state.instructions.append(f"  {temp} = call double @qk_parse_number_text(ptr {current_ptr})")
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
            if runtime_name_uses_slot_cached_runtime(name, state):
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
            return builder.binop("neg", "fsub", "double", "0.000000000000000e+00", operand_value)
        case UnaryExpr(op=UnaryOp.NOT, operand=operand):
            condition_value = lower_condition_expression(operand, state)
            return builder.select(
                "notnum",
                condition_value,
                "double",
                "0.000000000000000e+00",
                "1.000000000000000e+00",
            )
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
            return builder.call("fncall.num", "double", "@qk_parse_number_text", [f"ptr {string_value}"])
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
            return builder.binop("add", "fadd", "double", left_operand, right_operand)
        case BinaryExpr(op=BinaryOp.SUB, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            return builder.binop("sub", "fsub", "double", left_operand, right_operand)
        case BinaryExpr(op=BinaryOp.MUL, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            return builder.binop("mul", "fmul", "double", left_operand, right_operand)
        case BinaryExpr(op=BinaryOp.DIV, left=left, right=right):
            left_operand = lower_runtime_numeric_expression(left, state)
            right_operand = lower_runtime_numeric_expression(right, state)
            return builder.binop("div", "fdiv", "double", left_operand, right_operand)
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
            return builder.call(
                "pow",
                "double",
                "@llvm.pow.f64",
                [f"double {left_operand}", f"double {right_operand}"],
            )
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
            temp = builder.temp("boolnum")
            builder.emit(f"  {temp} = uitofp i1 {condition_value} to double")
            return temp
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            if runtime_expression_has_side_effects(if_true, state) or runtime_expression_has_side_effects(if_false,
                                                                                                          state):
                return lower_runtime_numeric_conditional_expression(expression, state)
            test_value = lower_condition_expression(test, state)
            true_operand = lower_runtime_numeric_expression(if_true, state)
            false_operand = lower_runtime_numeric_expression(if_false, state)
            return builder.select("ternary.num", test_value, "double", true_operand, false_operand)
        case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
            array_name_ptr = lower_runtime_constant_string(array_name, state)
            key_ptr = lower_runtime_array_subscripts((index, *extra_indexes), state)
            temp = state.next_temp("array.num")
            state.instructions.append(
                f"  {temp} = call double @qk_array_get_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
            )
            return temp
        case _:
            if runtime_expression_has_string_result(expression, state):
                string_value = lower_runtime_captured_string_expression(expression, state)
                return builder.call("num.coerce", "double", "@qk_parse_number_text", [f"ptr {string_value}"])
            raise RuntimeError("unsupported numeric expression in runtime-backed backend")


def lower_runtime_assignment_expression(expression: AssignExpr, state: LoweringState) -> str:
    """Lower one numeric assignment expression in the runtime-backed backend subset."""

    def combine_numeric_assignment(current_value: str, update_value: str) -> str:
        if expression.op is AssignOp.PLAIN:
            return update_value
        result = state.next_temp("assign.op")
        if expression.op is AssignOp.ADD:
            state.instructions.append(f"  {result} = fadd double {current_value}, {update_value}")
            return result
        if expression.op is AssignOp.SUB:
            state.instructions.append(f"  {result} = fsub double {current_value}, {update_value}")
            return result
        if expression.op is AssignOp.MUL:
            state.instructions.append(f"  {result} = fmul double {current_value}, {update_value}")
            return result
        if expression.op is AssignOp.DIV:
            state.instructions.append(f"  {result} = fdiv double {current_value}, {update_value}")
            return result
        if expression.op is AssignOp.MOD:
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

    target = expression.target
    match target:
        case FieldLValue(index=index):
            index_value = lower_runtime_field_index(index, state)
            assert state.runtime_param is not None
            if expression.op is AssignOp.PLAIN and runtime_assignment_preserves_string(expression.value, state):
                raise RuntimeError(
                    "string-valued field assignment expressions are not supported yet in runtime-backed backend"
                )
            current_field = state.next_temp("field.current")
            current_value = state.next_temp("field.current.num")
            state.instructions.extend(
                [
                    f"  {current_field} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 {index_value})",
                    f"  {current_value} = call double @qk_parse_number_text(ptr {current_field})",
                ]
            )
            numeric_value = lower_runtime_numeric_expression(expression.value, state)
            numeric_value = combine_numeric_assignment(current_value, numeric_value)
            state.instructions.append(
                f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {index_value}, double {numeric_value})"
            )
        case ArrayLValue(name=name, subscripts=subscripts):
            assert state.runtime_param is not None
            array_name_ptr = lower_runtime_constant_string(name, state)
            key_ptr = lower_runtime_array_subscripts(subscripts, state)
            if expression.op is AssignOp.PLAIN and runtime_assignment_preserves_string(expression.value, state):
                raise RuntimeError(
                    "string-valued array assignment expressions are not supported yet in runtime-backed backend"
                )
            current_value = state.next_temp("array.current.num")
            state.instructions.append(
                f"  {current_value} = call double @qk_array_get_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
            )
            numeric_value = lower_runtime_numeric_expression(expression.value, state)
            numeric_value = combine_numeric_assignment(current_value, numeric_value)
            state.instructions.append(
                f"  call void @qk_array_set_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {numeric_value})"
            )
        case NameLValue(name=name):
            if name in state.function_param_strings:
                if expression.op is AssignOp.PLAIN and runtime_assignment_preserves_string(expression.value, state):
                    string_value = lower_runtime_string_expression(expression.value, state)
                    store_runtime_function_param_string(name, string_value, state)
                    numeric_value = state.next_temp("assign.param.num")
                    stored_value = load_runtime_function_param_string(name, state)
                    state.instructions.append(f"  {numeric_value} = call double @qk_parse_number_text(ptr {stored_value})")
                    return numeric_value
                current_ptr = load_runtime_function_param_string(name, state)
                current_value = state.next_temp("param.current.num")
                state.instructions.append(f"  {current_value} = call double @qk_parse_number_text(ptr {current_ptr})")
                numeric_value = lower_runtime_numeric_expression(expression.value, state)
                numeric_value = combine_numeric_assignment(current_value, numeric_value)
                store_runtime_function_param_string(name, lower_runtime_string_from_numeric_value(numeric_value, state), state)
                return numeric_value
            if is_reusable_runtime_state_name(name):
                slot_name = variable_address(name, state)
                current_value = state.next_temp("state.current")
                state.instructions.append(f"  {current_value} = load double, ptr {slot_name}")
                numeric_value = lower_runtime_numeric_expression(expression.value, state)
                numeric_value = combine_numeric_assignment(current_value, numeric_value)
                state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
            elif runtime_name_uses_numeric_slot_state(name, state):
                slot_name = variable_address(name, state)
                current_value = state.next_temp("state.current")
                state.instructions.append(f"  {current_value} = load double, ptr {slot_name}")
                numeric_value = lower_runtime_numeric_expression(expression.value, state)
                numeric_value = combine_numeric_assignment(current_value, numeric_value)
                state.instructions.append(f"  store double {numeric_value}, ptr {slot_name}")
            else:
                slot_index = runtime_name_slot_index(name, state)
                scalar_name = lower_runtime_scalar_name(name, state)
                if (expression.op is AssignOp.PLAIN and isinstance(expression.value, NameExpr)
                        and runtime_name_uses_scalar_runtime(expression.value.name, state)
                        and not runtime_name_uses_local_numeric_storage(expression.value.name, state)
                        and not runtime_name_uses_string_slot_runtime(name, state)):
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
                elif expression.op is AssignOp.PLAIN and runtime_assignment_preserves_string(expression.value, state):
                    string_value = lower_runtime_string_expression(expression.value, state)
                    if runtime_name_uses_string_slot_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                        )
                        numeric_value = state.next_temp("assign.str.num")
                        state.instructions.append(
                            f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})"
                        )
                        state.instructions.append(
                            f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
                        )
                    else:
                        state.instructions.append(
                            f"  call void @qk_scalar_set_string(ptr {state.runtime_param}, ptr {scalar_name}, ptr {string_value})"
                        )
                        if slot_index is not None:
                            numeric_value = state.next_temp("assign.str.slot")
                            state.instructions.append(
                                f"  {numeric_value} = call double @qk_parse_number_text(ptr {string_value})"
                            )
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
                    current_value = state.next_temp("scalar.current")
                    if runtime_name_uses_slot_cached_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            f"  {current_value} = call double @qk_slot_get_number(ptr {state.runtime_param}, i64 {slot_index})"
                        )
                    else:
                        state.instructions.append(
                            f"  {current_value} = call double @qk_scalar_get_number_inline(ptr {state.runtime_param}, ptr {scalar_name})"
                        )
                    numeric_value = lower_runtime_numeric_expression(expression.value, state)
                    numeric_value = combine_numeric_assignment(current_value, numeric_value)
                    if runtime_name_uses_slot_cached_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {numeric_value})"
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
            if name in state.function_param_strings:
                current_ptr = load_runtime_function_param_string(name, state)
                old_value = state.next_temp("inc.old")
                new_value = state.next_temp("inc.new")
                state.instructions.append(f"  {old_value} = call double @qk_parse_number_text(ptr {current_ptr})")
                state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
                store_runtime_function_param_string(
                    name, lower_runtime_string_from_numeric_value(new_value, state), state
                )
                return old_value if return_old else new_value
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
            if runtime_name_uses_slot_cached_runtime(name, state):
                assert slot_index is not None
                state.instructions.append(
                    f"  {old_value} = call double @qk_slot_get_number(ptr {state.runtime_param}, i64 {slot_index})"
                )
            else:
                state.instructions.append(
                    f"  {old_value} = call double @qk_scalar_get_number_inline(ptr {state.runtime_param}, ptr {scalar_name})"
                )
            state.instructions.append(f"  {new_value} = {opcode} double {old_value}, {amount}")
            if runtime_name_uses_slot_cached_runtime(name, state):
                assert slot_index is not None
                state.instructions.append(
                    f"  call void @qk_slot_set_number(ptr {state.runtime_param}, i64 {slot_index}, double {new_value})"
                )
            state.instructions.append(
                f"  call void @qk_scalar_set_number_inline(ptr {state.runtime_param}, ptr {scalar_name}, double {new_value})"
            )
            return old_value if return_old else new_value
        case FieldExpr(index=index):
            index_value = lower_runtime_field_index(index, state)
            old_text = state.next_temp("inc.field")
            old_value = state.next_temp("inc.old")
            new_value = state.next_temp("inc.new")
            state.instructions.extend(
                [
                    f"  {old_text} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 {index_value})",
                    f"  {old_value} = call double @qk_parse_number_text(ptr {old_text})",
                    f"  {new_value} = {opcode} double {old_value}, {amount}",
                    f"  call void @qk_set_field_number(ptr {state.runtime_param}, i64 {index_value}, double {new_value})",
                ]
            )
            return old_value if return_old else new_value
        case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
            array_name_ptr = lower_runtime_constant_string(array_name, state)
            key_ptr = lower_runtime_array_subscripts((index, *extra_indexes), state)
            old_value = state.next_temp("inc.old")
            new_value = state.next_temp("inc.new")
            state.instructions.extend(
                [
                    f"  {old_value} = call double @qk_array_get_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})",
                    f"  {new_value} = {opcode} double {old_value}, {amount}",
                    f"  call void @qk_array_set_number(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, double {new_value})",
                ]
            )
            return old_value if return_old else new_value
        case _:
            raise RuntimeError("unsupported increment/decrement target in runtime-backed backend")


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
            return load_runtime_function_param_string(name, state)
        case NameExpr(name="FILENAME"):
            temp = state.next_temp("filename")
            state.instructions.append(f"  {temp} = call ptr @qk_get_filename_inline(ptr {state.runtime_param})")
            return temp
        case NameExpr(name=name):
            if runtime_name_uses_slot_cached_runtime(name, state):
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
                    stored_value = state.next_temp("assign.field.str")
                    state.instructions.append(
                        f"  {stored_value} = call ptr @qk_get_field_inline(ptr {state.runtime_param}, i64 {field_index})"
                    )
                    return stored_value
                case ArrayLValue(name=name, subscripts=subscripts) if runtime_assignment_preserves_string(value, state):
                    array_name_ptr = lower_runtime_constant_string(name, state)
                    key_ptr = lower_runtime_array_subscripts(subscripts, state)
                    string_value = lower_runtime_string_expression(value, state)
                    state.instructions.append(
                        f"  call void @qk_array_set_string(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr}, ptr {string_value})"
                    )
                    stored_value = state.next_temp("assign.array.str")
                    state.instructions.append(
                        f"  {stored_value} = call ptr @qk_array_get(ptr {state.runtime_param}, ptr {array_name_ptr}, ptr {key_ptr})"
                    )
                    return stored_value
                case NameLValue(name=name) if runtime_assignment_preserves_string(value, state):
                    if name in state.function_param_strings:
                        string_value = lower_runtime_string_expression(value, state)
                        store_runtime_function_param_string(name, string_value, state)
                        return load_runtime_function_param_string(name, state)
                    if is_reusable_runtime_state_name(name):
                        raise RuntimeError(
                            "string-valued assignment expressions are not supported for reusable numeric state"
                        )
                    slot_index = runtime_name_slot_index(name, state)
                    string_value = lower_runtime_string_expression(value, state)
                    if runtime_name_uses_string_slot_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
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
                        state.instructions.append(
                            f"  call void @qk_slot_set_string(ptr {state.runtime_param}, i64 {slot_index}, ptr {string_value})"
                        )
                    stored_value = state.next_temp("assign.str")
                    if runtime_name_uses_slot_cached_runtime(name, state):
                        assert slot_index is not None
                        state.instructions.append(
                            f"  {stored_value} = call ptr @qk_slot_get_string(ptr {state.runtime_param}, i64 {slot_index})"
                        )
                    else:
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
            if (runtime_expression_is_known_string(left, state) and runtime_expression_is_known_string(right, state)
                    and not isinstance(left, BinaryExpr) and not isinstance(right, BinaryExpr)):
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
        case ConditionalExpr():
            return lower_runtime_string_conditional_expression(expression, state)
        case _:
            numeric_value = lower_runtime_numeric_expression(expression, state)
            temp = state.next_temp("numstr")
            state.instructions.append(
                f"  {temp} = call ptr @qk_format_number(ptr {state.runtime_param}, double {numeric_value})"
            )
    return temp


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
        state.instructions.append(
            f"  {result} = call double @qk_getline_main_string(ptr {state.runtime_param}, ptr {result_slot})"
        )
    else:
        source_ptr = lower_runtime_captured_string_expression(expression.source, state)
        result = state.next_temp("getline")
        state.instructions.append(
            f"  {result} = call double @qk_getline_file_string(ptr {state.runtime_param}, ptr {source_ptr}, ptr {result_slot})"
        )
    assign_condition = state.next_temp("getline.assign")
    assign_label = state.next_label("getline.assign.block")
    done_label = state.next_label("getline.done")
    state.instructions.append(f"  {assign_condition} = fcmp ogt double {result}, 0.000000000000000e+00")
    state.instructions.append(f"  br i1 {assign_condition}, label %{assign_label}, label %{done_label}")
    state.instructions.append(f"{assign_label}:")
    result_ptr = state.next_temp("getline.result.ptr")
    state.instructions.append(f"  {result_ptr} = load ptr, ptr {result_slot}")
    if expression.target is None:
        raise RuntimeError("getline requires an assignment target in the runtime-backed backend")
    lower_runtime_assign_string_lvalue(expression.target, result_ptr, state)
    state.instructions.append(f"  br label %{done_label}")
    state.instructions.append(f"{done_label}:")
    return result


def lower_runtime_numeric_conditional_expression(expression: ConditionalExpr, state: LoweringState) -> str:
    """Lower one runtime-backed numeric ternary expression with short-circuit control flow."""
    builder = LLVMIRBuilder(state)
    test_value = lower_condition_expression(expression.test, state)
    true_label = builder.label("ternary.true")
    false_label = builder.label("ternary.false")
    end_label = builder.label("ternary.end")

    builder.cond_branch(test_value, true_label, false_label)
    builder.mark_label(true_label)
    true_operand = lower_runtime_numeric_expression(expression.if_true, state)
    builder.branch(end_label)
    builder.mark_label(false_label)
    false_operand = lower_runtime_numeric_expression(expression.if_false, state)
    builder.branch(end_label)
    builder.mark_label(end_label)
    return builder.phi("ternary.num", "double", [(true_operand, true_label), (false_operand, false_label)])


def lower_runtime_condition_conditional_expression(expression: ConditionalExpr, state: LoweringState) -> str:
    """Lower one runtime-backed boolean ternary expression with short-circuit control flow."""
    builder = LLVMIRBuilder(state)
    test_value = lower_condition_expression(expression.test, state)
    true_label = builder.label("cond.true")
    false_label = builder.label("cond.false")
    end_label = builder.label("cond.end")

    builder.cond_branch(test_value, true_label, false_label)
    builder.mark_label(true_label)
    true_condition = lower_condition_expression(expression.if_true, state)
    builder.branch(end_label)
    builder.mark_label(false_label)
    false_condition = lower_condition_expression(expression.if_false, state)
    builder.branch(end_label)
    builder.mark_label(end_label)
    return builder.phi("cond", "i1", [(true_condition, true_label), (false_condition, false_label)])


def lower_runtime_string_conditional_expression(expression: ConditionalExpr, state: LoweringState) -> str:
    """Lower one runtime-backed string ternary expression with short-circuit control flow."""
    assert state.runtime_param is not None
    builder = LLVMIRBuilder(state)
    test_value = lower_condition_expression(expression.test, state)
    true_label = builder.label("ternary.true")
    false_label = builder.label("ternary.false")
    end_label = builder.label("ternary.end")

    builder.cond_branch(test_value, true_label, false_label)
    builder.mark_label(true_label)
    true_value = lower_runtime_string_expression(expression.if_true, state)
    true_capture = builder.call(
        "ternary.str.capture",
        "ptr",
        "@qk_capture_string_arg_inline",
        [f"ptr {state.runtime_param}", f"ptr {true_value}"],
    )
    builder.branch(end_label)
    builder.mark_label(false_label)
    false_value = lower_runtime_string_expression(expression.if_false, state)
    false_capture = builder.call(
        "ternary.str.capture",
        "ptr",
        "@qk_capture_string_arg_inline",
        [f"ptr {state.runtime_param}", f"ptr {false_value}"],
    )
    builder.branch(end_label)
    builder.mark_label(end_label)
    return builder.phi("ternary.str", "ptr", [(true_capture, true_label), (false_capture, false_label)])


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
                from .lower_lvalue import lower_runtime_string_truthiness

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
            op_code = {
                BinaryOp.LESS: 0,
                BinaryOp.LESS_EQUAL: 1,
                BinaryOp.GREATER: 2,
                BinaryOp.GREATER_EQUAL: 3,
                BinaryOp.EQUAL: 4,
                BinaryOp.NOT_EQUAL: 5,
            }[expression.op]
            if state.runtime_param is not None:
                left_forces_string = expression_forces_string_comparison(expression.left)
                right_forces_string = expression_forces_string_comparison(expression.right)
                if left_forces_string or right_forces_string:
                    left_string = lower_runtime_captured_string_expression(expression.left, state)
                    right_string = lower_runtime_captured_string_expression(expression.right, state)
                    temp = state.next_temp("cmp")
                    state.instructions.append(
                        f"  {temp} = call i1 @qk_compare_strings_inline(ptr {left_string}, ptr {right_string}, i32 {op_code})"
                    )
                    return temp
                if (not left_forces_string
                        and not right_forces_string
                        and runtime_expression_is_definitely_numeric(expression.left, state)
                        and runtime_expression_is_definitely_numeric(expression.right, state)):
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
                left_force_string_flag = str(left_forces_string).lower()
                right_force_string_flag = str(right_forces_string).lower()
                temp = state.next_temp("cmp")
                state.instructions.append(
                    f"  {temp} = call i1 @qk_compare_values_inline("
                    f"ptr {left_string}, double {left_number}, i1 {left_needs_check}, i1 {left_force_string_flag}, "
                    f"ptr {right_string}, double {right_number}, i1 {right_needs_check}, i1 {right_force_string_flag}, "
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
            rhs_value_label = state.next_label("and.value")
            false_label = state.next_label("and.false")
            end_label = state.next_label("and.end")
            phi_temp = state.next_temp("and")

            state.instructions.append(f"  br i1 {left_condition}, label %{rhs_label}, label %{false_label}")
            state.instructions.append(f"{rhs_label}:")
            right_condition = lower_condition_expression(expression.right, state)
            state.instructions.append(f"  br label %{rhs_value_label}")
            state.instructions.append(f"{rhs_value_label}:")
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{false_label}:")
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{end_label}:")
            state.instructions.append(
                f"  {phi_temp} = phi i1 [ false, %{false_label} ], [ {right_condition}, %{rhs_value_label} ]"
            )
            return phi_temp
        if expression.op is BinaryOp.LOGICAL_OR:
            left_condition = lower_condition_expression(expression.left, state)
            true_label = state.next_label("or.true")
            rhs_label = state.next_label("or.rhs")
            rhs_value_label = state.next_label("or.value")
            end_label = state.next_label("or.end")
            phi_temp = state.next_temp("or")

            state.instructions.append(f"  br i1 {left_condition}, label %{true_label}, label %{rhs_label}")
            state.instructions.append(f"{true_label}:")
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{rhs_label}:")
            right_condition = lower_condition_expression(expression.right, state)
            state.instructions.append(f"  br label %{rhs_value_label}")
            state.instructions.append(f"{rhs_value_label}:")
            state.instructions.append(f"  br label %{end_label}")
            state.instructions.append(f"{end_label}:")
            state.instructions.append(
                f"  {phi_temp} = phi i1 [ true, %{true_label} ], [ {right_condition}, %{rhs_value_label} ]"
            )
            return phi_temp
        if state.runtime_param is not None and expression.op in {BinaryOp.MATCH, BinaryOp.NOT_MATCH}:
            return lower_runtime_match_operator(expression, state)
        if state.runtime_param is not None and expression.op is BinaryOp.IN:
            return lower_runtime_in_expression(expression, state)

    if isinstance(expression, ConditionalExpr):
        if runtime_expression_has_side_effects(expression.if_true, state) or runtime_expression_has_side_effects(
                expression.if_false, state):
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
                f"  {match_result} = call i1 @qk_regex_match_current_record(ptr {state.runtime_param}, ptr {string_ptr})",
            ]
        )
        return match_result
    return lower_condition_expression(pattern.test, state)
