"""Compile-time type lattice and join operation for AWK value inference."""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from .parser import (
    ArrayIndexExpr,
    AssignExpr,
    AssignOp,
    BinaryExpr,
    BinaryOp,
    CallExpr,
    ConditionalExpr,
    Expr,
    GetlineExpr,
    NameExpr,
    NumericLiteralExpr,
    PostfixExpr,
    RegexLiteralExpr,
    StringLiteralExpr,
    UnaryExpr,
)


class LatticeType(Enum):
    """Type lattice elements for AWK value inference.

    Lattice ordering (join semilattice)::

            MIXED
           /      \\
      NUMERIC    STRING
           \\      /
            UNKNOWN (bottom, no observed value yet)
    """

    UNKNOWN = "unknown"
    NUMERIC = "numeric"
    STRING = "string"
    MIXED = "mixed"

    def __str__(self) -> str:  # pragma: no cover
        return self.value


def join(left: LatticeType, right: LatticeType) -> LatticeType:
    """Return the least upper bound of two lattice types.

    Rules:
    - identical types: that type
    - either is UNKNOWN: the other type (identity element)
    - NUMERIC joined with STRING: MIXED
    - any involving MIXED: MIXED
    """
    if left is right:
        return left
    if left is LatticeType.UNKNOWN:
        return right
    if right is LatticeType.UNKNOWN:
        return left
    return LatticeType.MIXED


def can_be_numeric(t: LatticeType) -> bool:
    """Return whether a value of type *t* may hold a numeric value."""
    return t is LatticeType.UNKNOWN or t is LatticeType.NUMERIC or t is LatticeType.MIXED


def can_be_string(t: LatticeType) -> bool:
    """Return whether a value of type *t* may hold a string value."""
    return t is LatticeType.UNKNOWN or t is LatticeType.STRING or t is LatticeType.MIXED


def join_all(types: list[LatticeType] | tuple[LatticeType, ...]) -> LatticeType:
    """Fold *join* over a sequence of lattice types, returning UNKNOWN for an empty sequence."""
    result = LatticeType.UNKNOWN
    for t in types:
        result = join(result, t)
    return result


def infer_expression_type(
    expression: Expr,
    variable_types: Mapping[str, LatticeType] | None = None,
) -> LatticeType:
    """Infer the lattice type for one expression under the current variable types."""
    env = {} if variable_types is None else variable_types
    match expression:
        case NumericLiteralExpr():
            return LatticeType.NUMERIC
        case StringLiteralExpr() | RegexLiteralExpr():
            return LatticeType.STRING
        case NameExpr(name=name):
            return env.get(name, LatticeType.UNKNOWN)
        case ArrayIndexExpr():
            return LatticeType.UNKNOWN
        case GetlineExpr():
            return LatticeType.NUMERIC
        case UnaryExpr(operand=operand):
            operand_type = infer_expression_type(operand, env)
            if operand_type is LatticeType.STRING:
                return LatticeType.MIXED
            return LatticeType.NUMERIC
        case PostfixExpr():
            return LatticeType.NUMERIC
        case ConditionalExpr(if_true=if_true, if_false=if_false):
            return join(
                infer_expression_type(if_true, env),
                infer_expression_type(if_false, env),
            )
        case AssignExpr(op=AssignOp.PLAIN, value=value):
            return infer_expression_type(value, env)
        case AssignExpr():
            return LatticeType.NUMERIC
        case BinaryExpr(op=op, left=left, right=right):
            left_type = infer_expression_type(left, env)
            right_type = infer_expression_type(right, env)
            if op in {
                BinaryOp.ADD,
                BinaryOp.SUB,
                BinaryOp.MUL,
                BinaryOp.DIV,
                BinaryOp.MOD,
                BinaryOp.POW,
            }:
                if left_type is LatticeType.STRING or right_type is LatticeType.STRING:
                    return LatticeType.MIXED
                return LatticeType.NUMERIC
            if op is BinaryOp.CONCAT:
                return LatticeType.STRING
            if op in {
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
                return LatticeType.NUMERIC
            return LatticeType.UNKNOWN
        case CallExpr(function=function_name):
            if function_name in {"index", "int", "length", "match", "split", "sub", "gsub", "system"}:
                return LatticeType.NUMERIC
            if function_name in {"sprintf", "substr", "tolower", "toupper"}:
                return LatticeType.STRING
            return LatticeType.UNKNOWN
    return LatticeType.UNKNOWN
