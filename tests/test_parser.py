from __future__ import annotations

import pytest

from quawk.diagnostics import ParseError
from quawk.lexer import lex
from quawk.parser import Action, BeginPattern, PatternAction, PrintStmt, Program, StringLiteralExpr, parse


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
    with pytest.raises(ParseError, match="expected PRINT, got EOF") as excinfo:
        parse(lex("BEGIN {"))

    assert excinfo.value.span.format_start() == "<inline>:1:8"
