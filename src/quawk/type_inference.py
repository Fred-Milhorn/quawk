"""Compile-time type lattice and join operation for AWK value inference."""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from .parser import (
    Action,
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignOp,
    AssignStmt,
    BinaryExpr,
    BinaryOp,
    BlockStmt,
    CallExpr,
    ConditionalExpr,
    DeleteStmt,
    DoWhileStmt,
    Expr,
    ExprPattern,
    ExprStmt,
    FieldExpr,
    FieldLValue,
    ForInStmt,
    ForStmt,
    FunctionDef,
    GetlineExpr,
    IfStmt,
    NameLValue,
    NameExpr,
    NumericLiteralExpr,
    PatternAction,
    PostfixExpr,
    PrintfStmt,
    PrintStmt,
    Program,
    RangePattern,
    ReturnStmt,
    RegexLiteralExpr,
    StringLiteralExpr,
    UnaryExpr,
    WhileStmt,
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


def infer_variable_types(program: Program) -> dict[str, LatticeType]:
    """Infer variable lattice types by propagating assignment effects across one program."""
    variable_types: dict[str, LatticeType] = {}

    def note_assignment(name: str, assigned_type: LatticeType, local_names: frozenset[str]) -> None:
        if name in local_names:
            return
        previous = variable_types.get(name, LatticeType.UNKNOWN)
        variable_types[name] = join(previous, assigned_type)

    def visit_lvalue_indexes(target: NameLValue | ArrayLValue | FieldLValue, local_names: frozenset[str]) -> None:
        match target:
            case NameLValue():
                return
            case ArrayLValue(subscripts=subscripts):
                for subscript in subscripts:
                    visit_expression(subscript, local_names)
            case FieldLValue(index=index):
                visit_expression(index, local_names)

    def visit_expression(expression: Expr, local_names: frozenset[str]) -> None:
        match expression:
            case AssignExpr(target=target, op=op, value=value):
                visit_expression(value, local_names)
                visit_lvalue_indexes(target, local_names)
                if isinstance(target, NameLValue):
                    if op is AssignOp.PLAIN:
                        assigned = infer_expression_type(value, variable_types)
                    else:
                        assigned = LatticeType.NUMERIC
                    note_assignment(target.name, assigned, local_names)
            case BinaryExpr(left=left, right=right):
                visit_expression(left, local_names)
                visit_expression(right, local_names)
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                visit_expression(test, local_names)
                visit_expression(if_true, local_names)
                visit_expression(if_false, local_names)
            case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
                visit_expression(operand, local_names)
            case CallExpr(args=args):
                for arg in args:
                    visit_expression(arg, local_names)
            case ArrayIndexExpr(index=index, extra_indexes=extra_indexes):
                visit_expression(index, local_names)
                for extra_index in extra_indexes:
                    visit_expression(extra_index, local_names)
            case FieldExpr(index=index):
                if not isinstance(index, int):
                    visit_expression(index, local_names)
            case GetlineExpr(target=target, source=source):
                if source is not None:
                    visit_expression(source, local_names)
                if target is not None:
                    visit_lvalue_indexes(target, local_names)
                    if isinstance(target, NameLValue):
                        note_assignment(target.name, LatticeType.STRING, local_names)
            case _:
                return

    def visit_statement(statement, local_names: frozenset[str]) -> None:
        match statement:
            case AssignStmt(target=target, op=op, value=value):
                visit_expression(value, local_names)
                visit_lvalue_indexes(target, local_names)
                if isinstance(target, NameLValue):
                    if op is AssignOp.PLAIN:
                        assigned = infer_expression_type(value, variable_types)
                    else:
                        assigned = LatticeType.NUMERIC
                    note_assignment(target.name, assigned, local_names)
            case ExprStmt(value=value):
                visit_expression(value, local_names)
            case PrintStmt(arguments=arguments, redirect=redirect) | PrintfStmt(arguments=arguments, redirect=redirect):
                for arg in arguments:
                    visit_expression(arg, local_names)
                if redirect is not None:
                    visit_expression(redirect.target, local_names)
            case BlockStmt(statements=statements):
                for nested in statements:
                    visit_statement(nested, local_names)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                visit_expression(condition, local_names)
                visit_statement(then_branch, local_names)
                if else_branch is not None:
                    visit_statement(else_branch, local_names)
            case WhileStmt(condition=condition, body=body):
                visit_expression(condition, local_names)
                visit_statement(body, local_names)
            case DoWhileStmt(body=body, condition=condition):
                visit_statement(body, local_names)
                visit_expression(condition, local_names)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                for init_expression in init:
                    visit_expression(init_expression, local_names)
                if condition is not None:
                    visit_expression(condition, local_names)
                for update_expression in update:
                    visit_expression(update_expression, local_names)
                visit_statement(body, local_names)
            case ForInStmt(name=name, iterable=iterable, body=body):
                visit_expression(iterable, local_names)
                note_assignment(name, LatticeType.STRING, local_names)
                visit_statement(body, local_names | frozenset({name}))
            case DeleteStmt(target=target):
                visit_lvalue_indexes(target, local_names)
            case ReturnStmt(value=value):
                if value is not None:
                    visit_expression(value, local_names)
            case _:
                return

    def visit_action(action: Action, local_names: frozenset[str]) -> None:
        for statement in action.statements:
            visit_statement(statement, local_names)

    def visit_pattern(pattern: ExprPattern | RangePattern) -> None:
        match pattern:
            case ExprPattern(test=test):
                visit_expression(test, frozenset())
            case RangePattern(left=left, right=right):
                visit_pattern(left)
                visit_pattern(right)

    for item in program.items:
        if isinstance(item, FunctionDef):
            visit_action(item.body, frozenset(item.params))
            continue
        if isinstance(item, PatternAction):
            if isinstance(item.pattern, ExprPattern | RangePattern):
                visit_pattern(item.pattern)
            if item.action is not None:
                visit_action(item.action, frozenset())

    return variable_types
