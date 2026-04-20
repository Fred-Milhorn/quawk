from __future__ import annotations

from quawk.ast import (
    ArrayLValue,
    AssignExpr,
    AssignOp,
    CallExpr,
    FieldExpr,
    FieldLValue,
    NameExpr,
    NameLValue,
)
from quawk.ast_walk import expression_children, lvalue_expressions
from quawk.source import ProgramSource


SOURCE = ProgramSource.from_inline("x")
SPAN = SOURCE.span(SOURCE.point(0, 0), SOURCE.point(0, 1))


def name_expr(name: str) -> NameExpr:
    return NameExpr(name=name, span=SPAN)


def test_lvalue_expressions_yields_array_subscripts_and_field_indexes() -> None:
    subscript = name_expr("i")
    field_index = name_expr("n")

    assert list(lvalue_expressions(NameLValue("x", SPAN))) == []
    assert list(lvalue_expressions(ArrayLValue("a", (subscript,), SPAN))) == [subscript]
    assert list(lvalue_expressions(FieldLValue(field_index, SPAN))) == [field_index]


def test_expression_children_preserves_lvalue_then_value_order_for_assignment() -> None:
    subscript = name_expr("i")
    value = name_expr("value")
    expression = AssignExpr(
        target=ArrayLValue("a", (subscript,), SPAN),
        op=AssignOp.PLAIN,
        value=value,
        span=SPAN,
    )

    assert list(expression_children(expression)) == [subscript, value]


def test_expression_children_skips_constant_field_indexes() -> None:
    dynamic_index = name_expr("n")

    assert list(expression_children(FieldExpr(1, SPAN))) == []
    assert list(expression_children(FieldExpr(dynamic_index, SPAN))) == [dynamic_index]


def test_expression_children_yields_call_arguments() -> None:
    left = name_expr("left")
    right = name_expr("right")

    assert list(expression_children(CallExpr("f", (left, right), SPAN))) == [left, right]
