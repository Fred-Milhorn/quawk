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


@dataclass(frozen=True)
class EndPattern:
    span: SourceSpan


@dataclass(frozen=True)
class ExprPattern:
    test: Expr
    span: SourceSpan


Pattern: TypeAlias = BeginPattern | EndPattern | ExprPattern


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
class RegexLiteralExpr:
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


@dataclass(frozen=True)
class CallExpr:
    function: str
    args: tuple[Expr, ...]
    span: SourceSpan


class BinaryOp(Enum):
    ADD = auto()
    LESS = auto()
    EQUAL = auto()
    LOGICAL_AND = auto()


@dataclass(frozen=True)
class BinaryExpr:
    left: Expr
    op: BinaryOp
    right: Expr
    span: SourceSpan


Expr: TypeAlias = (
    StringLiteralExpr | NumericLiteralExpr | RegexLiteralExpr | NameExpr | FieldExpr | CallExpr | BinaryExpr
)


@dataclass(frozen=True)
class PrintStmt:
    arguments: tuple[Expr, ...]
    span: SourceSpan


@dataclass(frozen=True)
class AssignStmt:
    name: str
    value: Expr
    span: SourceSpan


@dataclass(frozen=True)
class BlockStmt:
    statements: tuple[Stmt, ...]
    span: SourceSpan


@dataclass(frozen=True)
class IfStmt:
    condition: Expr
    then_branch: Stmt
    span: SourceSpan


@dataclass(frozen=True)
class WhileStmt:
    condition: Expr
    body: Stmt
    span: SourceSpan


@dataclass(frozen=True)
class ReturnStmt:
    value: Expr | None
    span: SourceSpan


Stmt: TypeAlias = PrintStmt | AssignStmt | BlockStmt | IfStmt | WhileStmt | ReturnStmt


@dataclass(frozen=True)
class Action:
    statements: tuple[Stmt, ...]
    span: SourceSpan


@dataclass(frozen=True)
class PatternAction:
    pattern: Pattern | None
    action: Action | None
    span: SourceSpan


@dataclass(frozen=True)
class FunctionDef:
    name: str
    params: tuple[str, ...]
    body: Action
    span: SourceSpan


Item: TypeAlias = FunctionDef | PatternAction


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
        if isinstance(item, FunctionDef):
            lines.append(f"  FunctionDef span={item.span.format_start()} name={item.name!r}")
            if item.params:
                lines.append(f"    Params {', '.join(repr(param) for param in item.params)}")
            lines.append(f"    Action span={item.body.span.format_start()}")
            for statement in item.body.statements:
                lines.extend(format_statement(statement, "      "))
            continue
        lines.append(f"  PatternAction span={item.span.format_start()}")
        if item.pattern is not None:
            match item.pattern:
                case BeginPattern():
                    lines.append(f"    BeginPattern span={item.pattern.span.format_start()}")
                case EndPattern():
                    lines.append(f"    EndPattern span={item.pattern.span.format_start()}")
                case ExprPattern():
                    lines.append(f"    ExprPattern span={item.pattern.span.format_start()}")
                    lines.extend(format_expression(item.pattern.test, "      "))
        if item.action is not None:
            lines.append(f"    Action span={item.action.span.format_start()}")
            for statement in item.action.statements:
                lines.extend(format_statement(statement, "      "))
    return "\n".join(lines) + "\n"


def format_statement(statement: Stmt, indent: str) -> list[str]:
    """Render a statement node for stable `--parse` inspection output."""
    match statement:
        case PrintStmt():
            lines = [f"{indent}PrintStmt span={statement.span.format_start()}"]
            for argument in statement.arguments:
                lines.extend(format_expression(argument, indent + "  "))
            return lines
        case AssignStmt():
            lines = [f"{indent}AssignStmt span={statement.span.format_start()} name={statement.name!r}"]
            lines.extend(format_expression(statement.value, indent + "  "))
            return lines
        case BlockStmt():
            lines = [f"{indent}BlockStmt span={statement.span.format_start()}"]
            for nested in statement.statements:
                lines.extend(format_statement(nested, indent + "  "))
            return lines
        case IfStmt():
            lines = [f"{indent}IfStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            lines.append(f"{indent}  Then")
            lines.extend(format_statement(statement.then_branch, indent + "    "))
            return lines
        case WhileStmt():
            lines = [f"{indent}WhileStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            return lines
        case ReturnStmt():
            lines = [f"{indent}ReturnStmt span={statement.span.format_start()}"]
            if statement.value is not None:
                lines.extend(format_expression(statement.value, indent + "  "))
            return lines
    raise AssertionError(f"unhandled statement type: {type(statement)!r}")


def format_expression(expression: Expr, indent: str) -> list[str]:
    """Render an expression node for stable `--parse` inspection output."""
    match expression:
        case StringLiteralExpr():
            return [f"{indent}StringLiteralExpr span={expression.span.format_start()} value={expression.value!r}"]
        case NumericLiteralExpr():
            return [f"{indent}NumericLiteralExpr span={expression.span.format_start()} value={expression.value!r}"]
        case RegexLiteralExpr():
            return [f"{indent}RegexLiteralExpr span={expression.span.format_start()} raw_text={expression.raw_text!r}"]
        case NameExpr():
            return [f"{indent}NameExpr span={expression.span.format_start()} name={expression.name!r}"]
        case FieldExpr():
            return [f"{indent}FieldExpr span={expression.span.format_start()} index={expression.index}"]
        case CallExpr():
            lines = [f"{indent}CallExpr span={expression.span.format_start()} function={expression.function!r}"]
            for argument in expression.args:
                lines.extend(format_expression(argument, indent + "  "))
            return lines
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
        items: list[Item] = []
        while not self.check(TokenKind.EOF):
            items.append(self.parse_item())
            self.consume_separators()
        self.expect(TokenKind.EOF)
        if not items:
            token = self.current()
            raise ParseError(f"expected pattern-action, got {token.kind.name}", token.span)
        return Program(
            items=tuple(items),
            span=combine_spans(items[0].span, items[-1].span),
        )

    def parse_item(self) -> Item:
        """Parse one top-level item."""
        if self.check(TokenKind.FUNCTION):
            return self.parse_function_definition()
        return self.parse_pattern_action()

    def parse_function_definition(self) -> FunctionDef:
        """Parse one top-level function definition."""
        function_token = self.expect(TokenKind.FUNCTION)
        name_token = self.expect(TokenKind.IDENT)
        self.expect(TokenKind.LPAREN)
        params = self.parse_parameter_list()
        self.expect(TokenKind.RPAREN)
        body = self.parse_action()
        return FunctionDef(
            name=name_token.text or "",
            params=tuple(params),
            body=body,
            span=combine_spans(function_token.span, body.span),
        )

    def parse_parameter_list(self) -> list[str]:
        """Parse the optional identifier list in one function signature."""
        params: list[str] = []
        if self.check(TokenKind.RPAREN):
            return params

        first_param = self.expect(TokenKind.IDENT)
        params.append(first_param.text or "")
        while self.check(TokenKind.COMMA):
            self.advance()
            param_token = self.expect(TokenKind.IDENT)
            params.append(param_token.text or "")
        return params

    def parse_pattern_action(self) -> PatternAction:
        """Parse one top-level pattern-action item."""
        if self.check(TokenKind.LBRACE):
            action = self.parse_action()
            return PatternAction(pattern=None, action=action, span=action.span)

        pattern = self.parse_pattern()
        action = self.parse_action()
        return PatternAction(pattern=pattern, action=action, span=combine_spans(pattern.span, action.span))

    def parse_pattern(self) -> Pattern:
        """Parse the currently supported pattern form."""
        token = self.current()
        match token.kind:
            case TokenKind.BEGIN:
                begin_token = self.advance()
                return BeginPattern(begin_token.span)
            case TokenKind.END:
                end_token = self.advance()
                return EndPattern(end_token.span)
            case TokenKind.REGEX:
                regex_token = self.advance()
                regex_expr = RegexLiteralExpr(
                    raw_text=regex_token.text or "",
                    span=regex_token.span,
                )
                return ExprPattern(test=regex_expr, span=regex_token.span)
            case _:
                raise ParseError(f"expected pattern, got {token.kind.name}", token.span)

    def parse_action(self) -> Action:
        """Parse a braced action block."""
        lbrace_token, statements, rbrace_token = self.parse_braced_statements()
        return Action(tuple(statements), combine_spans(lbrace_token.span, rbrace_token.span))

    def parse_braced_statements(self) -> tuple[Token, list[Stmt], Token]:
        """Parse a braced statement list shared by actions and block statements."""
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
        return lbrace_token, statements, rbrace_token

    def parse_statement(self) -> Stmt:
        """Parse a statement in the current supported subset."""
        if self.check(TokenKind.LBRACE):
            return self.parse_block_statement()
        if self.check(TokenKind.IF):
            return self.parse_if_statement()
        if self.check(TokenKind.PRINT):
            return self.parse_print_statement()
        if self.check(TokenKind.RETURN):
            return self.parse_return_statement()
        if self.check(TokenKind.WHILE):
            return self.parse_while_statement()
        if self.check(TokenKind.IDENT) and self.peek_kind() is TokenKind.EQUAL:
            return self.parse_assignment_statement()
        token = self.current()
        raise ParseError(f"expected statement, got {token.kind.name}", token.span)

    def parse_block_statement(self) -> BlockStmt:
        """Parse a nested braced block statement."""
        lbrace_token, statements, rbrace_token = self.parse_braced_statements()
        return BlockStmt(tuple(statements), combine_spans(lbrace_token.span, rbrace_token.span))

    def parse_if_statement(self) -> IfStmt:
        """Parse an `if` statement without `else` support."""
        if_token = self.expect(TokenKind.IF)
        condition = self.parse_parenthesized_expression()
        then_branch = self.parse_statement()
        return IfStmt(
            condition=condition,
            then_branch=then_branch,
            span=combine_spans(if_token.span, then_branch.span),
        )

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

    def parse_while_statement(self) -> WhileStmt:
        """Parse a `while` loop statement."""
        while_token = self.expect(TokenKind.WHILE)
        condition = self.parse_parenthesized_expression()
        body = self.parse_statement()
        return WhileStmt(condition=condition, body=body, span=combine_spans(while_token.span, body.span))

    def parse_return_statement(self) -> ReturnStmt:
        """Parse a `return` statement with an optional value expression."""
        return_token = self.expect(TokenKind.RETURN)
        if self.check(TokenKind.RBRACE) or self.check(TokenKind.NEWLINE) or self.check(TokenKind.SEMICOLON):
            return ReturnStmt(value=None, span=return_token.span)

        value = self.parse_expression()
        return ReturnStmt(value=value, span=combine_spans(return_token.span, value.span))

    def parse_expression(self) -> Expr:
        """Parse an expression in the current supported subset."""
        return self.parse_logical_and_expression()

    def parse_parenthesized_expression(self) -> Expr:
        """Parse a parenthesized expression used by control-flow statements."""
        self.expect(TokenKind.LPAREN)
        expression = self.parse_expression()
        self.expect(TokenKind.RPAREN)
        return expression

    def parse_logical_and_expression(self) -> Expr:
        """Parse logical-AND expressions over the supported comparison subset."""
        expression = self.parse_equality_expression()
        while self.check(TokenKind.AND_AND):
            self.advance()
            right = self.parse_equality_expression()
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.LOGICAL_AND,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

    def parse_equality_expression(self) -> Expr:
        """Parse equality expressions over the supported comparison subset."""
        expression = self.parse_comparison_expression()
        while self.check(TokenKind.EQUAL_EQUAL):
            self.advance()
            right = self.parse_comparison_expression()
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.EQUAL,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

    def parse_comparison_expression(self) -> Expr:
        """Parse comparison expressions over the currently supported arithmetic subset."""
        expression = self.parse_additive_expression()
        while self.check(TokenKind.LESS):
            self.advance()
            right = self.parse_additive_expression()
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.LESS,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

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
                if self.peek_kind() is TokenKind.LPAREN:
                    return self.parse_call_expression()
                name_token = self.advance()
                return NameExpr(name=name_token.text or "", span=name_token.span)
            case TokenKind.DOLLAR:
                dollar_token = self.advance()
                number_token = self.expect(TokenKind.NUMBER)
                raw_text = number_token.text or ""
                if "." in raw_text:
                    raise ParseError("field index must be an integer literal", number_token.span)
                return FieldExpr(index=int(raw_text), span=combine_spans(dollar_token.span, number_token.span))
            case TokenKind.LPAREN:
                return self.parse_parenthesized_expression()
            case _:
                raise ParseError(f"expected expression, got {token.kind.name}", token.span)

    def parse_call_expression(self) -> CallExpr:
        """Parse one function call expression."""
        name_token = self.expect(TokenKind.IDENT)
        self.expect(TokenKind.LPAREN)
        args: list[Expr] = []
        if not self.check(TokenKind.RPAREN):
            args.append(self.parse_expression())
            while self.check(TokenKind.COMMA):
                self.advance()
                args.append(self.parse_expression())
        rparen_token = self.expect(TokenKind.RPAREN)
        return CallExpr(
            function=name_token.text or "",
            args=tuple(args),
            span=combine_spans(name_token.span, rparen_token.span),
        )

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
