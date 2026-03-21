from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import ParseError
from .lexer import Token, TokenKind
from .source import SourceSpan, combine_spans


@dataclass(frozen=True)
class PrintStatement:
    literal: str
    span: SourceSpan


@dataclass(frozen=True)
class BeginProgram:
    statements: tuple[PrintStatement, ...]
    span: SourceSpan


def parse(tokens: list[Token]) -> BeginProgram:
    parser = Parser(tokens)
    return parser.parse_program()


def format_program(program: BeginProgram) -> str:
    lines = [f"BeginProgram span={program.span.format_start()}"]
    for statement in program.statements:
        lines.extend(
            [
                f"  PrintStatement span={statement.span.format_start()}",
                f"    literal={statement.literal!r}",
            ]
        )
    return "\n".join(lines) + "\n"


class Parser:

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> BeginProgram:
        begin_token = self.expect(TokenKind.BEGIN)
        self.expect(TokenKind.LBRACE)

        statements: list[PrintStatement] = []
        while self.current().kind is not TokenKind.RBRACE:
            statements.append(self.parse_print_statement())

        rbrace_token = self.expect(TokenKind.RBRACE)
        self.expect(TokenKind.EOF)
        return BeginProgram(tuple(statements), combine_spans(begin_token.span, rbrace_token.span))

    def parse_print_statement(self) -> PrintStatement:
        print_token = self.expect(TokenKind.PRINT)
        literal_token = self.expect(TokenKind.STRING)
        return PrintStatement(
            decode_string_literal(literal_token),
            combine_spans(print_token.span, literal_token.span),
        )

    def current(self) -> Token:
        return self.tokens[self.index]

    def expect(self, kind: TokenKind) -> Token:
        token = self.current()
        if token.kind is not kind:
            raise ParseError(f"expected {kind.value}, got {token.kind.value}", token.span)
        self.index += 1
        return token


def decode_string_literal(token: Token) -> str:
    inner = token.lexeme[1:-1]
    result: list[str] = []
    index = 0

    while index < len(inner):
        char = inner[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue

        index += 1
        if index >= len(inner):
            raise ParseError("unterminated escape sequence in string literal", token.span)

        escaped = inner[index]
        match escaped:
            case "\\" | '"':
                result.append(escaped)
            case "n":
                result.append("\n")
            case "t":
                result.append("\t")
            case _:
                raise ParseError(f"unsupported escape sequence: \\{escaped}", token.span)
        index += 1

    return "".join(result)
