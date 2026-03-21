from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .diagnostics import ParseError
from .lexer import Token, TokenKind
from .source import SourceSpan, combine_spans


@dataclass(frozen=True)
class BeginPattern:
    span: SourceSpan


Pattern: TypeAlias = BeginPattern


@dataclass(frozen=True)
class StringLiteralExpr:
    value: str
    raw_text: str
    span: SourceSpan


Expr: TypeAlias = StringLiteralExpr


@dataclass(frozen=True)
class PrintStmt:
    arguments: tuple[Expr, ...]
    span: SourceSpan


Stmt: TypeAlias = PrintStmt


@dataclass(frozen=True)
class Action:
    statements: tuple[Stmt, ...]
    span: SourceSpan


@dataclass(frozen=True)
class PatternAction:
    pattern: Pattern | None
    action: Action | None
    span: SourceSpan


Item: TypeAlias = PatternAction


@dataclass(frozen=True)
class Program:
    items: tuple[Item, ...]
    span: SourceSpan


def parse(tokens: list[Token]) -> Program:
    return Parser(tokens).parse_program()


def format_program(program: Program) -> str:
    lines = [f"Program span={program.span.format_start()}"]
    for item in program.items:
        lines.append(f"  PatternAction span={item.span.format_start()}")
        if item.pattern is not None:
            lines.append(f"    BeginPattern span={item.pattern.span.format_start()}")
        if item.action is not None:
            lines.append(f"    Action span={item.action.span.format_start()}")
            for statement in item.action.statements:
                lines.append(f"      PrintStmt span={statement.span.format_start()}")
                for argument in statement.arguments:
                    lines.append(
                        f"        StringLiteralExpr span={argument.span.format_start()} value={argument.value!r}"
                    )
    return "\n".join(lines) + "\n"


class Parser:

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> Program:
        self.consume_separators()
        item = self.parse_pattern_action()
        self.consume_separators()
        self.expect(TokenKind.EOF)
        return Program(items=(item, ), span=item.span)

    def parse_pattern_action(self) -> PatternAction:
        pattern = self.parse_pattern()
        action = self.parse_action()
        return PatternAction(pattern=pattern, action=action, span=combine_spans(pattern.span, action.span))

    def parse_pattern(self) -> Pattern:
        begin_token = self.expect(TokenKind.BEGIN)
        return BeginPattern(begin_token.span)

    def parse_action(self) -> Action:
        lbrace_token = self.expect(TokenKind.LBRACE)
        self.consume_separators()

        statements: list[Stmt] = []
        if not self.check(TokenKind.RBRACE):
            statements.append(self.parse_statement())
            while self.consume_separators():
                if self.check(TokenKind.RBRACE):
                    break
                statements.append(self.parse_statement())

        rbrace_token = self.expect(TokenKind.RBRACE)
        return Action(tuple(statements), combine_spans(lbrace_token.span, rbrace_token.span))

    def parse_statement(self) -> Stmt:
        return self.parse_print_statement()

    def parse_print_statement(self) -> PrintStmt:
        print_token = self.expect(TokenKind.PRINT)
        argument = self.parse_expression()
        return PrintStmt(arguments=(argument, ), span=combine_spans(print_token.span, argument.span))

    def parse_expression(self) -> Expr:
        token = self.current()
        if token.kind is not TokenKind.STRING:
            raise ParseError(f"expected STRING, got {token.kind.name}", token.span)

        literal_token = self.advance()
        return StringLiteralExpr(
            value=decode_string_literal(literal_token),
            raw_text=literal_token.text or "",
            span=literal_token.span,
        )

    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current()
        if token.kind is not TokenKind.EOF:
            self.index += 1
        return token

    def check(self, kind: TokenKind) -> bool:
        return self.current().kind is kind

    def expect(self, kind: TokenKind) -> Token:
        token = self.current()
        if token.kind is not kind:
            raise ParseError(f"expected {kind.name}, got {token.kind.name}", token.span)
        self.index += 1
        return token

    def consume_separators(self) -> bool:
        consumed = False
        while self.check(TokenKind.NEWLINE) or self.check(TokenKind.SEMICOLON):
            self.advance()
            consumed = True
        return consumed


def decode_string_literal(token: Token) -> str:
    raw_text = token.text or ""
    inner = raw_text[1:-1]
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
