# Parser and AST definitions for the current language subset.
# This module lowers the token stream into the generalized AST categories that
# the rest of the compiler is meant to grow around.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
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


@dataclass(frozen=True)
class NumericLiteralExpr:
    value: float
    raw_text: str
    span: SourceSpan


@dataclass(frozen=True)
class NameExpr:
    name: str
    span: SourceSpan


@dataclass(frozen=True)
class FieldExpr:
    index: int
    span: SourceSpan


class BinaryOp(Enum):
    ADD = auto()


@dataclass(frozen=True)
class BinaryExpr:
    left: Expr
    op: BinaryOp
    right: Expr
    span: SourceSpan


Expr: TypeAlias = StringLiteralExpr | NumericLiteralExpr | NameExpr | FieldExpr | BinaryExpr


@dataclass(frozen=True)
class PrintStmt:
    arguments: tuple[Expr, ...]
    span: SourceSpan


@dataclass(frozen=True)
class AssignStmt:
    name: str
    value: Expr
    span: SourceSpan


Stmt: TypeAlias = PrintStmt | AssignStmt


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
    """Parse tokens into the generalized AST for the current supported subset."""
    return Parser(tokens).parse_program()


def format_program(program: Program) -> str:
    """Render the AST in a stable text form for `quawk --parse`."""
    lines = [f"Program span={program.span.format_start()}"]
    for item in program.items:
        lines.append(f"  PatternAction span={item.span.format_start()}")
        if item.pattern is not None:
            lines.append(f"    BeginPattern span={item.pattern.span.format_start()}")
        if item.action is not None:
            lines.append(f"    Action span={item.action.span.format_start()}")
            for statement in item.action.statements:
                match statement:
                    case PrintStmt():
                        lines.append(f"      PrintStmt span={statement.span.format_start()}")
                        for argument in statement.arguments:
                            lines.extend(format_expression(argument, "        "))
                    case AssignStmt():
                        lines.append(f"      AssignStmt span={statement.span.format_start()} name={statement.name!r}")
                        lines.extend(format_expression(statement.value, "        "))
    return "\n".join(lines) + "\n"


def format_expression(expression: Expr, indent: str) -> list[str]:
    """Render an expression node for stable `--parse` inspection output."""
    match expression:
        case StringLiteralExpr():
            return [f"{indent}StringLiteralExpr span={expression.span.format_start()} value={expression.value!r}"]
        case NumericLiteralExpr():
            return [f"{indent}NumericLiteralExpr span={expression.span.format_start()} value={expression.value!r}"]
        case NameExpr():
            return [f"{indent}NameExpr span={expression.span.format_start()} name={expression.name!r}"]
        case FieldExpr():
            return [f"{indent}FieldExpr span={expression.span.format_start()} index={expression.index}"]
        case BinaryExpr():
            lines = [f"{indent}BinaryExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.left, indent + "  "))
            lines.extend(format_expression(expression.right, indent + "  "))
            return lines
    raise AssertionError(f"unhandled expression type: {type(expression)!r}")


class Parser:
    """Recursive-descent parser for the currently supported grammar subset."""

    def __init__(self, tokens: list[Token]) -> None:
        """Create a parser over an already-tokenized input stream."""
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> Program:
        """Parse the whole program and require EOF afterward."""
        self.consume_separators()
        item = self.parse_pattern_action()
        self.consume_separators()
        self.expect(TokenKind.EOF)
        return Program(items=(item, ), span=item.span)

    def parse_pattern_action(self) -> PatternAction:
        """Parse the single top-level pattern-action the current subset supports."""
        if self.check(TokenKind.LBRACE):
            action = self.parse_action()
            return PatternAction(pattern=None, action=action, span=action.span)

        pattern = self.parse_pattern()
        action = self.parse_action()
        return PatternAction(pattern=pattern, action=action, span=combine_spans(pattern.span, action.span))

    def parse_pattern(self) -> Pattern:
        """Parse the currently supported pattern form."""
        begin_token = self.expect(TokenKind.BEGIN)
        return BeginPattern(begin_token.span)

    def parse_action(self) -> Action:
        """Parse a braced action block."""
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
        """Parse a statement in the current supported subset."""
        if self.check(TokenKind.PRINT):
            return self.parse_print_statement()
        if self.check(TokenKind.IDENT) and self.peek_kind() is TokenKind.EQUAL:
            return self.parse_assignment_statement()
        token = self.current()
        raise ParseError(f"expected statement, got {token.kind.name}", token.span)

    def parse_print_statement(self) -> PrintStmt:
        """Parse a `print` statement with the currently supported argument form."""
        print_token = self.expect(TokenKind.PRINT)
        argument = self.parse_expression()
        return PrintStmt(arguments=(argument, ), span=combine_spans(print_token.span, argument.span))

    def parse_assignment_statement(self) -> AssignStmt:
        """Parse a scalar assignment statement in the current subset."""
        name_token = self.expect(TokenKind.IDENT)
        self.expect(TokenKind.EQUAL)
        value = self.parse_expression()
        return AssignStmt(
            name=name_token.text or "",
            value=value,
            span=combine_spans(name_token.span, value.span),
        )

    def parse_expression(self) -> Expr:
        """Parse an expression in the current supported subset."""
        return self.parse_additive_expression()

    def parse_additive_expression(self) -> Expr:
        """Parse the currently supported additive expression subset."""
        expression = self.parse_primary_expression()
        while self.check(TokenKind.PLUS):
            self.advance()
            right = self.parse_primary_expression()
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.ADD,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

    def parse_primary_expression(self) -> Expr:
        """Parse a primary expression in the current subset."""
        token = self.current()
        match token.kind:
            case TokenKind.STRING:
                literal_token = self.advance()
                return StringLiteralExpr(
                    value=decode_string_literal(literal_token),
                    raw_text=literal_token.text or "",
                    span=literal_token.span,
                )
            case TokenKind.NUMBER:
                literal_token = self.advance()
                raw_text = literal_token.text or ""
                return NumericLiteralExpr(
                    value=float(raw_text),
                    raw_text=raw_text,
                    span=literal_token.span,
                )
            case TokenKind.IDENT:
                name_token = self.advance()
                return NameExpr(name=name_token.text or "", span=name_token.span)
            case TokenKind.DOLLAR:
                dollar_token = self.advance()
                number_token = self.expect(TokenKind.NUMBER)
                raw_text = number_token.text or ""
                if "." in raw_text:
                    raise ParseError("field index must be an integer literal", number_token.span)
                return FieldExpr(index=int(raw_text), span=combine_spans(dollar_token.span, number_token.span))
            case _:
                raise ParseError(f"expected expression, got {token.kind.name}", token.span)

    def current(self) -> Token:
        """Return the current token without consuming it."""
        return self.tokens[self.index]

    def advance(self) -> Token:
        """Consume and return the current token."""
        token = self.current()
        if token.kind is not TokenKind.EOF:
            self.index += 1
        return token

    def check(self, kind: TokenKind) -> bool:
        """Report whether the current token has `kind`."""
        return self.current().kind is kind

    def peek_kind(self) -> TokenKind:
        """Return the kind of the next token without consuming it."""
        next_index = min(self.index + 1, len(self.tokens) - 1)
        return self.tokens[next_index].kind

    def expect(self, kind: TokenKind) -> Token:
        """Consume a token of `kind` or raise a parse error at the current span."""
        token = self.current()
        if token.kind is not kind:
            raise ParseError(f"expected {kind.name}, got {token.kind.name}", token.span)
        self.index += 1
        return token

    def consume_separators(self) -> bool:
        """Consume statement separators and report whether any were present."""
        consumed = False
        while self.check(TokenKind.NEWLINE) or self.check(TokenKind.SEMICOLON):
            self.advance()
            consumed = True
        return consumed


def decode_string_literal(token: Token) -> str:
    """Decode the raw text of a string token into its runtime value."""
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
