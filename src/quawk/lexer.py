from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .diagnostics import LexError
from .source import SourceSpan, SourceText


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
    span: SourceSpan


def lex(source: str | SourceText) -> list[Token]:
    source_text = source if isinstance(source, SourceText) else SourceText.from_inline(source)
    tokens: list[Token] = []
    index = 0

    while index < len(source_text.text):
        char = source_text.text[index]

        match char:
            case _ if char.isspace():
                index += 1
            case "{":
                tokens.append(Token(TokenKind.LBRACE, char, source_text.span(index, index + 1)))
                index += 1
            case "}":
                tokens.append(Token(TokenKind.RBRACE, char, source_text.span(index, index + 1)))
                index += 1
            case '"':
                token, index = lex_string(source_text, index)
                tokens.append(token)
            case _ if char.isalpha() or char == "_":
                token, index = lex_word(source_text, index)
                tokens.append(token)
            case _:
                raise LexError(f"unsupported token: {char!r}", source_text.span(index, index + 1))

    tokens.append(Token(TokenKind.EOF, "", source_text.span(len(source_text.text), len(source_text.text))))
    return tokens


def format_tokens(tokens: list[Token]) -> str:
    return "".join(f"{token.kind.value} lexeme={token.lexeme!r} span={token.span.format_start()}\n" for token in tokens)


def lex_word(source: SourceText, start: int) -> tuple[Token, int]:
    index = start
    while index < len(source.text) and (source.text[index].isalnum() or source.text[index] == "_"):
        index += 1

    word = source.text[start:index]
    span = source.span(start, index)
    match word:
        case "BEGIN":
            return Token(TokenKind.BEGIN, word, span), index
        case "print":
            return Token(TokenKind.PRINT, word, span), index
        case _:
            raise LexError(f"unsupported token: {word!r}", span)


def lex_string(source: SourceText, start: int) -> tuple[Token, int]:
    index = start + 1
    escaped = False

    while index < len(source.text):
        char = source.text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return Token(TokenKind.STRING, source.text[start:index + 1], source.span(start, index + 1)), index + 1
        index += 1

    raise LexError("unterminated string literal", source.span(start, len(source.text)))
