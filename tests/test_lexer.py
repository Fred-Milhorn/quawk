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


def test_rejects_unexpected_characters() -> None:
    with pytest.raises(LexError, match="unexpected character") as excinfo:
        lex("BEGIN { @ }")
    assert excinfo.value.span.format_start() == "<inline>:1:9"


def test_rejects_unterminated_string_literals() -> None:
    with pytest.raises(LexError, match="unterminated string literal") as excinfo:
        lex('BEGIN { print "hello }')
    assert excinfo.value.span.format_start() == "<inline>:1:15"


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
