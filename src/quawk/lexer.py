from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenKind(str, Enum):
    BEGIN = "BEGIN"
    PRINT = "PRINT"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    STRING = "STRING"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str


class LexError(ValueError):
    pass


def lex(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0

    while index < len(source):
        char = source[index]

        if char.isspace():
            index += 1
            continue

        if source.startswith("BEGIN", index) and is_word_boundary(source, index + 5):
            tokens.append(Token(TokenKind.BEGIN, "BEGIN"))
            index += 5
            continue

        if source.startswith("print", index) and is_word_boundary(source, index + 5):
            tokens.append(Token(TokenKind.PRINT, "print"))
            index += 5
            continue

        if char == "{":
            tokens.append(Token(TokenKind.LBRACE, char))
            index += 1
            continue

        if char == "}":
            tokens.append(Token(TokenKind.RBRACE, char))
            index += 1
            continue

        if char == '"':
            token, index = lex_string(source, index)
            tokens.append(token)
            continue

        raise LexError(f"unsupported token at offset {index}: {char!r}")

    tokens.append(Token(TokenKind.EOF, ""))
    return tokens


def is_word_boundary(source: str, index: int) -> bool:
    if index >= len(source):
        return True
    return not (source[index].isalnum() or source[index] == "_")


def lex_string(source: str, start: int) -> tuple[Token, int]:
    index = start + 1
    escaped = False

    while index < len(source):
        char = source[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return Token(TokenKind.STRING, source[start : index + 1]), index + 1
        index += 1

    raise LexError("unterminated string literal")
