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

        match char:
            case _ if char.isspace():
                index += 1
            case "{":
                tokens.append(Token(TokenKind.LBRACE, char))
                index += 1
            case "}":
                tokens.append(Token(TokenKind.RBRACE, char))
                index += 1
            case '"':
                token, index = lex_string(source, index)
                tokens.append(token)
            case _ if char.isalpha() or char == "_":
                token, index = lex_word(source, index)
                tokens.append(token)
            case _:
                raise LexError(f"unsupported token at offset {index}: {char!r}")

    tokens.append(Token(TokenKind.EOF, ""))
    return tokens


def lex_word(source: str, start: int) -> tuple[Token, int]:
    index = start
    while index < len(source) and (source[index].isalnum() or source[index] == "_"):
        index += 1

    word = source[start:index]
    match word:
        case "BEGIN":
            return Token(TokenKind.BEGIN, word), index
        case "print":
            return Token(TokenKind.PRINT, word), index
        case _:
            raise LexError(f"unsupported token at offset {start}: {word!r}")


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
            return Token(TokenKind.STRING, source[start:index + 1]), index + 1
        index += 1

    raise LexError("unterminated string literal")
