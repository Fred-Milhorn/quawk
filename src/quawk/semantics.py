"""Semantic analysis and scope modeling for the current frontend subset."""

from __future__ import annotations

from dataclasses import dataclass

from .ast import (
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
    GetlineExpr,
    IfStmt,
    NameExpr,
    NameLValue,
    NextFileStmt,
    NextStmt,
    PatternAction,
    PostfixExpr,
    PostfixOp,
    PrintfStmt,
    PrintStmt,
    Program,
    RangePattern,
    ReturnStmt,
    Stmt,
    UnaryExpr,
    UnaryOp,
    WhileStmt,
    expression_to_lvalue,
)
from .ast_walk import expression_children, lvalue_expressions
from .builtins import builtin_accepts_arity, is_builtin_function_name
from .diagnostics import SemanticError, SemanticErrorCode


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
            raise SemanticError(
                f"duplicate function definition: {item.name}",
                item.span,
                SemanticErrorCode.DUPLICATE_FUNCTION_DEFINITION,
            )
        validate_function_definition(item)
        functions[item.name] = item
        function_scopes[item.name] = FunctionScope(params=item.params)

    for item in program.items:
        if isinstance(item, FunctionDef):
            scope = function_scopes[item.name]
            validate_action(item.body, functions, scope=scope, inside_function=True, in_record_action=False)
            continue
        if isinstance(item, PatternAction) and item.action is not None:
            if item.pattern is not None:
                validate_pattern(item.pattern, functions, scope=None)
            validate_action(
                item.action,
                functions,
                scope=None,
                inside_function=False,
                in_record_action=is_record_action(item),
            )

    return ProgramAnalysis(functions=functions, function_scopes=function_scopes)


def validate_action(
    action: Action,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
    inside_function: bool,
    in_record_action: bool,
    loop_depth: int = 0,
) -> None:
    """Validate every statement in one action block."""
    for statement in action.statements:
        validate_statement(
            statement,
            functions,
            scope=scope,
            inside_function=inside_function,
            in_record_action=in_record_action,
            loop_depth=loop_depth,
        )


def validate_function_definition(function: FunctionDef) -> None:
    """Validate one function signature for duplicate or conflicting names."""
    seen_params: set[str] = set()
    for param_name, param_span in zip(function.params, function.param_spans, strict=True):
        if param_name == function.name:
            raise SemanticError(
                f"function parameter conflicts with function name: {param_name}",
                param_span,
                SemanticErrorCode.FUNCTION_PARAMETER_CONFLICT,
            )
        if param_name in seen_params:
            raise SemanticError(
                f"duplicate parameter name in function {function.name}: {param_name}",
                param_span,
                SemanticErrorCode.DUPLICATE_PARAMETER_NAME,
            )
        seen_params.add(param_name)


def validate_statement(
    statement: Stmt,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
    inside_function: bool,
    in_record_action: bool,
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
                    in_record_action=in_record_action,
                    loop_depth=loop_depth,
                )
        case BreakStmt(span=span):
            if loop_depth == 0:
                raise SemanticError("break is only valid inside a loop", span, SemanticErrorCode.BREAK_OUTSIDE_LOOP)
        case ContinueStmt(span=span):
            if loop_depth == 0:
                raise SemanticError(
                    "continue is only valid inside a loop",
                    span,
                    SemanticErrorCode.CONTINUE_OUTSIDE_LOOP,
                )
        case NextStmt(span=span):
            if not in_record_action:
                raise SemanticError(
                    "next is only valid in record actions",
                    span,
                    SemanticErrorCode.NEXT_OUTSIDE_RECORD_ACTION,
                )
        case NextFileStmt(span=span):
            if not in_record_action:
                raise SemanticError(
                    "nextfile is only valid in record actions",
                    span,
                    SemanticErrorCode.NEXTFILE_OUTSIDE_RECORD_ACTION,
                )
        case DeleteStmt(target=target):
            validate_lvalue(target, functions, scope=scope)
        case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
            validate_expression(condition, functions, scope=scope)
            validate_statement(
                then_branch,
                functions,
                scope=scope,
                inside_function=inside_function,
                in_record_action=in_record_action,
                loop_depth=loop_depth,
            )
            if else_branch is not None:
                validate_statement(
                    else_branch,
                    functions,
                    scope=scope,
                    inside_function=inside_function,
                    in_record_action=in_record_action,
                    loop_depth=loop_depth,
                )
        case WhileStmt(condition=condition, body=body):
            validate_expression(condition, functions, scope=scope)
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                in_record_action=in_record_action,
                loop_depth=loop_depth + 1,
            )
        case DoWhileStmt(body=body, condition=condition):
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                in_record_action=in_record_action,
                loop_depth=loop_depth + 1,
            )
            validate_expression(condition, functions, scope=scope)
        case ForStmt(init=init, condition=condition, update=update, body=body):
            for expression in init:
                validate_expression(expression, functions, scope=scope)
            if condition is not None:
                validate_expression(condition, functions, scope=scope)
            for expression in update:
                validate_expression(expression, functions, scope=scope)
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                in_record_action=in_record_action,
                loop_depth=loop_depth + 1,
            )
        case ForInStmt(name=name, iterable=iterable, body=body, span=span):
            if name in functions and not (scope is not None and scope.is_local_name(name)):
                raise SemanticError(
                    f"cannot assign to function name: {name}",
                    span,
                    SemanticErrorCode.ASSIGN_TO_FUNCTION_NAME,
                )
            validate_expression(iterable, functions, scope=scope)
            if not isinstance(iterable, NameExpr):
                raise SemanticError(
                    "for-in iteration requires an array name",
                    iterable.span,
                    SemanticErrorCode.INVALID_FOR_IN_ITERABLE,
                )
            validate_statement(
                body,
                functions,
                scope=scope,
                inside_function=inside_function,
                in_record_action=in_record_action,
                loop_depth=loop_depth + 1,
            )
        case PrintStmt(arguments=arguments, redirect=redirect):
            for argument in arguments:
                validate_expression(argument, functions, scope=scope)
            if redirect is not None:
                validate_expression(redirect.target, functions, scope=scope)
        case PrintfStmt(arguments=arguments, redirect=redirect):
            for argument in arguments:
                validate_expression(argument, functions, scope=scope)
            if redirect is not None:
                validate_expression(redirect.target, functions, scope=scope)
        case ExprStmt(value=value):
            validate_expression(value, functions, scope=scope)
        case ExitStmt(value=value):
            if value is not None:
                validate_expression(value, functions, scope=scope)
        case ReturnStmt(value=value, span=span):
            if not inside_function:
                raise SemanticError(
                    "return is only valid inside a function",
                    span,
                    SemanticErrorCode.RETURN_OUTSIDE_FUNCTION,
                )
            if value is not None:
                validate_expression(value, functions, scope=scope)
        case _:
            raise AssertionError(f"unhandled statement type: {type(statement)!r}")


def validate_expression(
    expression: Expr,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
) -> None:
    """Validate one expression tree in the current subset."""
    match expression:
        case BinaryExpr() | ArrayIndexExpr() | ConditionalExpr() | FieldExpr():
            for child in expression_children(expression):
                validate_expression(child, functions, scope=scope)
        case CallExpr(function=function_name, args=args, span=span):
            function_def = functions.get(function_name)
            if function_def is None and not is_builtin_function_name(function_name):
                raise SemanticError(
                    f"call to undefined function: {function_name}",
                    span,
                    SemanticErrorCode.UNDEFINED_FUNCTION_CALL,
                )
            if function_def is None and not builtin_accepts_arity(function_name, len(args)):
                match function_name:
                    case "atan2":
                        raise SemanticError(
                            "builtin atan2 expects two arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "close":
                        raise SemanticError(
                            "builtin close expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "cos":
                        raise SemanticError(
                            "builtin cos expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "exp":
                        raise SemanticError(
                            "builtin exp expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "gsub":
                        raise SemanticError(
                            "builtin gsub expects two or three arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "index":
                        raise SemanticError(
                            "builtin index expects two arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "int":
                        raise SemanticError(
                            "builtin int expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "length":
                        raise SemanticError(
                            "builtin length expects zero or one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "log":
                        raise SemanticError(
                            "builtin log expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "match":
                        raise SemanticError(
                            "builtin match expects two arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "rand":
                        raise SemanticError(
                            "builtin rand expects zero arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "sin":
                        raise SemanticError(
                            "builtin sin expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "sprintf":
                        raise SemanticError(
                            "builtin sprintf expects at least a format argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "split":
                        raise SemanticError(
                            "builtin split expects two or three arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "sqrt":
                        raise SemanticError(
                            "builtin sqrt expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "srand":
                        raise SemanticError(
                            "builtin srand expects zero or one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "sub":
                        raise SemanticError(
                            "builtin sub expects two or three arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "substr":
                        raise SemanticError(
                            "builtin substr expects two or three arguments",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "system":
                        raise SemanticError(
                            "builtin system expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "tolower":
                        raise SemanticError(
                            "builtin tolower expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case "toupper":
                        raise SemanticError(
                            "builtin toupper expects one argument",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
                    case _:
                        raise SemanticError(
                            f"unsupported builtin call: {function_name}",
                            span,
                            SemanticErrorCode.INVALID_BUILTIN_CALL,
                        )
            for argument in expression_children(expression):
                validate_expression(argument, functions, scope=scope)
            if function_def is None and function_name in {"sub", "gsub"} and len(args) == 3 and expression_to_lvalue(args[2]) is None:
                raise SemanticError(
                    f"builtin {function_name} requires an assignable third argument",
                    args[2].span,
                    SemanticErrorCode.INVALID_BUILTIN_CALL,
                )
        case GetlineExpr(target=target, source=source):
            if target is not None:
                validate_lvalue(target, functions, scope=scope)
            if source is not None:
                validate_expression(source, functions, scope=scope)
        case AssignExpr(target=target, value=value):
            validate_lvalue(target, functions, scope=scope)
            validate_expression(value, functions, scope=scope)
        case UnaryExpr(op=op, operand=operand, span=span):
            validate_expression(operand, functions, scope=scope)
            if op in {UnaryOp.PRE_INC, UnaryOp.PRE_DEC} and not is_assignable_expression(operand):
                raise SemanticError(
                    "increment and decrement require an assignable expression",
                    span,
                    SemanticErrorCode.INVALID_INCREMENT_TARGET,
                )
        case PostfixExpr(op=op, operand=operand, span=span):
            validate_expression(operand, functions, scope=scope)
            if op in {PostfixOp.POST_INC, PostfixOp.POST_DEC} and not is_assignable_expression(operand):
                raise SemanticError(
                    "increment and decrement require an assignable expression",
                    span,
                    SemanticErrorCode.INVALID_INCREMENT_TARGET,
                )
        case NameExpr():
            return
        case _:
            return


def validate_lvalue(
    target: NameLValue | ArrayLValue | FieldLValue,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
) -> None:
    """Validate an lvalue tree in the current frontend."""
    match target:
        case NameLValue(name=name, span=span):
            if name in functions and not (scope is not None and scope.is_local_name(name)):
                raise SemanticError(
                    f"cannot assign to function name: {name}",
                    span,
                    SemanticErrorCode.ASSIGN_TO_FUNCTION_NAME,
                )
        case ArrayLValue(name=name, subscripts=subscripts, span=span):
            if name in functions and not (scope is not None and scope.is_local_name(name)):
                raise SemanticError(
                    f"cannot assign to function name: {name}",
                    span,
                    SemanticErrorCode.ASSIGN_TO_FUNCTION_NAME,
                )
            for expression in lvalue_expressions(target):
                validate_expression(expression, functions, scope=scope)
        case FieldLValue():
            for expression in lvalue_expressions(target):
                validate_expression(expression, functions, scope=scope)


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
        raise SemanticError(
            f"cannot assign to function name: {statement.name}",
            statement.span,
            SemanticErrorCode.ASSIGN_TO_FUNCTION_NAME,
        )
    validate_lvalue(statement.target, functions, scope=scope)
    validate_expression(statement.value, functions, scope=scope)


def validate_pattern(
    pattern: ExprPattern | RangePattern | object,
    functions: dict[str, FunctionDef],
    scope: FunctionScope | None,
) -> None:
    """Validate one top-level pattern tree."""
    match pattern:
        case ExprPattern(test=test):
            validate_expression(test, functions, scope=scope)
        case RangePattern(left=left, right=right):
            validate_pattern(left, functions, scope=scope)
            validate_pattern(right, functions, scope=scope)
        case _:
            return


def is_record_action(item: PatternAction) -> bool:
    """Report whether one top-level action executes in record-processing context."""
    if item.pattern is None:
        return True
    if isinstance(item.pattern, ExprPattern | RangePattern):
        return True
    return False


def is_assignable_expression(expression: Expr) -> bool:
    """Report whether an expression can appear on the left-hand side of assignment-like operators."""
    return isinstance(expression, NameExpr | ArrayIndexExpr | FieldExpr)
