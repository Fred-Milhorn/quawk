# Scanner and token-location tests.
# These cases verify token classification, text capture, and source-position
# tracking in the frontend scanner.

from __future__ import annotations

import pytest

from quawk.diagnostics import LexError
from quawk.lexer import TokenKind, lex
from quawk.source import ProgramSource


def test_lexes_begin_print_literal_program() -> None:
    tokens = lex('BEGIN { print "hello" }')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        '"hello"',
        "}",
        None,
    ]
    assert [token.span.format_start() for token in tokens] == [
        "<inline>:1:1",
        "<inline>:1:7",
        "<inline>:1:9",
        "<inline>:1:15",
        "<inline>:1:23",
        "<inline>:1:24",
    ]


def test_lexes_newlines_and_escaped_quotes() -> None:
    tokens = lex(' \nBEGIN\t{ print "say \\"hi\\"" }\n')

    assert [token.kind for token in tokens] == [
        TokenKind.NEWLINE,
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.EOF,
    ]
    assert tokens[4].text == '"say \\"hi\\""'
    assert tokens[0].span.format_start() == "<inline>:1:2"
    assert tokens[1].span.format_start() == "<inline>:2:1"
    assert tokens[6].span.format_start() == "<inline>:2:29"
    assert tokens[7].span.format_start() == "<inline>:2:29"


def test_lexes_general_identifiers_and_numbers() -> None:
    tokens = lex("foo 123 4.5")

    assert [token.kind for token in tokens] == [
        TokenKind.IDENT,
        TokenKind.NUMBER,
        TokenKind.NUMBER,
        TokenKind.EOF,
    ]
    assert [token.text for token in tokens] == ["foo", "123", "4.5", None]


def test_lexes_regex_literal_in_pattern_position() -> None:
    tokens = lex("/foo/ { print $0 }")

    assert [token.kind for token in tokens] == [
        TokenKind.REGEX,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.DOLLAR,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[0].text == "/foo/"
    assert tokens[0].span.format_start() == "<inline>:1:1"


def test_lexes_regex_literal_after_print_keyword() -> None:
    tokens = lex("BEGIN { print /foo/ }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.REGEX,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[3].text == "/foo/"


def test_lexes_slash_as_operator_after_operand() -> None:
    tokens = lex("BEGIN { print 8 / 2 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.SLASH,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[4].display_text() == "/"


def test_lexes_regex_with_escaped_slash_and_character_class() -> None:
    tokens = lex(r'/fo\/o[\/]bar/ { print $0 }')

    assert tokens[0].kind is TokenKind.REGEX
    assert tokens[0].text == r'/fo\/o[\/]bar/'


def test_lexes_numeric_print_expression_tokens() -> None:
    tokens = lex("BEGIN { print 1 + 2 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.PLUS,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        "1",
        "+",
        "2",
        "}",
        None,
    ]


def test_lexes_equality_expression_tokens() -> None:
    tokens = lex("BEGIN { print 1 == 1 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.EQUAL_EQUAL,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        "1",
        "==",
        "1",
        "}",
        None,
    ]
    assert tokens[4].span.format_start() == "<inline>:1:17"


def test_lexes_parenthesized_logical_and_expression_tokens() -> None:
    tokens = lex("BEGIN { print (1 < 2) && (2 < 3) }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.AND_AND,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[8].display_text() == "&&"
    assert [token.span.format_start() for token in tokens[3:10]] == [
        "<inline>:1:15",
        "<inline>:1:16",
        "<inline>:1:18",
        "<inline>:1:20",
        "<inline>:1:21",
        "<inline>:1:23",
        "<inline>:1:26",
    ]


def test_lexes_assignment_tokens() -> None:
    tokens = lex("BEGIN { x = 1; print x }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.IDENT,
        TokenKind.EQUAL,
        TokenKind.NUMBER,
        TokenKind.SEMICOLON,
        TokenKind.PRINT,
        TokenKind.IDENT,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_bare_action_field_tokens() -> None:
    tokens = lex("{ print $1 }")

    assert [token.kind for token in tokens] == [
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.DOLLAR,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_comparison_and_control_flow_tokens() -> None:
    tokens = lex("BEGIN { if (1 < 2) print 3; while (x < 3) { x = x + 1 } }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.IF,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.SEMICOLON,
        TokenKind.WHILE,
        TokenKind.LPAREN,
        TokenKind.IDENT,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.LBRACE,
        TokenKind.IDENT,
        TokenKind.EQUAL,
        TokenKind.IDENT,
        TokenKind.PLUS,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_function_definition_and_return_tokens() -> None:
    tokens = lex("function f(x) { return x + 1 }")

    assert [token.kind for token in tokens] == [
        TokenKind.FUNCTION,
        TokenKind.IDENT,
        TokenKind.LPAREN,
        TokenKind.IDENT,
        TokenKind.RPAREN,
        TokenKind.LBRACE,
        TokenKind.RETURN,
        TokenKind.IDENT,
        TokenKind.PLUS,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.span.format_start() for token in tokens[:12]] == [
        "<inline>:1:1",
        "<inline>:1:10",
        "<inline>:1:11",
        "<inline>:1:12",
        "<inline>:1:13",
        "<inline>:1:15",
        "<inline>:1:17",
        "<inline>:1:24",
        "<inline>:1:26",
        "<inline>:1:28",
        "<inline>:1:30",
        "<inline>:1:31",
    ]


def test_lexes_break_and_continue_tokens() -> None:
    tokens = lex("BEGIN { while (1) { break; continue } }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.WHILE,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.LBRACE,
        TokenKind.BREAK,
        TokenKind.SEMICOLON,
        TokenKind.CONTINUE,
        TokenKind.RBRACE,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_mixed_begin_record_end_tokens() -> None:
    tokens = lex('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.DOLLAR,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.END,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        '"start"',
        "}",
        "\n",
        "{",
        "print",
        "$",
        "2",
        "}",
        "\n",
        "END",
        "{",
        "print",
        '"done"',
        "}",
        None,
    ]


def test_rejects_unexpected_characters() -> None:
    with pytest.raises(LexError, match="unexpected character") as excinfo:
        lex("BEGIN { @ }")
    assert excinfo.value.span.format_start() == "<inline>:1:9"


def test_rejects_unterminated_string_literals() -> None:
    with pytest.raises(LexError, match="unterminated string literal") as excinfo:
        lex('BEGIN { print "hello }')
    assert excinfo.value.span.format_start() == "<inline>:1:15"


def test_rejects_unterminated_regex_literals() -> None:
    with pytest.raises(LexError, match="unterminated regex literal") as excinfo:
        lex("/foo")
    assert excinfo.value.span.format_start() == "<inline>:1:1"


def test_lex_preserves_file_locations_across_multiple_f_files() -> None:
    source = ProgramSource.from_files([
        ("first.awk", "BEGIN {"),
        ("second.awk", 'print "hello" }'),
    ])

    tokens = lex(source)

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.NEWLINE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.span.format_start() for token in tokens] == [
        "first.awk:1:1",
        "first.awk:1:7",
        "first.awk:1:8",
        "second.awk:1:1",
        "second.awk:1:7",
        "second.awk:1:15",
        "second.awk:1:16",
    ]
