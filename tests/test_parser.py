# Parser and AST-shape tests.
# These cases verify that the generalized frontend structure still accepts the
# MVP program and produces the intended AST categories.

from __future__ import annotations

import pytest

from quawk.diagnostics import ParseError
from quawk.lexer import lex
from quawk.parser import (
    Action,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BinaryOp,
    FieldExpr,
    NameExpr,
    NumericLiteralExpr,
    PatternAction,
    PrintStmt,
    Program,
    StringLiteralExpr,
    parse,
)


def test_parses_mvp_program_into_general_ast_categories() -> None:
    program = parse(lex('BEGIN { print "hello" }'))

    assert isinstance(program, Program)
    assert len(program.items) == 1

    item = program.items[0]
    assert isinstance(item, PatternAction)
    assert isinstance(item.pattern, BeginPattern)
    assert isinstance(item.action, Action)
    assert len(item.action.statements) == 1

    statement = item.action.statements[0]
    assert isinstance(statement, PrintStmt)
    assert len(statement.arguments) == 1

    argument = statement.arguments[0]
    assert isinstance(argument, StringLiteralExpr)
    assert argument.value == "hello"
    assert argument.raw_text == '"hello"'


def test_parse_errors_report_expected_token_kind() -> None:
    with pytest.raises(ParseError, match="expected statement, got EOF") as excinfo:
        parse(lex("BEGIN {"))

    assert excinfo.value.span.format_start() == "<inline>:1:8"


def test_parses_numeric_addition_into_binary_expression() -> None:
    program = parse(lex("BEGIN { print 1 + 2 }"))

    statement = program.items[0].action.statements[0]
    assert isinstance(statement, PrintStmt)

    argument = statement.arguments[0]
    assert isinstance(argument, BinaryExpr)
    assert argument.op is BinaryOp.ADD
    assert isinstance(argument.left, NumericLiteralExpr)
    assert argument.left.value == 1.0
    assert isinstance(argument.right, NumericLiteralExpr)
    assert argument.right.value == 2.0


def test_parses_assignment_and_variable_read() -> None:
    program = parse(lex("BEGIN { x = 1 + 2; print x }"))

    action = program.items[0].action
    assert isinstance(action, Action)
    assert len(action.statements) == 2

    assign = action.statements[0]
    assert isinstance(assign, AssignStmt)
    assert assign.name == "x"
    assert isinstance(assign.value, BinaryExpr)

    print_stmt = action.statements[1]
    assert isinstance(print_stmt, PrintStmt)
    assert isinstance(print_stmt.arguments[0], NameExpr)
    assert print_stmt.arguments[0].name == "x"


def test_parses_bare_action_with_field_expression() -> None:
    program = parse(lex("{ print $1 }"))

    item = program.items[0]
    assert isinstance(item, PatternAction)
    assert item.pattern is None
    assert isinstance(item.action, Action)
    statement = item.action.statements[0]
    assert isinstance(statement, PrintStmt)
    assert isinstance(statement.arguments[0], FieldExpr)
    assert statement.arguments[0].index == 1
