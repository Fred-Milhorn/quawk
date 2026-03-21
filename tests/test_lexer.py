from __future__ import annotations

import pytest

from quawk.lexer import LexError, TokenKind, lex
from quawk.source import SourceText


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
    assert [token.lexeme for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        '"hello"',
        "}",
        "",
    ]
    assert [token.span.format_start() for token in tokens] == [
        "<inline>:1:1",
        "<inline>:1:7",
        "<inline>:1:9",
        "<inline>:1:15",
        "<inline>:1:23",
        "<inline>:1:24",
    ]


def test_lexes_whitespace_and_escaped_quotes() -> None:
    tokens = lex(' \nBEGIN\t{ print "say \\"hi\\"" }\n')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[3].lexeme == '"say \\"hi\\""'
    assert tokens[0].span.format_start() == "<inline>:2:1"
    assert tokens[1].span.format_start() == "<inline>:2:7"
    assert tokens[5].span.format_start() == "<inline>:2:29"


def test_rejects_unsupported_tokens() -> None:
    with pytest.raises(LexError, match="unsupported token") as excinfo:
        lex("BEGIN { x }")
    assert excinfo.value.span.format_start() == "<inline>:1:9"


def test_rejects_unterminated_string_literals() -> None:
    with pytest.raises(LexError, match="unterminated string literal") as excinfo:
        lex('BEGIN { print "hello }')
    assert excinfo.value.span.format_start() == "<inline>:1:15"


def test_lex_preserves_original_file_locations_across_multiple_f_files() -> None:
    source = SourceText.from_files([
        ("first.awk", "BEGIN {"),
        ("second.awk", 'print "hello" }'),
    ])

    tokens = lex(source)

    assert [token.span.format_start() for token in tokens] == [
        "first.awk:1:1",
        "first.awk:1:7",
        "second.awk:1:1",
        "second.awk:1:7",
        "second.awk:1:15",
        "second.awk:1:16",
    ]
