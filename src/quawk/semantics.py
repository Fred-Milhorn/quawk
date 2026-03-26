"""Semantic analysis and scope modeling for the current frontend subset."""

from __future__ import annotations

from dataclasses import dataclass

from .builtins import is_builtin_function_name
from .diagnostics import SemanticError
from .parser import (
    Action,
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignStmt,
    BinaryExpr,
    BlockStmt,
    BreakStmt,
    CallExpr,
    ConditionalExpr,
    ContinueStmt,
    DeleteStmt,
    DoWhileStmt,
    ExitStmt,
    Expr,
    ExprPattern,
    ExprStmt,
    FieldExpr,
    FieldLValue,
    ForInStmt,
    ForStmt,
    FunctionDef,
    IfStmt,
    NameExpr,
    NameLValue,
    NextFileStmt,
    NextStmt,
    PatternAction,
    PostfixExpr,
    PrintfStmt,
    PrintStmt,
    Program,
    ReturnStmt,
    Stmt,
    UnaryExpr,
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
        case NextStmt():
            return
        case NextFileStmt():
            return
        case DeleteStmt(target=target):
            validate_lvalue(target, functions)
        case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
            validate_expression(condition, functions)
            validate_statement(
                then_branch,
                functions,
                scope=scope,
                inside_function=inside_function,
                loop_depth=loop_depth,
            )
            if else_branch is not None:
                validate_statement(
                    else_branch,
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
        case DoWhileStmt(body=body, condition=condition):
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                loop_depth=loop_depth + 1,
            )
            validate_expression(condition, functions)
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
        case PrintfStmt(arguments=arguments):
            for argument in arguments:
                validate_expression(argument, functions)
        case ExprStmt(value=value):
            validate_expression(value, functions)
        case ExitStmt(value=value):
            if value is not None:
                validate_expression(value, functions)
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
        case ArrayIndexExpr(index=index, extra_indexes=extra_indexes):
            validate_expression(index, functions)
            for extra_index in extra_indexes:
                validate_expression(extra_index, functions)
        case CallExpr(function=function_name, args=args, span=span):
            function_def = functions.get(function_name)
            if function_def is None and not is_builtin_function_name(function_name):
                raise SemanticError(f"call to undefined function: {function_name}", span)
            if function_def is None and function_name == "length" and len(args) > 1:
                raise SemanticError("builtin length expects zero or one argument", span)
            for argument in args:
                validate_expression(argument, functions)
        case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
            validate_expression(test, functions)
            validate_expression(if_true, functions)
            validate_expression(if_false, functions)
        case AssignExpr(target=target, value=value):
            validate_lvalue(target, functions)
            validate_expression(value, functions)
        case UnaryExpr(operand=operand):
            validate_expression(operand, functions)
        case PostfixExpr(operand=operand):
            validate_expression(operand, functions)
        case FieldExpr(index=index):
            if not isinstance(index, int):
                validate_expression(index, functions)
        case NameExpr():
            return
        case _:
            return


def validate_lvalue(target: NameLValue | ArrayLValue | FieldLValue, functions: dict[str, FunctionDef]) -> None:
    """Validate an lvalue tree in the current frontend."""
    match target:
        case NameLValue():
            return
        case ArrayLValue(subscripts=subscripts):
            for subscript in subscripts:
                validate_expression(subscript, functions)
        case FieldLValue(index=index):
            validate_expression(index, functions)


def validate_assignment_statement(
    statement: AssignStmt,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
) -> None:
    """Validate one assignment target and its expressions."""
    if (
        statement.name is not None
        and statement.name in functions
        and not (scope is not None and scope.is_local_name(statement.name))
    ):
        raise SemanticError(f"cannot assign to function name: {statement.name}", statement.span)
    validate_lvalue(statement.target, functions)
    validate_expression(statement.value, functions)
