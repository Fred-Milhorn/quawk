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


@dataclass(frozen=True)
class RangePattern:
    left: Pattern
    right: Pattern
    span: SourceSpan


Pattern: TypeAlias = BeginPattern | EndPattern | ExprPattern | RangePattern


@dataclass(frozen=True)
class NameLValue:
    name: str
    span: SourceSpan


@dataclass(frozen=True)
class ArrayLValue:
    name: str
    subscripts: tuple[Expr, ...]
    span: SourceSpan


@dataclass(frozen=True)
class FieldLValue:
    index: Expr
    span: SourceSpan


LValue: TypeAlias = NameLValue | ArrayLValue | FieldLValue


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
    index: int | Expr
    span: SourceSpan


@dataclass(frozen=True)
class CallExpr:
    function: str
    args: tuple[Expr, ...]
    span: SourceSpan


@dataclass(frozen=True)
class ArrayIndexExpr:
    array_name: str
    index: Expr
    extra_indexes: tuple[Expr, ...]
    span: SourceSpan

    @property
    def subscripts(self) -> tuple[Expr, ...]:
        """Return the full array subscript list."""
        return (self.index, *self.extra_indexes)


class AssignOp(Enum):
    PLAIN = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    POW = auto()


class BinaryOp(Enum):
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    POW = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    LOGICAL_AND = auto()
    LOGICAL_OR = auto()
    MATCH = auto()
    NOT_MATCH = auto()
    IN = auto()
    CONCAT = auto()


class OutputRedirectKind(Enum):
    WRITE = auto()
    APPEND = auto()
    PIPE = auto()


@dataclass(frozen=True)
class GetlineExpr:
    target: LValue | None
    source: Expr | None
    span: SourceSpan


@dataclass(frozen=True)
class BinaryExpr:
    left: Expr
    op: BinaryOp
    right: Expr
    span: SourceSpan


@dataclass(frozen=True)
class ConditionalExpr:
    test: Expr
    if_true: Expr
    if_false: Expr
    span: SourceSpan


@dataclass(frozen=True)
class AssignExpr:
    target: LValue
    op: AssignOp
    value: Expr
    span: SourceSpan


class UnaryOp(Enum):
    UPLUS = auto()
    UMINUS = auto()
    NOT = auto()
    PRE_INC = auto()
    PRE_DEC = auto()


@dataclass(frozen=True)
class UnaryExpr:
    op: UnaryOp
    operand: Expr
    span: SourceSpan


class PostfixOp(Enum):
    POST_INC = auto()
    POST_DEC = auto()


@dataclass(frozen=True)
class PostfixExpr:
    operand: Expr
    op: PostfixOp
    span: SourceSpan


Expr: TypeAlias = (
    StringLiteralExpr
    | NumericLiteralExpr
    | RegexLiteralExpr
    | NameExpr
    | FieldExpr
    | CallExpr
    | ArrayIndexExpr
    | GetlineExpr
    | BinaryExpr
    | ConditionalExpr
    | AssignExpr
    | UnaryExpr
    | PostfixExpr
)


@dataclass(frozen=True)
class OutputRedirect:
    kind: OutputRedirectKind
    target: Expr
    span: SourceSpan


@dataclass(frozen=True)
class PrintStmt:
    arguments: tuple[Expr, ...]
    span: SourceSpan
    redirect: OutputRedirect | None = None


@dataclass(frozen=True)
class PrintfStmt:
    arguments: tuple[Expr, ...]
    span: SourceSpan
    redirect: OutputRedirect | None = None


@dataclass(frozen=True)
class AssignStmt:
    target: LValue
    op: AssignOp
    value: Expr
    span: SourceSpan

    @property
    def name(self) -> str | None:
        """Return the assigned scalar or array name when present."""
        match self.target:
            case NameLValue(name=name) | ArrayLValue(name=name):
                return name
            case _:
                return None

    @property
    def index(self) -> Expr | None:
        """Return the first array subscript when present."""
        if isinstance(self.target, ArrayLValue) and self.target.subscripts:
            return self.target.subscripts[0]
        return None

    @property
    def extra_indexes(self) -> tuple[Expr, ...]:
        """Return any remaining array subscripts after the first."""
        if isinstance(self.target, ArrayLValue):
            return self.target.subscripts[1:]
        return ()

    @property
    def field_index(self) -> Expr | None:
        """Return the field lvalue index when present."""
        if isinstance(self.target, FieldLValue):
            return self.target.index
        return None


@dataclass(frozen=True)
class BlockStmt:
    statements: tuple[Stmt, ...]
    span: SourceSpan


@dataclass(frozen=True)
class BreakStmt:
    span: SourceSpan


@dataclass(frozen=True)
class ContinueStmt:
    span: SourceSpan


@dataclass(frozen=True)
class NextStmt:
    span: SourceSpan


@dataclass(frozen=True)
class NextFileStmt:
    span: SourceSpan


@dataclass(frozen=True)
class ExitStmt:
    value: Expr | None
    span: SourceSpan


@dataclass(frozen=True)
class ExprStmt:
    value: Expr
    span: SourceSpan


@dataclass(frozen=True)
class DeleteStmt:
    target: LValue
    span: SourceSpan

    @property
    def array_name(self) -> str | None:
        """Return the deleted name when present."""
        match self.target:
            case NameLValue(name=name) | ArrayLValue(name=name):
                return name
            case _:
                return None

    @property
    def index(self) -> Expr | None:
        """Return the first deleted array subscript when present."""
        if isinstance(self.target, ArrayLValue) and self.target.subscripts:
            return self.target.subscripts[0]
        return None

    @property
    def extra_indexes(self) -> tuple[Expr, ...]:
        """Return any remaining deleted array subscripts after the first."""
        if isinstance(self.target, ArrayLValue):
            return self.target.subscripts[1:]
        return ()


@dataclass(frozen=True)
class IfStmt:
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None
    span: SourceSpan


@dataclass(frozen=True)
class WhileStmt:
    condition: Expr
    body: Stmt
    span: SourceSpan


@dataclass(frozen=True)
class DoWhileStmt:
    body: Stmt
    condition: Expr
    span: SourceSpan


@dataclass(frozen=True)
class ForStmt:
    init: tuple[Expr, ...]
    condition: Expr | None
    update: tuple[Expr, ...]
    body: Stmt
    span: SourceSpan


@dataclass(frozen=True)
class ForInStmt:
    name: str
    iterable: Expr
    body: Stmt
    span: SourceSpan

    @property
    def array_name(self) -> str | None:
        """Return the iterated array name when the iterable is a bare name."""
        if isinstance(self.iterable, NameExpr):
            return self.iterable.name
        return None


@dataclass(frozen=True)
class ReturnStmt:
    value: Expr | None
    span: SourceSpan


Stmt: TypeAlias = (
    PrintStmt
    | PrintfStmt
    | AssignStmt
    | BlockStmt
    | BreakStmt
    | ContinueStmt
    | NextStmt
    | NextFileStmt
    | ExitStmt
    | DeleteStmt
    | IfStmt
    | WhileStmt
    | DoWhileStmt
    | ForStmt
    | ForInStmt
    | ExprStmt
    | ReturnStmt
)


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
    param_spans: tuple[SourceSpan, ...]
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
            lines.extend(format_pattern(item.pattern, "    "))
        if item.action is not None:
            lines.append(f"    Action span={item.action.span.format_start()}")
            for statement in item.action.statements:
                lines.extend(format_statement(statement, "      "))
    return "\n".join(lines) + "\n"


def format_pattern(pattern: Pattern, indent: str) -> list[str]:
    """Render one pattern node for stable inspection output."""
    match pattern:
        case BeginPattern():
            return [f"{indent}BeginPattern span={pattern.span.format_start()}"]
        case EndPattern():
            return [f"{indent}EndPattern span={pattern.span.format_start()}"]
        case ExprPattern():
            lines = [f"{indent}ExprPattern span={pattern.span.format_start()}"]
            lines.extend(format_expression(pattern.test, indent + "  "))
            return lines
        case RangePattern():
            lines = [f"{indent}RangePattern span={pattern.span.format_start()}"]
            lines.append(f"{indent}  Left")
            lines.extend(format_pattern(pattern.left, indent + "    "))
            lines.append(f"{indent}  Right")
            lines.extend(format_pattern(pattern.right, indent + "    "))
            return lines
    raise AssertionError(f"unhandled pattern type: {type(pattern)!r}")


def format_lvalue(target: LValue, indent: str) -> list[str]:
    """Render one lvalue node for stable inspection output."""
    match target:
        case NameLValue():
            return [f"{indent}NameLValue span={target.span.format_start()} name={target.name!r}"]
        case ArrayLValue():
            lines = [f"{indent}ArrayLValue span={target.span.format_start()} name={target.name!r}"]
            for subscript in target.subscripts:
                lines.extend(format_expression(subscript, indent + "  "))
            return lines
        case FieldLValue():
            lines = [f"{indent}FieldLValue span={target.span.format_start()}"]
            lines.extend(format_expression(target.index, indent + "  "))
            return lines
    raise AssertionError(f"unhandled lvalue type: {type(target)!r}")


def format_assign_op(op: AssignOp) -> str:
    """Return the stable inspection name for one assignment operator."""
    match op:
        case AssignOp.PLAIN:
            return "PlainAssign"
        case AssignOp.ADD:
            return "AddAssign"
        case AssignOp.SUB:
            return "SubAssign"
        case AssignOp.MUL:
            return "MulAssign"
        case AssignOp.DIV:
            return "DivAssign"
        case AssignOp.MOD:
            return "ModAssign"
        case AssignOp.POW:
            return "PowAssign"
    raise AssertionError(f"unhandled assign op: {op!r}")


def format_statement(statement: Stmt, indent: str) -> list[str]:
    """Render a statement node for stable `--parse` inspection output."""
    match statement:
        case PrintStmt():
            lines = [f"{indent}PrintStmt span={statement.span.format_start()}"]
            for argument in statement.arguments:
                lines.extend(format_expression(argument, indent + "  "))
            if statement.redirect is not None:
                lines.append(f"{indent}  Redirect kind={statement.redirect.kind.name}")
                lines.extend(format_expression(statement.redirect.target, indent + "    "))
            return lines
        case PrintfStmt():
            lines = [f"{indent}PrintfStmt span={statement.span.format_start()}"]
            for argument in statement.arguments:
                lines.extend(format_expression(argument, indent + "  "))
            if statement.redirect is not None:
                lines.append(f"{indent}  Redirect kind={statement.redirect.kind.name}")
                lines.extend(format_expression(statement.redirect.target, indent + "    "))
            return lines
        case AssignStmt():
            lines = [
                (
                    f"{indent}AssignStmt span={statement.span.format_start()} "
                    f"op={format_assign_op(statement.op)}"
                )
            ]
            lines.extend(format_lvalue(statement.target, indent + "  "))
            lines.append(f"{indent}  Value")
            lines.extend(format_expression(statement.value, indent + "    "))
            return lines
        case ExprStmt():
            lines = [f"{indent}ExprStmt span={statement.span.format_start()}"]
            lines.extend(format_expression(statement.value, indent + "  "))
            return lines
        case BlockStmt():
            lines = [f"{indent}BlockStmt span={statement.span.format_start()}"]
            for nested in statement.statements:
                lines.extend(format_statement(nested, indent + "  "))
            return lines
        case BreakStmt():
            return [f"{indent}BreakStmt span={statement.span.format_start()}"]
        case ContinueStmt():
            return [f"{indent}ContinueStmt span={statement.span.format_start()}"]
        case NextStmt():
            return [f"{indent}NextStmt span={statement.span.format_start()}"]
        case NextFileStmt():
            return [f"{indent}NextFileStmt span={statement.span.format_start()}"]
        case ExitStmt():
            lines = [f"{indent}ExitStmt span={statement.span.format_start()}"]
            if statement.value is not None:
                lines.extend(format_expression(statement.value, indent + "  "))
            return lines
        case DeleteStmt():
            lines = [f"{indent}DeleteStmt span={statement.span.format_start()}"]
            lines.extend(format_lvalue(statement.target, indent + "  "))
            return lines
        case IfStmt():
            lines = [f"{indent}IfStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            lines.append(f"{indent}  Then")
            lines.extend(format_statement(statement.then_branch, indent + "    "))
            if statement.else_branch is not None:
                lines.append(f"{indent}  Else")
                lines.extend(format_statement(statement.else_branch, indent + "    "))
            return lines
        case WhileStmt():
            lines = [f"{indent}WhileStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            return lines
        case DoWhileStmt():
            lines = [f"{indent}DoWhileStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            return lines
        case ForStmt():
            lines = [f"{indent}ForStmt span={statement.span.format_start()}"]
            if statement.init:
                lines.append(f"{indent}  Init")
                for expression in statement.init:
                    lines.extend(format_expression(expression, indent + "    "))
            if statement.condition is not None:
                lines.append(f"{indent}  Condition")
                lines.extend(format_expression(statement.condition, indent + "    "))
            if statement.update:
                lines.append(f"{indent}  Update")
                for expression in statement.update:
                    lines.extend(format_expression(expression, indent + "    "))
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            return lines
        case ForInStmt():
            lines = [
                (
                    f"{indent}ForInStmt span={statement.span.format_start()} "
                    f"name={statement.name!r}"
                )
            ]
            lines.append(f"{indent}  Iterable")
            lines.extend(format_expression(statement.iterable, indent + "    "))
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
            if isinstance(expression.index, int):
                return [f"{indent}FieldExpr span={expression.span.format_start()} index={expression.index}"]
            lines = [f"{indent}FieldExpr span={expression.span.format_start()}"]
            lines.extend(format_expression(expression.index, indent + "  "))
            return lines
        case CallExpr():
            lines = [f"{indent}CallExpr span={expression.span.format_start()} function={expression.function!r}"]
            for argument in expression.args:
                lines.extend(format_expression(argument, indent + "  "))
            return lines
        case ArrayIndexExpr():
            lines = [
                (
                    f"{indent}ArrayIndexExpr span={expression.span.format_start()} "
                    f"array_name={expression.array_name!r}"
                )
            ]
            for subscript in expression.subscripts:
                lines.extend(format_expression(subscript, indent + "  "))
            return lines
        case GetlineExpr():
            lines = [f"{indent}GetlineExpr span={expression.span.format_start()}"]
            if expression.target is not None:
                lines.append(f"{indent}  Target")
                lines.extend(format_lvalue(expression.target, indent + "    "))
            if expression.source is not None:
                lines.append(f"{indent}  Source")
                lines.extend(format_expression(expression.source, indent + "    "))
            return lines
        case BinaryExpr():
            lines = [f"{indent}BinaryExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.left, indent + "  "))
            lines.extend(format_expression(expression.right, indent + "  "))
            return lines
        case ConditionalExpr():
            lines = [f"{indent}ConditionalExpr span={expression.span.format_start()}"]
            lines.append(f"{indent}  Test")
            lines.extend(format_expression(expression.test, indent + "    "))
            lines.append(f"{indent}  IfTrue")
            lines.extend(format_expression(expression.if_true, indent + "    "))
            lines.append(f"{indent}  IfFalse")
            lines.extend(format_expression(expression.if_false, indent + "    "))
            return lines
        case AssignExpr():
            lines = [
                (
                    f"{indent}AssignExpr span={expression.span.format_start()} "
                    f"op={format_assign_op(expression.op)}"
                )
            ]
            lines.extend(format_lvalue(expression.target, indent + "  "))
            lines.append(f"{indent}  Value")
            lines.extend(format_expression(expression.value, indent + "    "))
            return lines
        case UnaryExpr():
            lines = [f"{indent}UnaryExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.operand, indent + "  "))
            return lines
        case PostfixExpr():
            lines = [f"{indent}PostfixExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.operand, indent + "  "))
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
        params, param_spans = self.parse_parameter_list()
        self.expect(TokenKind.RPAREN)
        body = self.parse_action()
        return FunctionDef(
            name=name_token.text or "",
            params=tuple(params),
            param_spans=tuple(param_spans),
            body=body,
            span=combine_spans(function_token.span, body.span),
        )

    def parse_parameter_list(self) -> tuple[list[str], list[SourceSpan]]:
        """Parse the optional identifier list in one function signature."""
        params: list[str] = []
        param_spans: list[SourceSpan] = []
        if self.check(TokenKind.RPAREN):
            return params, param_spans

        first_param = self.expect(TokenKind.IDENT)
        params.append(first_param.text or "")
        param_spans.append(first_param.span)
        while self.check(TokenKind.COMMA):
            self.advance()
            param_token = self.expect(TokenKind.IDENT)
            params.append(param_token.text or "")
            param_spans.append(param_token.span)
        return params, param_spans

    def parse_pattern_action(self) -> PatternAction:
        """Parse one top-level pattern-action item."""
        if self.check(TokenKind.LBRACE):
            bare_action = self.parse_action()
            return PatternAction(pattern=None, action=bare_action, span=bare_action.span)

        pattern = self.parse_pattern()
        action: Action | None = self.parse_action() if self.check(TokenKind.LBRACE) else None
        if action is None:
            return PatternAction(pattern=pattern, action=None, span=pattern.span)
        return PatternAction(pattern=pattern, action=action, span=combine_spans(pattern.span, action.span))

    def parse_pattern(self) -> Pattern:
        """Parse one top-level pattern, including range patterns."""
        pattern = self.parse_pattern_atom()
        if self.check(TokenKind.COMMA):
            self.advance()
            right = self.parse_pattern_atom()
            return RangePattern(left=pattern, right=right, span=combine_spans(pattern.span, right.span))
        return pattern

    def parse_pattern_atom(self) -> Pattern:
        """Parse one non-range pattern atom."""
        token = self.current()
        match token.kind:
            case TokenKind.BEGIN:
                begin_token = self.advance()
                return BeginPattern(begin_token.span)
            case TokenKind.END:
                end_token = self.advance()
                return EndPattern(end_token.span)
            case _:
                expression = self.parse_expression()
                return ExprPattern(test=expression, span=expression.span)

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
        if self.check(TokenKind.BREAK):
            return self.parse_break_statement()
        if self.check(TokenKind.CONTINUE):
            return self.parse_continue_statement()
        if self.check(TokenKind.DELETE):
            return self.parse_delete_statement()
        if self.check(TokenKind.DO):
            return self.parse_do_while_statement()
        if self.check(TokenKind.EXIT):
            return self.parse_exit_statement()
        if self.check(TokenKind.FOR):
            return self.parse_for_statement()
        if self.check(TokenKind.IF):
            return self.parse_if_statement()
        if self.check(TokenKind.NEXT):
            return self.parse_next_statement()
        if self.check(TokenKind.NEXTFILE):
            return self.parse_nextfile_statement()
        if self.check(TokenKind.PRINT):
            return self.parse_print_statement()
        if self.check(TokenKind.PRINTF):
            return self.parse_printf_statement()
        if self.check(TokenKind.RETURN):
            return self.parse_return_statement()
        if self.check(TokenKind.WHILE):
            return self.parse_while_statement()
        if not is_expression_start(self.current().kind):
            token = self.current()
            raise ParseError(f"expected statement, got {token.kind.name}", token.span)
        return self.parse_expression_statement()

    def parse_block_statement(self) -> BlockStmt:
        """Parse a nested braced block statement."""
        lbrace_token, statements, rbrace_token = self.parse_braced_statements()
        return BlockStmt(tuple(statements), combine_spans(lbrace_token.span, rbrace_token.span))

    def parse_break_statement(self) -> BreakStmt:
        """Parse a `break` statement."""
        break_token = self.expect(TokenKind.BREAK)
        return BreakStmt(span=break_token.span)

    def parse_continue_statement(self) -> ContinueStmt:
        """Parse a `continue` statement."""
        continue_token = self.expect(TokenKind.CONTINUE)
        return ContinueStmt(span=continue_token.span)

    def parse_delete_statement(self) -> DeleteStmt:
        """Parse a `delete` statement over the supported lvalue forms."""
        delete_token = self.expect(TokenKind.DELETE)
        target = self.parse_lvalue()
        return DeleteStmt(target=target, span=combine_spans(delete_token.span, target.span))

    def parse_do_while_statement(self) -> DoWhileStmt:
        """Parse a `do ... while` statement."""
        do_token = self.expect(TokenKind.DO)
        body = self.parse_statement()
        self.expect(TokenKind.WHILE)
        condition = self.parse_parenthesized_expression()
        return DoWhileStmt(body=body, condition=condition, span=combine_spans(do_token.span, condition.span))

    def parse_for_statement(self) -> ForStmt | ForInStmt:
        """Parse either a classic `for` loop or a `for (name in array)` loop."""
        for_token = self.expect(TokenKind.FOR)
        self.expect(TokenKind.LPAREN)
        if self.check(TokenKind.IDENT) and self.peek_kind() is TokenKind.IN:
            name_token = self.expect(TokenKind.IDENT)
            self.expect(TokenKind.IN)
            iterable = self.parse_expression()
            self.expect(TokenKind.RPAREN)
            body = self.parse_statement()
            return ForInStmt(
                name=name_token.text or "",
                iterable=iterable,
                body=body,
                span=combine_spans(for_token.span, body.span),
            )

        init: tuple[Expr, ...] = ()
        condition: Expr | None = None
        update: tuple[Expr, ...] = ()

        if not self.check(TokenKind.SEMICOLON):
            init = tuple(self.parse_expression_list())
        self.expect(TokenKind.SEMICOLON)

        if not self.check(TokenKind.SEMICOLON):
            condition = self.parse_expression()
        self.expect(TokenKind.SEMICOLON)

        if not self.check(TokenKind.RPAREN):
            update = tuple(self.parse_expression_list())
        self.expect(TokenKind.RPAREN)

        body = self.parse_statement()
        return ForStmt(
            init=init,
            condition=condition,
            update=update,
            body=body,
            span=combine_spans(for_token.span, body.span),
        )

    def parse_if_statement(self) -> IfStmt:
        """Parse an `if` statement with optional `else` support."""
        if_token = self.expect(TokenKind.IF)
        condition = self.parse_parenthesized_expression()
        then_branch = self.parse_statement()
        else_branch = None
        self.consume_separators()
        if self.check(TokenKind.ELSE):
            self.advance()
            else_branch = self.parse_statement()
        return IfStmt(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            span=combine_spans(if_token.span, (else_branch or then_branch).span),
        )

    def parse_print_statement(self) -> PrintStmt:
        """Parse a `print` statement with an optional expression list."""
        print_token = self.expect(TokenKind.PRINT)
        if self.is_statement_terminator():
            return PrintStmt(arguments=(), span=print_token.span)
        arguments: list[Expr] = []
        if not self.is_output_redirect_start():
            arguments = self.parse_expression_list(PRINT_REDIRECT_START_KINDS)
        redirect = self.parse_output_redirect() if self.is_output_redirect_start() else None
        statement_end = redirect.span if redirect is not None else arguments[-1].span
        return PrintStmt(
            arguments=tuple(arguments),
            redirect=redirect,
            span=combine_spans(print_token.span, statement_end),
        )

    def parse_printf_statement(self) -> PrintfStmt:
        """Parse a `printf` statement."""
        printf_token = self.expect(TokenKind.PRINTF)
        if self.check(TokenKind.LPAREN):
            self.advance()
            arguments = self.parse_expression_list(frozenset({TokenKind.RPAREN}))
            rparen_token = self.expect(TokenKind.RPAREN)
            statement_end_span = rparen_token.span
        else:
            arguments = self.parse_expression_list(PRINT_REDIRECT_START_KINDS)
            statement_end_span = arguments[-1].span
        redirect = self.parse_output_redirect() if self.is_output_redirect_start() else None
        statement_end = redirect.span if redirect is not None else statement_end_span
        return PrintfStmt(
            arguments=tuple(arguments),
            redirect=redirect,
            span=combine_spans(printf_token.span, statement_end),
        )

    def parse_assignment_statement(self) -> AssignStmt:
        """Parse an assignment statement in the current statement position."""
        expression = self.parse_expression()
        if not isinstance(expression, AssignExpr):
            raise ParseError("expected assignment expression", expression.span)
        return AssignStmt(target=expression.target, op=expression.op, value=expression.value, span=expression.span)

    def parse_expression_statement(self) -> AssignStmt | ExprStmt:
        """Parse a generic expression statement, folding bare assignments into statements."""
        expression = self.parse_expression()
        if isinstance(expression, AssignExpr):
            return AssignStmt(target=expression.target, op=expression.op, value=expression.value, span=expression.span)
        return ExprStmt(value=expression, span=expression.span)

    def parse_while_statement(self) -> WhileStmt:
        """Parse a `while` loop statement."""
        while_token = self.expect(TokenKind.WHILE)
        condition = self.parse_parenthesized_expression()
        body = self.parse_statement()
        return WhileStmt(condition=condition, body=body, span=combine_spans(while_token.span, body.span))

    def parse_next_statement(self) -> NextStmt:
        """Parse a `next` statement."""
        next_token = self.expect(TokenKind.NEXT)
        return NextStmt(span=next_token.span)

    def parse_nextfile_statement(self) -> NextFileStmt:
        """Parse a `nextfile` statement."""
        nextfile_token = self.expect(TokenKind.NEXTFILE)
        return NextFileStmt(span=nextfile_token.span)

    def parse_exit_statement(self) -> ExitStmt:
        """Parse an `exit` statement with an optional value."""
        exit_token = self.expect(TokenKind.EXIT)
        if self.is_statement_terminator():
            return ExitStmt(value=None, span=exit_token.span)
        value = self.parse_expression()
        return ExitStmt(value=value, span=combine_spans(exit_token.span, value.span))

    def parse_return_statement(self) -> ReturnStmt:
        """Parse a `return` statement with an optional value expression."""
        return_token = self.expect(TokenKind.RETURN)
        if self.is_statement_terminator():
            return ReturnStmt(value=None, span=return_token.span)

        value = self.parse_expression()
        return ReturnStmt(value=value, span=combine_spans(return_token.span, value.span))

    def parse_expression(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> Expr:
        """Parse an expression with the current precedence rules."""
        return self.parse_assignment_expression(stop_kinds)

    def parse_parenthesized_expression(self) -> Expr:
        """Parse a parenthesized expression used by control-flow statements."""
        self.expect(TokenKind.LPAREN)
        expression = self.parse_expression()
        self.expect(TokenKind.RPAREN)
        return expression

    def parse_assignment_expression(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> Expr:
        """Parse assignment expressions with right associativity."""
        expression = self.parse_conditional_expression(stop_kinds)
        if self.current().kind in ASSIGNMENT_TOKEN_KINDS:
            target = expression_to_lvalue(expression)
            if target is None:
                raise ParseError("expected assignable expression on left-hand side", expression.span)
            op_token = self.advance()
            value = self.parse_assignment_expression()
            return AssignExpr(
                target=target,
                op=assignment_op_from_token(op_token.kind),
                value=value,
                span=combine_spans(expression.span, value.span),
            )
        return expression

    def parse_conditional_expression(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> Expr:
        """Parse ternary conditional expressions."""
        expression = self.parse_logical_or_expression(stop_kinds)
        if not self.check(TokenKind.QUESTION):
            return expression
        self.advance()
        if_true = self.parse_expression()
        self.expect(TokenKind.COLON)
        if_false = self.parse_conditional_expression()
        return ConditionalExpr(
            test=expression,
            if_true=if_true,
            if_false=if_false,
            span=combine_spans(expression.span, if_false.span),
        )

    def parse_logical_or_expression(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> Expr:
        """Parse logical-OR expressions."""
        expression = self.parse_logical_and_expression(stop_kinds)
        while self.check(TokenKind.OR_OR):
            self.advance()
            right = self.parse_logical_and_expression(stop_kinds)
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.LOGICAL_OR,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

    def parse_logical_and_expression(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> Expr:
        """Parse logical-AND expressions."""
        expression = self.parse_comparison_expression(stop_kinds)
        while self.check(TokenKind.AND_AND):
            self.advance()
            right = self.parse_comparison_expression(stop_kinds)
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.LOGICAL_AND,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

    def parse_comparison_expression(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> Expr:
        """Parse equality and relational comparisons."""
        expression = self.parse_match_expression()
        while True:
            if self.current().kind in stop_kinds:
                return expression
            op = comparison_op_from_token(self.current().kind)
            if op is None:
                return expression
            self.advance()
            right = self.parse_match_expression()
            expression = BinaryExpr(
                left=expression,
                op=op,
                right=right,
                span=combine_spans(expression.span, right.span),
            )

    def parse_match_expression(self) -> Expr:
        """Parse `~` and `!~` expressions."""
        expression = self.parse_in_expression()
        while True:
            op = match_op_from_token(self.current().kind)
            if op is None:
                return expression
            self.advance()
            right = self.parse_in_expression()
            expression = BinaryExpr(
                left=expression,
                op=op,
                right=right,
                span=combine_spans(expression.span, right.span),
            )

    def parse_in_expression(self) -> Expr:
        """Parse `in` expressions."""
        expression = self.parse_concat_expression()
        if not self.check(TokenKind.IN):
            return expression
        self.advance()
        right = self.parse_concat_expression()
        return BinaryExpr(left=expression, op=BinaryOp.IN, right=right, span=combine_spans(expression.span, right.span))

    def parse_concat_expression(self) -> Expr:
        """Parse implicit concatenation expressions."""
        expression = self.parse_additive_expression()
        while is_expression_start(self.current().kind):
            right = self.parse_additive_expression()
            expression = BinaryExpr(
                left=expression,
                op=BinaryOp.CONCAT,
                right=right,
                span=combine_spans(expression.span, right.span),
            )
        return expression

    def parse_additive_expression(self) -> Expr:
        """Parse additive expressions."""
        expression = self.parse_multiplicative_expression()
        while True:
            op = additive_op_from_token(self.current().kind)
            if op is None:
                return expression
            self.advance()
            right = self.parse_multiplicative_expression()
            expression = BinaryExpr(
                left=expression,
                op=op,
                right=right,
                span=combine_spans(expression.span, right.span),
            )

    def parse_multiplicative_expression(self) -> Expr:
        """Parse multiplicative expressions."""
        expression = self.parse_power_expression()
        while True:
            op = multiplicative_op_from_token(self.current().kind)
            if op is None:
                return expression
            self.advance()
            right = self.parse_power_expression()
            expression = BinaryExpr(
                left=expression,
                op=op,
                right=right,
                span=combine_spans(expression.span, right.span),
            )

    def parse_power_expression(self) -> Expr:
        """Parse right-associative power expressions."""
        expression = self.parse_unary_expression()
        if not self.check(TokenKind.CARET):
            return expression
        self.advance()
        right = self.parse_power_expression()
        return BinaryExpr(
            left=expression,
            op=BinaryOp.POW,
            right=right,
            span=combine_spans(expression.span, right.span),
        )

    def parse_unary_expression(self) -> Expr:
        """Parse unary prefix expressions."""
        op = unary_op_from_token(self.current().kind)
        if op is not None:
            token = self.advance()
            operand = self.parse_unary_expression()
            return UnaryExpr(op=op, operand=operand, span=combine_spans(token.span, operand.span))
        return self.parse_postfix_expression()

    def parse_postfix_expression(self) -> Expr:
        """Parse postfix increment and decrement expressions."""
        expression = self.parse_primary_expression()
        op = postfix_op_from_token(self.current().kind)
        if op is None:
            return expression
        token = self.advance()
        return PostfixExpr(op=op, operand=expression, span=combine_spans(expression.span, token.span))

    def parse_primary_expression(self) -> Expr:
        """Parse a primary expression."""
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
            case TokenKind.REGEX:
                regex_token = self.advance()
                return RegexLiteralExpr(raw_text=regex_token.text or "", span=regex_token.span)
            case TokenKind.IDENT:
                if token.text == "getline":
                    return self.parse_getline_expression()
                if self.peek_kind() is TokenKind.LPAREN:
                    return self.parse_call_expression()
                if self.peek_kind() is TokenKind.LBRACKET:
                    return self.parse_array_index_expression()
                name_token = self.advance()
                return NameExpr(name=name_token.text or "", span=name_token.span)
            case TokenKind.DOLLAR:
                dollar_token = self.advance()
                index_expression = self.parse_unary_expression()
                if isinstance(index_expression, NumericLiteralExpr) and "." not in index_expression.raw_text:
                    return FieldExpr(
                        index=int(index_expression.raw_text),
                        span=combine_spans(dollar_token.span, index_expression.span),
                    )
                return FieldExpr(index=index_expression, span=combine_spans(dollar_token.span, index_expression.span))
            case TokenKind.LPAREN:
                return self.parse_parenthesized_expression()
            case _:
                raise ParseError(f"expected expression, got {token.kind.name}", token.span)

    def parse_getline_expression(self) -> GetlineExpr:
        """Parse one POSIX `getline` expression in the currently claimed forms."""
        getline_token = self.expect(TokenKind.IDENT)
        assert getline_token.text == "getline"

        target: LValue | None = None
        source: Expr | None = None
        if self.check(TokenKind.LESS):
            self.advance()
            source = self.parse_expression()
            span_end = source.span
            return GetlineExpr(target=target, source=source, span=combine_spans(getline_token.span, span_end))

        if self.current().kind in {TokenKind.IDENT, TokenKind.DOLLAR}:
            target = self.parse_lvalue()
        if self.check(TokenKind.LESS):
            self.advance()
            source = self.parse_expression()

        span_end = getline_token.span
        if source is not None:
            span_end = source.span
        elif target is not None:
            span_end = target.span
        return GetlineExpr(target=target, source=source, span=combine_spans(getline_token.span, span_end))

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

    def parse_array_index_expression(self) -> ArrayIndexExpr:
        """Parse one associative-array indexed-read expression."""
        name_token = self.expect(TokenKind.IDENT)
        _, subscripts, rbracket_token = self.parse_array_subscripts()
        index = subscripts[0]
        return ArrayIndexExpr(
            array_name=name_token.text or "",
            index=index,
            extra_indexes=tuple(subscripts[1:]),
            span=combine_spans(name_token.span, rbracket_token.span),
        )

    def parse_expression_list(self, stop_kinds: frozenset[TokenKind] = frozenset()) -> list[Expr]:
        """Parse a comma-separated expression list."""
        expressions = [self.parse_expression(stop_kinds)]
        while self.check(TokenKind.COMMA):
            self.advance()
            expressions.append(self.parse_expression(stop_kinds))
        return expressions

    def parse_output_redirect(self) -> OutputRedirect:
        """Parse one `print`/`printf` redirect tail."""
        token = self.advance()
        match token.kind:
            case TokenKind.GREATER:
                kind = OutputRedirectKind.WRITE
            case TokenKind.GREATER_GREATER:
                kind = OutputRedirectKind.APPEND
            case TokenKind.PIPE:
                kind = OutputRedirectKind.PIPE
            case _:
                raise ParseError(f"expected output redirect, got {token.kind.name}", token.span)
        target = self.parse_expression()
        return OutputRedirect(kind=kind, target=target, span=combine_spans(token.span, target.span))

    def parse_lvalue(self) -> LValue:
        """Parse one lvalue in expression or statement position."""
        token = self.current()
        match token.kind:
            case TokenKind.IDENT:
                name_token = self.advance()
                if not self.check(TokenKind.LBRACKET):
                    return NameLValue(name=name_token.text or "", span=name_token.span)
                _, subscripts, rbracket_token = self.parse_array_subscripts()
                return ArrayLValue(
                    name=name_token.text or "",
                    subscripts=tuple(subscripts),
                    span=combine_spans(name_token.span, rbracket_token.span),
                )
            case TokenKind.DOLLAR:
                dollar_token = self.advance()
                index = self.parse_expression()
                return FieldLValue(index=index, span=combine_spans(dollar_token.span, index.span))
            case _:
                raise ParseError(f"expected lvalue, got {token.kind.name}", token.span)

    def parse_array_subscripts(self) -> tuple[Token, list[Expr], Token]:
        """Parse one bracketed array subscript list."""
        lbracket_token = self.expect(TokenKind.LBRACKET)
        subscripts = [self.parse_expression()]
        while self.check(TokenKind.COMMA):
            self.advance()
            subscripts.append(self.parse_expression())
        rbracket_token = self.expect(TokenKind.RBRACKET)
        return lbracket_token, subscripts, rbracket_token

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

    def is_statement_terminator(self) -> bool:
        """Report whether the current token ends the active simple statement."""
        return self.check(TokenKind.RBRACE) or self.check(TokenKind.NEWLINE) or self.check(TokenKind.SEMICOLON)

    def is_output_redirect_start(self) -> bool:
        """Report whether the current token starts a print/printf redirect tail."""
        return self.current().kind in PRINT_REDIRECT_START_KINDS


ASSIGNMENT_TOKEN_KINDS = {
    TokenKind.EQUAL,
    TokenKind.PLUS_EQUAL,
    TokenKind.MINUS_EQUAL,
    TokenKind.STAR_EQUAL,
    TokenKind.SLASH_EQUAL,
    TokenKind.PERCENT_EQUAL,
    TokenKind.CARET_EQUAL,
}

PRINT_REDIRECT_START_KINDS = frozenset({TokenKind.GREATER, TokenKind.GREATER_GREATER, TokenKind.PIPE})


def assignment_op_from_token(kind: TokenKind) -> AssignOp:
    """Return the assignment-op enum for one token kind."""
    match kind:
        case TokenKind.EQUAL:
            return AssignOp.PLAIN
        case TokenKind.PLUS_EQUAL:
            return AssignOp.ADD
        case TokenKind.MINUS_EQUAL:
            return AssignOp.SUB
        case TokenKind.STAR_EQUAL:
            return AssignOp.MUL
        case TokenKind.SLASH_EQUAL:
            return AssignOp.DIV
        case TokenKind.PERCENT_EQUAL:
            return AssignOp.MOD
        case TokenKind.CARET_EQUAL:
            return AssignOp.POW
        case _:
            raise AssertionError(f"unhandled assignment token: {kind!r}")


def comparison_op_from_token(kind: TokenKind) -> BinaryOp | None:
    """Return the comparison operator for `kind`, if any."""
    match kind:
        case TokenKind.LESS:
            return BinaryOp.LESS
        case TokenKind.LESS_EQUAL:
            return BinaryOp.LESS_EQUAL
        case TokenKind.GREATER:
            return BinaryOp.GREATER
        case TokenKind.GREATER_EQUAL:
            return BinaryOp.GREATER_EQUAL
        case TokenKind.EQUAL_EQUAL:
            return BinaryOp.EQUAL
        case TokenKind.NOT_EQUAL:
            return BinaryOp.NOT_EQUAL
        case _:
            return None


def match_op_from_token(kind: TokenKind) -> BinaryOp | None:
    """Return the match operator for `kind`, if any."""
    match kind:
        case TokenKind.MATCH:
            return BinaryOp.MATCH
        case TokenKind.NOT_MATCH:
            return BinaryOp.NOT_MATCH
        case _:
            return None


def additive_op_from_token(kind: TokenKind) -> BinaryOp | None:
    """Return the additive operator for `kind`, if any."""
    match kind:
        case TokenKind.PLUS:
            return BinaryOp.ADD
        case TokenKind.MINUS:
            return BinaryOp.SUB
        case _:
            return None


def multiplicative_op_from_token(kind: TokenKind) -> BinaryOp | None:
    """Return the multiplicative operator for `kind`, if any."""
    match kind:
        case TokenKind.STAR:
            return BinaryOp.MUL
        case TokenKind.SLASH:
            return BinaryOp.DIV
        case TokenKind.PERCENT:
            return BinaryOp.MOD
        case _:
            return None


def unary_op_from_token(kind: TokenKind) -> UnaryOp | None:
    """Return the unary operator for `kind`, if any."""
    match kind:
        case TokenKind.PLUS:
            return UnaryOp.UPLUS
        case TokenKind.MINUS:
            return UnaryOp.UMINUS
        case TokenKind.BANG:
            return UnaryOp.NOT
        case TokenKind.PLUS_PLUS:
            return UnaryOp.PRE_INC
        case TokenKind.MINUS_MINUS:
            return UnaryOp.PRE_DEC
        case _:
            return None


def postfix_op_from_token(kind: TokenKind) -> PostfixOp | None:
    """Return the postfix operator for `kind`, if any."""
    match kind:
        case TokenKind.PLUS_PLUS:
            return PostfixOp.POST_INC
        case TokenKind.MINUS_MINUS:
            return PostfixOp.POST_DEC
        case _:
            return None


def is_expression_start(kind: TokenKind) -> bool:
    """Report whether `kind` can begin an expression for concatenation parsing."""
    return kind in {
        TokenKind.STRING,
        TokenKind.NUMBER,
        TokenKind.REGEX,
        TokenKind.IDENT,
        TokenKind.DOLLAR,
        TokenKind.LPAREN,
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.BANG,
        TokenKind.PLUS_PLUS,
        TokenKind.MINUS_MINUS,
    }


def expression_to_lvalue(expression: Expr) -> LValue | None:
    """Convert an expression node into its lvalue form when possible."""
    match expression:
        case NameExpr(name=name, span=span):
            return NameLValue(name=name, span=span)
        case ArrayIndexExpr(array_name=array_name, span=span):
            return ArrayLValue(name=array_name, subscripts=expression.subscripts, span=span)
        case FieldExpr(index=index, span=span):
            if isinstance(index, int):
                return FieldLValue(
                    index=NumericLiteralExpr(value=float(index), raw_text=str(index), span=span),
                    span=span,
                )
            return FieldLValue(index=index, span=span)
        case _:
            return None


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
