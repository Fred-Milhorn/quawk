"""Shared AST traversal helpers."""

from __future__ import annotations

from collections.abc import Iterator

from .ast import (
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    BinaryExpr,
    CallExpr,
    ConditionalExpr,
    Expr,
    FieldExpr,
    FieldLValue,
    GetlineExpr,
    LValue,
    PostfixExpr,
    UnaryExpr,
)


def lvalue_expressions(target: LValue) -> Iterator[Expr]:
    """Yield expressions nested inside one lvalue."""
    match target:
        case ArrayLValue(subscripts=subscripts):
            yield from subscripts
        case FieldLValue(index=index):
            yield index
        case _:
            return


def expression_children(expression: Expr) -> Iterator[Expr]:
    """Yield immediate child expressions for one expression node."""
    match expression:
        case ArrayIndexExpr():
            yield from expression.subscripts
        case BinaryExpr(left=left, right=right):
            yield left
            yield right
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            yield test
            yield if_true
            yield if_false
        case AssignExpr(target=target, value=value):
            yield from lvalue_expressions(target)
            yield value
        case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
            yield operand
        case FieldExpr(index=index):
            if not isinstance(index, int):
                yield index
        case CallExpr(args=args):
            yield from args
        case GetlineExpr(target=target, source=source):
            if target is not None:
                yield from lvalue_expressions(target)
            if source is not None:
                yield source
        case _:
            return
