"""AST node definitions for the supported AWK language subset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias

from .source import SourceSpan


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
