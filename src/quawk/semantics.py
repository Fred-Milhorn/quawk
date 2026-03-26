"""Semantic analysis and scope modeling for the current frontend subset."""

from __future__ import annotations

from dataclasses import dataclass

from .builtins import is_builtin_function_name
from .diagnostics import SemanticError
from .parser import (
    Action,
    ArrayIndexExpr,
    AssignStmt,
    BinaryExpr,
    BlockStmt,
    BreakStmt,
    CallExpr,
    ContinueStmt,
    DeleteStmt,
    Expr,
    ExprPattern,
    ForInStmt,
    ForStmt,
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
        validate_function_definition(item)
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
    loop_depth: int = 0,
) -> None:
    """Validate every statement in one action block."""
    for statement in action.statements:
        validate_statement(statement, functions, scope=scope, inside_function=inside_function, loop_depth=loop_depth)


def validate_function_definition(function: FunctionDef) -> None:
    """Validate one function signature for duplicate or conflicting names."""
    seen_params: set[str] = set()
    for param_name, param_span in zip(function.params, function.param_spans, strict=True):
        if param_name == function.name:
            raise SemanticError(f"function parameter conflicts with function name: {param_name}", param_span)
        if param_name in seen_params:
            raise SemanticError(f"duplicate parameter name in function {function.name}: {param_name}", param_span)
        seen_params.add(param_name)


def validate_statement(
    statement: Stmt,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
    inside_function: bool,
    loop_depth: int,
) -> None:
    """Validate one statement in the current semantic context."""
    match statement:
        case AssignStmt():
            validate_assignment_statement(statement, functions, scope=scope)
        case BlockStmt(statements=statements):
            for nested in statements:
                validate_statement(
                    nested,
                    functions,
                    scope=scope,
                    inside_function=inside_function,
                    loop_depth=loop_depth,
                )
        case BreakStmt(span=span):
            if loop_depth == 0:
                raise SemanticError("break is only valid inside a loop", span)
        case ContinueStmt(span=span):
            if loop_depth == 0:
                raise SemanticError("continue is only valid inside a loop", span)
        case DeleteStmt(index=index):
            validate_expression(index, functions)
        case IfStmt(condition=condition, then_branch=then_branch):
            validate_expression(condition, functions)
            validate_statement(
                then_branch,
                functions,
                scope=scope,
                inside_function=inside_function,
                loop_depth=loop_depth,
            )
        case WhileStmt(condition=condition, body=body):
            validate_expression(condition, functions)
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                loop_depth=loop_depth + 1,
            )
        case ForStmt(init=init, condition=condition, update=update, body=body):
            if init is not None:
                validate_assignment_statement(init, functions, scope=scope)
            if condition is not None:
                validate_expression(condition, functions)
            if update is not None:
                validate_assignment_statement(update, functions, scope=scope)
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                loop_depth=loop_depth + 1,
            )
        case ForInStmt(name=name, body=body, span=span):
            if name in functions and not (scope is not None and scope.is_local_name(name)):
                raise SemanticError(f"cannot assign to function name: {name}", span)
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                loop_depth=loop_depth + 1,
            )
        case PrintStmt(arguments=arguments):
            for argument in arguments:
                validate_expression(argument, functions)
        case ReturnStmt(value=value, span=span):
            if not inside_function:
                raise SemanticError("return is only valid inside a function", span)
            if value is not None:
                validate_expression(value, functions)
        case _:
            raise AssertionError(f"unhandled statement type: {type(statement)!r}")


def validate_expression(expression: Expr, functions: dict[str, FunctionDef]) -> None:
    """Validate one expression tree in the current subset."""
    match expression:
        case BinaryExpr(left=left, right=right):
            validate_expression(left, functions)
            validate_expression(right, functions)
        case ArrayIndexExpr(index=index):
            validate_expression(index, functions)
        case CallExpr(function=function_name, args=args, span=span):
            function_def = functions.get(function_name)
            if function_def is None and not is_builtin_function_name(function_name):
                raise SemanticError(f"call to undefined function: {function_name}", span)
            if function_def is None and function_name == "length" and len(args) > 1:
                raise SemanticError("builtin length expects zero or one argument", span)
            for argument in args:
                validate_expression(argument, functions)
        case NameExpr():
            return
        case _:
            return


def validate_assignment_statement(
    statement: AssignStmt,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
) -> None:
    """Validate one assignment target and its expressions."""
    if statement.name in functions and not (scope is not None and scope.is_local_name(statement.name)):
        raise SemanticError(f"cannot assign to function name: {statement.name}", statement.span)
    if statement.index is not None:
        validate_expression(statement.index, functions)
    validate_expression(statement.value, functions)
