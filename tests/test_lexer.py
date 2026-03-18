from __future__ import annotations

import pytest

from quawk.lexer import LexError, TokenKind, lex


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


def test_rejects_unsupported_tokens() -> None:
    with pytest.raises(LexError, match="unsupported token"):
        lex("BEGIN { x }")


def test_rejects_unterminated_string_literals() -> None:
    with pytest.raises(LexError, match="unterminated string literal"):
        lex('BEGIN { print "hello }')
