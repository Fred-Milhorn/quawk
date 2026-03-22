# Scanner and token model for the frontend.
# This module turns source text into positioned tokens while preserving enough
# structure for diagnostics, parsing, and `--lex` inspection output.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from .diagnostics import LexError
from .source import ProgramSource, SourceCursor, SourcePoint, SourceSpan


class TokenKind(Enum):
    BEGIN = auto()
    END = auto()
    FUNCTION = auto()
    PRINT = auto()
    PRINTF = auto()
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    PLUS = auto()
    EQUAL = auto()
    DOLLAR = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    SEMICOLON = auto()
    NEWLINE = auto()
    EOF = auto()


KEYWORDS: dict[str, TokenKind] = {
    "BEGIN": TokenKind.BEGIN,
    "END": TokenKind.END,
    "function": TokenKind.FUNCTION,
    "print": TokenKind.PRINT,
    "printf": TokenKind.PRINTF,
}

FIXED_TOKEN_TEXT: dict[TokenKind, str] = {
    TokenKind.BEGIN: "BEGIN",
    TokenKind.END: "END",
    TokenKind.FUNCTION: "function",
    TokenKind.PRINT: "print",
    TokenKind.PRINTF: "printf",
    TokenKind.PLUS: "+",
    TokenKind.EQUAL: "=",
    TokenKind.DOLLAR: "$",
    TokenKind.LBRACE: "{",
    TokenKind.RBRACE: "}",
    TokenKind.LPAREN: "(",
    TokenKind.RPAREN: ")",
    TokenKind.COMMA: ",",
    TokenKind.SEMICOLON: ";",
    TokenKind.NEWLINE: "\n",
}

PUNCTUATION_KINDS: dict[str, TokenKind] = {
    "+": TokenKind.PLUS,
    "=": TokenKind.EQUAL,
    "$": TokenKind.DOLLAR,
    "{": TokenKind.LBRACE,
    "}": TokenKind.RBRACE,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    ",": TokenKind.COMMA,
    ";": TokenKind.SEMICOLON,
}


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    span: SourceSpan
    text: str | None = None

    def display_text(self) -> str | None:
        """Return the token text used by debugging and inspection output."""
        if self.text is not None:
            return self.text
        return FIXED_TOKEN_TEXT.get(self.kind)


def lex(source: str | ProgramSource) -> list[Token]:
    """Lex inline text or tracked program input into tokens."""
    source_text = source if isinstance(source, ProgramSource) else ProgramSource.from_inline(source)
    return Lexer(source_text).scan_tokens()


def format_tokens(tokens: list[Token]) -> str:
    """Render tokens in a stable text form for `quawk --lex`."""
    lines: list[str] = []
    for token in tokens:
        text = token.display_text()
        if text is None:
            lines.append(f"{token.kind.name} span={token.span.format_start()}")
        else:
            lines.append(f"{token.kind.name} text={text!r} span={token.span.format_start()}")
    return "\n".join(lines) + "\n"


class Lexer:
    """Scanner for the currently supported quawk token set."""

    def __init__(self, source: ProgramSource) -> None:
        """Create a scanner over `source`."""
        self.source = source
        self.cursor = SourceCursor(source)

    def scan_tokens(self) -> list[Token]:
        """Scan the full token stream, always terminating with EOF."""
        tokens: list[Token] = []
        while True:
            token = self.scan_token()
            if token is None:
                continue
            tokens.append(token)
            if token.kind is TokenKind.EOF:
                return tokens

    def scan_token(self) -> Token | None:
        """Scan one token, or return `None` after consuming ignored trivia."""
        char = self.cursor.peek()
        if char is None:
            eof = self.cursor.point()
            return Token(TokenKind.EOF, self.source.span(eof, eof))

        if char in " \t\r\f\v":
            self.skip_horizontal_whitespace()
            return None

        start = self.cursor.point()

        if char == "\n":
            self.cursor.advance()
            end = self.cursor.point()
            return Token(TokenKind.NEWLINE, self.source.span(start, end))

        if char in PUNCTUATION_KINDS:
            self.cursor.advance()
            end = self.cursor.point()
            return Token(PUNCTUATION_KINDS[char], self.source.span(start, end))

        if char == '"':
            return self.scan_string_literal(start)

        if char.isalpha() or char == "_":
            return self.scan_identifier_or_keyword(start)

        if char.isdigit():
            return self.scan_number(start)

        self.cursor.advance()
        raise LexError(f"unexpected character: {char!r}", self.source.span(start, self.cursor.point()))

    def skip_horizontal_whitespace(self) -> None:
        """Consume non-newline whitespace."""
        while (char := self.cursor.peek()) is not None and char in " \t\r\f\v":
            self.cursor.advance()

    def scan_identifier_or_keyword(self, start: SourcePoint) -> Token:
        """Scan an identifier and reclassify it if it matches a keyword."""
        text = self.take_while(lambda char: char.isalnum() or char == "_")
        end = self.cursor.point()
        kind = KEYWORDS.get(text, TokenKind.IDENT)
        token_text = text if kind is TokenKind.IDENT else None
        return Token(kind, self.source.span(start, end), token_text)

    def scan_string_literal(self, start: SourcePoint) -> Token:
        """Scan a double-quoted string literal without decoding escapes yet."""
        chars = [self.cursor.advance() or ""]
        escaped = False

        while (char := self.cursor.peek()) is not None:
            if char == "\n" and not escaped:
                break

            chars.append(self.cursor.advance() or "")
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                return Token(TokenKind.STRING, self.source.span(start, self.cursor.point()), "".join(chars))

        raise LexError("unterminated string literal", self.source.span(start, self.cursor.point()))

    def scan_number(self, start: SourcePoint) -> Token:
        """Scan a simple integer or decimal literal."""
        seen_decimal = False

        def should_continue(char: str) -> bool:
            nonlocal seen_decimal
            if char.isdigit():
                return True
            if char == "." and not seen_decimal:
                seen_decimal = True
                return True
            return False

        text = self.take_while(should_continue)
        end = self.cursor.point()
        return Token(TokenKind.NUMBER, self.source.span(start, end), text)

    def take_while(self, predicate: Callable[[str], bool]) -> str:
        """Consume characters while `predicate` returns true."""
        chars: list[str] = []
        while (char := self.cursor.peek()) is not None and predicate(char):
            chars.append(self.cursor.advance() or "")
        return "".join(chars)
