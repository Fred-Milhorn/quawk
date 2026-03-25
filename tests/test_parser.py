# Parser and AST-shape tests.
# These cases verify that the generalized frontend structure still accepts the
# initial `P1` program and produces the intended AST categories.

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
    BlockStmt,
    BreakStmt,
    CallExpr,
    ContinueStmt,
    EndPattern,
    ExprPattern,
    FieldExpr,
    FunctionDef,
    IfStmt,
    NameExpr,
    NumericLiteralExpr,
    PatternAction,
    PrintStmt,
    Program,
    RegexLiteralExpr,
    ReturnStmt,
    StringLiteralExpr,
    WhileStmt,
    format_program,
    parse,
)
from quawk.source import combine_spans


def test_parses_p1_program_into_general_ast_categories() -> None:
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


def test_parses_if_statement_with_comparison() -> None:
    program = parse(lex("BEGIN { if (1 < 2) print 3 }"))

    action = program.items[0].action
    assert isinstance(action, Action)
    assert len(action.statements) == 1

    statement = action.statements[0]
    assert isinstance(statement, IfStmt)
    assert isinstance(statement.condition, BinaryExpr)
    assert statement.condition.op is BinaryOp.LESS
    assert isinstance(statement.then_branch, PrintStmt)


def test_parses_equality_expression_into_binary_expression() -> None:
    program = parse(lex("BEGIN { print 1 == 1 }"))

    statement = program.items[0].action.statements[0]
    assert isinstance(statement, PrintStmt)

    argument = statement.arguments[0]
    assert isinstance(argument, BinaryExpr)
    assert argument.op is BinaryOp.EQUAL
    assert isinstance(argument.left, NumericLiteralExpr)
    assert isinstance(argument.right, NumericLiteralExpr)


def test_parses_parenthesized_logical_and_expression() -> None:
    program = parse(lex("BEGIN { print (1 < 2) && (2 < 3) }"))

    statement = program.items[0].action.statements[0]
    assert isinstance(statement, PrintStmt)

    argument = statement.arguments[0]
    assert isinstance(argument, BinaryExpr)
    assert argument.op is BinaryOp.LOGICAL_AND
    assert isinstance(argument.left, BinaryExpr)
    assert argument.left.op is BinaryOp.LESS
    assert isinstance(argument.right, BinaryExpr)
    assert argument.right.op is BinaryOp.LESS


def test_parses_while_statement_with_block() -> None:
    program = parse(lex("BEGIN { x = 0; while (x < 3) { print x; x = x + 1 } }"))

    action = program.items[0].action
    assert isinstance(action, Action)
    assert len(action.statements) == 2

    loop = action.statements[1]
    assert isinstance(loop, WhileStmt)
    assert isinstance(loop.condition, BinaryExpr)
    assert loop.condition.op is BinaryOp.LESS
    assert isinstance(loop.body, BlockStmt)
    assert len(loop.body.statements) == 2


def test_parses_function_definition_and_call() -> None:
    program = parse(lex("function f(x) { return x + 1 }\nBEGIN { print f(2) }"))

    function_item = program.items[0]
    assert isinstance(function_item, FunctionDef)
    assert function_item.name == "f"
    assert function_item.params == ("x", )

    return_stmt = function_item.body.statements[0]
    assert isinstance(return_stmt, ReturnStmt)
    assert isinstance(return_stmt.value, BinaryExpr)
    assert isinstance(return_stmt.value.left, NameExpr)

    begin_item = program.items[1]
    assert isinstance(begin_item, PatternAction)
    assert isinstance(begin_item.pattern, BeginPattern)
    print_stmt = begin_item.action.statements[0]
    assert isinstance(print_stmt, PrintStmt)
    assert isinstance(print_stmt.arguments[0], CallExpr)
    assert print_stmt.arguments[0].function == "f"
    assert len(print_stmt.arguments[0].args) == 1


def test_parses_break_and_continue_inside_while_block() -> None:
    program = parse(lex("BEGIN { while (1) { break; continue } }"))

    action = program.items[0].action
    assert isinstance(action, Action)
    loop = action.statements[0]
    assert isinstance(loop, WhileStmt)
    assert isinstance(loop.body, BlockStmt)
    assert isinstance(loop.body.statements[0], BreakStmt)
    assert isinstance(loop.body.statements[1], ContinueStmt)


def test_ast_supports_multi_item_programs_with_end_pattern() -> None:
    begin_program = parse(lex('BEGIN { print "start" }'))
    record_program = parse(lex("{ print $2 }"))
    end_tokens = lex('END { print "done" }')
    end_action_program = parse(lex('{ print "done" }'))

    begin_item = begin_program.items[0]
    record_item = record_program.items[0]
    end_pattern = EndPattern(span=end_tokens[0].span)
    end_action = end_action_program.items[0].action
    assert end_action is not None

    end_item = PatternAction(
        pattern=end_pattern,
        action=end_action,
        span=end_pattern.span,
    )
    program = Program(
        items=(begin_item, record_item, end_item),
        span=begin_item.span,
    )

    assert len(program.items) == 3
    assert isinstance(program.items[0].pattern, BeginPattern)
    assert program.items[1].pattern is None
    assert isinstance(program.items[2].pattern, EndPattern)
    assert isinstance(program.items[1].action, Action)
    assert isinstance(program.items[1].action.statements[0], PrintStmt)
    assert isinstance(program.items[1].action.statements[0].arguments[0], FieldExpr)
    assert program.items[1].action.statements[0].arguments[0].index == 2


def test_ast_supports_regex_expression_pattern() -> None:
    tokens = lex("/foo/ { print $0 }")
    regex_token = tokens[0]
    regex_pattern = ExprPattern(
        test=RegexLiteralExpr(raw_text=regex_token.text or "", span=regex_token.span),
        span=regex_token.span,
    )
    field_expr = FieldExpr(index=0, span=combine_spans(tokens[3].span, tokens[4].span))
    print_stmt = PrintStmt(arguments=(field_expr, ), span=combine_spans(tokens[2].span, field_expr.span))
    action = Action(statements=(print_stmt, ), span=combine_spans(tokens[1].span, tokens[5].span))

    program = Program(
        items=(
            PatternAction(
                pattern=regex_pattern,
                action=action,
                span=combine_spans(regex_pattern.span, action.span),
            ),
        ),
        span=combine_spans(regex_pattern.span, action.span),
    )

    item = program.items[0]
    assert isinstance(item.pattern, ExprPattern)
    assert isinstance(item.pattern.test, RegexLiteralExpr)
    assert item.pattern.test.raw_text == "/foo/"
    assert isinstance(item.action, Action)


def test_format_program_renders_end_pattern_and_multiple_items() -> None:
    begin_program = parse(lex('BEGIN { print "start" }'))
    record_program = parse(lex("{ print $2 }"))
    end_tokens = lex('END { print "done" }')
    end_action_program = parse(lex('{ print "done" }'))

    begin_item = begin_program.items[0]
    record_item = record_program.items[0]
    end_action = end_action_program.items[0].action
    assert end_action is not None

    program = Program(
        items=(
            begin_item,
            record_item,
            PatternAction(
                pattern=EndPattern(span=end_tokens[0].span),
                action=end_action,
                span=end_tokens[0].span,
            ),
        ),
        span=begin_item.span,
    )

    assert format_program(program) == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        StringLiteralExpr span=<inline>:1:15 value='start'\n"
        "  PatternAction span=<inline>:1:1\n"
        "    Action span=<inline>:1:1\n"
        "      PrintStmt span=<inline>:1:3\n"
        "        FieldExpr span=<inline>:1:9 index=2\n"
        "  PatternAction span=<inline>:1:1\n"
        "    EndPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:1\n"
        "      PrintStmt span=<inline>:1:3\n"
        "        StringLiteralExpr span=<inline>:1:9 value='done'\n"
    )


def test_format_program_renders_regex_expression_pattern() -> None:
    tokens = lex("/foo/ { print $0 }")
    regex_token = tokens[0]
    regex_pattern = ExprPattern(
        test=RegexLiteralExpr(raw_text=regex_token.text or "", span=regex_token.span),
        span=regex_token.span,
    )
    field_expr = FieldExpr(index=0, span=combine_spans(tokens[3].span, tokens[4].span))
    print_stmt = PrintStmt(arguments=(field_expr, ), span=combine_spans(tokens[2].span, field_expr.span))
    action = Action(statements=(print_stmt, ), span=combine_spans(tokens[1].span, tokens[5].span))

    program = Program(
        items=(
            PatternAction(
                pattern=regex_pattern,
                action=action,
                span=combine_spans(regex_pattern.span, action.span),
            ),
        ),
        span=combine_spans(regex_pattern.span, action.span),
    )

    assert format_program(program) == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    ExprPattern span=<inline>:1:1\n"
        "      RegexLiteralExpr span=<inline>:1:1 raw_text='/foo/'\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        FieldExpr span=<inline>:1:15 index=0\n"
    )


def test_parses_mixed_begin_record_end_program() -> None:
    program = parse(lex('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }'))

    assert len(program.items) == 3
    assert isinstance(program.items[0], PatternAction)
    assert isinstance(program.items[0].pattern, BeginPattern)
    assert program.items[1].pattern is None
    assert isinstance(program.items[1].action, Action)
    assert isinstance(program.items[1].action.statements[0], PrintStmt)
    assert isinstance(program.items[1].action.statements[0].arguments[0], FieldExpr)
    assert program.items[1].action.statements[0].arguments[0].index == 2
    assert isinstance(program.items[2].pattern, EndPattern)
    assert isinstance(program.items[2].action, Action)
    assert isinstance(program.items[2].action.statements[0], PrintStmt)


def test_parses_end_only_program() -> None:
    program = parse(lex('END { print "done" }'))

    assert len(program.items) == 1
    assert isinstance(program.items[0], PatternAction)
    assert isinstance(program.items[0].pattern, EndPattern)
    assert isinstance(program.items[0].action, Action)
    assert isinstance(program.items[0].action.statements[0], PrintStmt)


def test_parses_regex_pattern_action_program() -> None:
    program = parse(lex("/foo/ { print $0 }"))

    assert len(program.items) == 1
    item = program.items[0]
    assert isinstance(item, PatternAction)
    assert isinstance(item.pattern, ExprPattern)
    assert isinstance(item.pattern.test, RegexLiteralExpr)
    assert item.pattern.test.raw_text == "/foo/"
    assert isinstance(item.action, Action)
    assert isinstance(item.action.statements[0], PrintStmt)
    assert isinstance(item.action.statements[0].arguments[0], FieldExpr)
    assert item.action.statements[0].arguments[0].index == 0
