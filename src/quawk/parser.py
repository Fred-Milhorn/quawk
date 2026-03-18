from __future__ import annotations

from dataclasses import dataclass

from .lexer import Token, TokenKind


@dataclass(frozen=True)
class PrintStatement:
    literal: str


@dataclass(frozen=True)
class BeginProgram:
    statements: tuple[PrintStatement, ...]


class ParseError(ValueError):
    pass


def parse(tokens: list[Token]) -> BeginProgram:
    parser = Parser(tokens)
    return parser.parse_program()


class Parser:

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> BeginProgram:
        self.expect(TokenKind.BEGIN)
        self.expect(TokenKind.LBRACE)

        statements: list[PrintStatement] = []
        while self.current().kind is not TokenKind.RBRACE:
            statements.append(self.parse_print_statement())

        self.expect(TokenKind.RBRACE)
        self.expect(TokenKind.EOF)
        return BeginProgram(tuple(statements))

    def parse_print_statement(self) -> PrintStatement:
        self.expect(TokenKind.PRINT)
        literal_token = self.expect(TokenKind.STRING)
        return PrintStatement(decode_string_literal(literal_token.lexeme))

    def current(self) -> Token:
        return self.tokens[self.index]

    def expect(self, kind: TokenKind) -> Token:
        token = self.current()
        if token.kind is not kind:
            raise ParseError(f"expected {kind.value}, got {token.kind.value}")
        self.index += 1
        return token


def decode_string_literal(lexeme: str) -> str:
    inner = lexeme[1:-1]
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
            raise ParseError("unterminated escape sequence in string literal")

        escaped = inner[index]
        match escaped:
            case "\\" | '"':
                result.append(escaped)
            case "n":
                result.append("\n")
            case "t":
                result.append("\t")
            case _:
                raise ParseError(f"unsupported escape sequence: \\{escaped}")
        index += 1

    return "".join(result)
