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
    BREAK = auto()
    CONTINUE = auto()
    DELETE = auto()
    DO = auto()
    END = auto()
    ELSE = auto()
    EXIT = auto()
    FOR = auto()
    FUNCTION = auto()
    IF = auto()
    IN = auto()
    NEXT = auto()
    NEXTFILE = auto()
    PRINT = auto()
    PRINTF = auto()
    RETURN = auto()
    WHILE = auto()
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    REGEX = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    GREATER_GREATER = auto()
    EQUAL_EQUAL = auto()
    NOT_EQUAL = auto()
    OR_OR = auto()
    PIPE = auto()
    AND_AND = auto()
    MATCH = auto()
    NOT_MATCH = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    CARET = auto()
    BANG = auto()
    EQUAL = auto()
    PLUS_EQUAL = auto()
    MINUS_EQUAL = auto()
    STAR_EQUAL = auto()
    SLASH_EQUAL = auto()
    PERCENT_EQUAL = auto()
    CARET_EQUAL = auto()
    PLUS_PLUS = auto()
    MINUS_MINUS = auto()
    DOLLAR = auto()
    QUESTION = auto()
    COLON = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    SEMICOLON = auto()
    NEWLINE = auto()
    EOF = auto()


KEYWORDS: dict[str, TokenKind] = {
    "BEGIN": TokenKind.BEGIN,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
    "delete": TokenKind.DELETE,
    "do": TokenKind.DO,
    "END": TokenKind.END,
    "else": TokenKind.ELSE,
    "exit": TokenKind.EXIT,
    "for": TokenKind.FOR,
    "function": TokenKind.FUNCTION,
    "if": TokenKind.IF,
    "in": TokenKind.IN,
    "next": TokenKind.NEXT,
    "nextfile": TokenKind.NEXTFILE,
    "print": TokenKind.PRINT,
    "printf": TokenKind.PRINTF,
    "return": TokenKind.RETURN,
    "while": TokenKind.WHILE,
}

FIXED_TOKEN_TEXT: dict[TokenKind, str] = {
    TokenKind.BEGIN: "BEGIN",
    TokenKind.BREAK: "break",
    TokenKind.CONTINUE: "continue",
    TokenKind.DELETE: "delete",
    TokenKind.DO: "do",
    TokenKind.END: "END",
    TokenKind.ELSE: "else",
    TokenKind.EXIT: "exit",
    TokenKind.FOR: "for",
    TokenKind.FUNCTION: "function",
    TokenKind.IF: "if",
    TokenKind.IN: "in",
    TokenKind.NEXT: "next",
    TokenKind.NEXTFILE: "nextfile",
    TokenKind.PRINT: "print",
    TokenKind.PRINTF: "printf",
    TokenKind.RETURN: "return",
    TokenKind.WHILE: "while",
    TokenKind.LESS: "<",
    TokenKind.LESS_EQUAL: "<=",
    TokenKind.GREATER: ">",
    TokenKind.GREATER_EQUAL: ">=",
    TokenKind.GREATER_GREATER: ">>",
    TokenKind.EQUAL_EQUAL: "==",
    TokenKind.NOT_EQUAL: "!=",
    TokenKind.OR_OR: "||",
    TokenKind.PIPE: "|",
    TokenKind.AND_AND: "&&",
    TokenKind.MATCH: "~",
    TokenKind.NOT_MATCH: "!~",
    TokenKind.PLUS: "+",
    TokenKind.MINUS: "-",
    TokenKind.STAR: "*",
    TokenKind.SLASH: "/",
    TokenKind.PERCENT: "%",
    TokenKind.CARET: "^",
    TokenKind.BANG: "!",
    TokenKind.EQUAL: "=",
    TokenKind.PLUS_EQUAL: "+=",
    TokenKind.MINUS_EQUAL: "-=",
    TokenKind.STAR_EQUAL: "*=",
    TokenKind.SLASH_EQUAL: "/=",
    TokenKind.PERCENT_EQUAL: "%=",
    TokenKind.CARET_EQUAL: "^=",
    TokenKind.PLUS_PLUS: "++",
    TokenKind.MINUS_MINUS: "--",
    TokenKind.DOLLAR: "$",
    TokenKind.QUESTION: "?",
    TokenKind.COLON: ":",
    TokenKind.LBRACE: "{",
    TokenKind.RBRACE: "}",
    TokenKind.LPAREN: "(",
    TokenKind.RPAREN: ")",
    TokenKind.LBRACKET: "[",
    TokenKind.RBRACKET: "]",
    TokenKind.COMMA: ",",
    TokenKind.SEMICOLON: ";",
    TokenKind.NEWLINE: "\n",
}

PUNCTUATION_KINDS: dict[str, TokenKind] = {
    "<": TokenKind.LESS,
    ">": TokenKind.GREATER,
    "|": TokenKind.PIPE,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "%": TokenKind.PERCENT,
    "^": TokenKind.CARET,
    "!": TokenKind.BANG,
    "~": TokenKind.MATCH,
    "$": TokenKind.DOLLAR,
    "=": TokenKind.EQUAL,
    "?": TokenKind.QUESTION,
    ":": TokenKind.COLON,
    "{": TokenKind.LBRACE,
    "}": TokenKind.RBRACE,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "[": TokenKind.LBRACKET,
    "]": TokenKind.RBRACKET,
    ",": TokenKind.COMMA,
    ";": TokenKind.SEMICOLON,
}

MULTI_CHAR_TOKEN_KINDS: dict[str, TokenKind] = {
    "<=": TokenKind.LESS_EQUAL,
    ">=": TokenKind.GREATER_EQUAL,
    ">>": TokenKind.GREATER_GREATER,
    "==": TokenKind.EQUAL_EQUAL,
    "!=": TokenKind.NOT_EQUAL,
    "||": TokenKind.OR_OR,
    "&&": TokenKind.AND_AND,
    "!~": TokenKind.NOT_MATCH,
    "+=": TokenKind.PLUS_EQUAL,
    "-=": TokenKind.MINUS_EQUAL,
    "*=": TokenKind.STAR_EQUAL,
    "/=": TokenKind.SLASH_EQUAL,
    "%=": TokenKind.PERCENT_EQUAL,
    "^=": TokenKind.CARET_EQUAL,
    "++": TokenKind.PLUS_PLUS,
    "--": TokenKind.MINUS_MINUS,
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
        # `/` is only a regex opener where the grammar is looking for a new
        # operand; otherwise it is the division operator token.
        self.expect_operand = True

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

        if char == "\\" and self.cursor.peek(1) == "\n":
            self.cursor.advance()
            self.cursor.advance()
            return None

        start = self.cursor.point()

        if char == "\n":
            self.cursor.advance()
            end = self.cursor.point()
            return self.finish_token(Token(TokenKind.NEWLINE, self.source.span(start, end)))

        if char == "#":
            self.skip_comment()
            return None

        if char == "/":
            return self.scan_slash_or_regex(start)

        if token := self.scan_multi_char_operator(start):
            return token

        if char in PUNCTUATION_KINDS:
            self.cursor.advance()
            end = self.cursor.point()
            return self.finish_token(Token(PUNCTUATION_KINDS[char], self.source.span(start, end)))

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

    def skip_comment(self) -> None:
        """Consume one POSIX AWK `# ...` comment without eating the newline."""
        while (char := self.cursor.peek()) is not None and char != "\n":
            self.cursor.advance()

    def scan_multi_char_operator(self, start: SourcePoint) -> Token | None:
        """Scan a fixed two-character operator when one is present."""
        first = self.cursor.peek()
        second = self.cursor.peek(1)
        if first is None or second is None:
            return None

        text = first + second
        kind = MULTI_CHAR_TOKEN_KINDS.get(text)
        if kind is None:
            return None

        self.cursor.advance()
        self.cursor.advance()
        end = self.cursor.point()
        return self.finish_token(Token(kind, self.source.span(start, end)))

    def scan_identifier_or_keyword(self, start: SourcePoint) -> Token:
        """Scan an identifier and reclassify it if it matches a keyword."""
        text = self.take_while(lambda char: char.isalnum() or char == "_")
        end = self.cursor.point()
        kind = KEYWORDS.get(text, TokenKind.IDENT)
        token_text = text if kind is TokenKind.IDENT else None
        return self.finish_token(Token(kind, self.source.span(start, end), token_text))

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
                return self.finish_token(
                    Token(TokenKind.STRING, self.source.span(start, self.cursor.point()), "".join(chars))
                )

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
        return self.finish_token(Token(TokenKind.NUMBER, self.source.span(start, end), text))

    def scan_slash_or_regex(self, start: SourcePoint) -> Token:
        """Scan either a regex literal or a slash operator token."""
        if not self.expect_operand:
            if self.cursor.peek(1) == "=":
                self.cursor.advance()
                self.cursor.advance()
                return self.finish_token(Token(TokenKind.SLASH_EQUAL, self.source.span(start, self.cursor.point())))
            self.cursor.advance()
            return self.finish_token(Token(TokenKind.SLASH, self.source.span(start, self.cursor.point())))
        return self.scan_regex_literal(start)

    def scan_regex_literal(self, start: SourcePoint) -> Token:
        """Scan a raw `/.../` regex literal with basic escape/class awareness."""
        chars = [self.cursor.advance() or ""]
        escaped = False
        in_char_class = False

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
            if char == "[" and not in_char_class:
                in_char_class = True
                continue
            if char == "]" and in_char_class:
                in_char_class = False
                continue
            if char == "/" and not in_char_class:
                return self.finish_token(
                    Token(TokenKind.REGEX, self.source.span(start, self.cursor.point()), "".join(chars))
                )

        raise LexError("unterminated regex literal", self.source.span(start, self.cursor.point()))

    def finish_token(self, token: Token) -> Token:
        """Update scanner context after producing one non-trivia token."""
        was_expecting_operand = self.expect_operand
        if token.kind in {TokenKind.PLUS_PLUS, TokenKind.MINUS_MINUS}:
            self.expect_operand = was_expecting_operand
            return token

        self.expect_operand = token.kind in {
            TokenKind.AND_AND,
            TokenKind.BANG,
            TokenKind.CARET,
            TokenKind.COLON,
            TokenKind.COMMA,
            TokenKind.DOLLAR,
            TokenKind.DO,
            TokenKind.ELSE,
            TokenKind.EQUAL,
            TokenKind.EQUAL_EQUAL,
            TokenKind.EXIT,
            TokenKind.GREATER,
            TokenKind.GREATER_EQUAL,
            TokenKind.IF,
            TokenKind.IN,
            TokenKind.LBRACE,
            TokenKind.LBRACKET,
            TokenKind.LESS,
            TokenKind.LESS_EQUAL,
            TokenKind.LPAREN,
            TokenKind.MATCH,
            TokenKind.MINUS,
            TokenKind.NEWLINE,
            TokenKind.NOT_EQUAL,
            TokenKind.NOT_MATCH,
            TokenKind.OR_OR,
            TokenKind.PERCENT,
            TokenKind.PLUS,
            TokenKind.PLUS_EQUAL,
            TokenKind.MINUS_EQUAL,
            TokenKind.STAR_EQUAL,
            TokenKind.SLASH_EQUAL,
            TokenKind.PERCENT_EQUAL,
            TokenKind.CARET_EQUAL,
            TokenKind.PRINT,
            TokenKind.PRINTF,
            TokenKind.QUESTION,
            TokenKind.RETURN,
            TokenKind.SEMICOLON,
            TokenKind.SLASH,
            TokenKind.STAR,
        }
        return token

    def take_while(self, predicate: Callable[[str], bool]) -> str:
        """Consume characters while `predicate` returns true."""
        chars: list[str] = []
        while (char := self.cursor.peek()) is not None and predicate(char):
            chars.append(self.cursor.advance() or "")
        return "".join(chars)
