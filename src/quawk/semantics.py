"""Semantic analysis and scope modeling for the current frontend subset."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import SemanticError
from .parser import (
    Action,
    AssignStmt,
    BinaryExpr,
    BlockStmt,
    CallExpr,
    Expr,
    ExprPattern,
    FunctionDef,
    IfStmt,
    NameExpr,
    PatternAction,
    PrintStmt,
    Program,
    ReturnStmt,
    Stmt,
    WhileStmt,
)


@dataclass(frozen=True)
class FunctionScope:
    """Resolved local-scope information for one user-defined function."""

    params: tuple[str, ...]

    def is_local_name(self, name: str) -> bool:
        """Report whether `name` resolves to the function-local scope."""
        return name in self.params


@dataclass(frozen=True)
class ProgramAnalysis:
    """Semantic-analysis result used by later execution stages."""

    functions: dict[str, FunctionDef]
    function_scopes: dict[str, FunctionScope]


def analyze(program: Program) -> ProgramAnalysis:
    """Build function symbols and validate scope-sensitive constructs."""
    functions: dict[str, FunctionDef] = {}
    function_scopes: dict[str, FunctionScope] = {}

    for item in program.items:
        if not isinstance(item, FunctionDef):
            continue
        existing = functions.get(item.name)
        if existing is not None:
            raise SemanticError(f"duplicate function definition: {item.name}", item.span)
        functions[item.name] = item
        function_scopes[item.name] = FunctionScope(params=item.params)

    for item in program.items:
        if isinstance(item, FunctionDef):
            scope = function_scopes[item.name]
            validate_action(item.body, functions, scope=scope, inside_function=True)
            continue
        if isinstance(item, PatternAction) and item.pattern is not None and isinstance(item.pattern, ExprPattern):
            validate_expression(item.pattern.test, functions)
        if isinstance(item, PatternAction) and item.action is not None:
            validate_action(item.action, functions, scope=None, inside_function=False)

    return ProgramAnalysis(functions=functions, function_scopes=function_scopes)


def validate_action(
    action: Action,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
    inside_function: bool,
) -> None:
    """Validate every statement in one action block."""
    for statement in action.statements:
        validate_statement(statement, functions, scope=scope, inside_function=inside_function)


def validate_statement(
    statement: Stmt,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
    inside_function: bool,
) -> None:
    """Validate one statement in the current semantic context."""
    if isinstance(statement, AssignStmt):
        if statement.name in functions and not (scope is not None and scope.is_local_name(statement.name)):
            raise SemanticError(f"cannot assign to function name: {statement.name}", statement.span)
        validate_expression(statement.value, functions)
        return
    if isinstance(statement, BlockStmt):
        for nested in statement.statements:
            validate_statement(nested, functions, scope=scope, inside_function=inside_function)
        return
    if isinstance(statement, IfStmt):
        validate_expression(statement.condition, functions)
        validate_statement(statement.then_branch, functions, scope=scope, inside_function=inside_function)
        return
    if isinstance(statement, WhileStmt):
        validate_expression(statement.condition, functions)
        validate_statement(statement.body, functions, scope=scope, inside_function=inside_function)
        return
    if isinstance(statement, PrintStmt):
        for argument in statement.arguments:
            validate_expression(argument, functions)
        return
    if isinstance(statement, ReturnStmt):
        if not inside_function:
            raise SemanticError("return is only valid inside a function", statement.span)
        if statement.value is not None:
            validate_expression(statement.value, functions)
        return
    raise AssertionError(f"unhandled statement type: {type(statement)!r}")


def validate_expression(expression: Expr, functions: dict[str, FunctionDef]) -> None:
    """Validate one expression tree in the current subset."""
    if isinstance(expression, BinaryExpr):
        validate_expression(expression.left, functions)
        validate_expression(expression.right, functions)
        return
    if isinstance(expression, CallExpr):
        for argument in expression.args:
            validate_expression(argument, functions)
        return
    if isinstance(expression, NameExpr):
        return
    return
