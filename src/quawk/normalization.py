"""Backend-oriented normalization for the currently supported lowering subset."""

from __future__ import annotations

from dataclasses import dataclass

from .parser import (
    Action,
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BlockStmt,
    CallExpr,
    ConditionalExpr,
    DeleteStmt,
    DoWhileStmt,
    EndPattern,
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
    PatternAction,
    PostfixExpr,
    PrintfStmt,
    PrintStmt,
    Program,
    RangePattern,
    ReturnStmt,
    Stmt,
    UnaryExpr,
    WhileStmt,
)


@dataclass(frozen=True)
class NormalizedRecordItem:
    """One normalized record-phase item used by reusable lowering."""

    pattern: ExprPattern | RangePattern | None
    action: Action | None
    range_state_name: str | None = None


@dataclass(frozen=True)
class NormalizedLoweringProgram:
    """Stable lowering-ready shape for the current backend subset."""

    direct_begin_statements: tuple[Stmt, ...] | None
    begin_actions: tuple[Action, ...]
    record_items: tuple[NormalizedRecordItem, ...]
    end_actions: tuple[Action, ...]
    variable_indexes: dict[str, int]
    array_names: frozenset[str]


def normalize_program_for_lowering(program: Program) -> NormalizedLoweringProgram:
    """Normalize `program` into the stable shape consumed by lowering."""
    begin_actions: list[Action] = []
    record_items: list[NormalizedRecordItem] = []
    end_actions: list[Action] = []
    range_state_names: list[str] = []

    for item in program.items:
        if isinstance(item, FunctionDef):
            continue
        if not isinstance(item, PatternAction):
            raise RuntimeError("the current lowering path only supports pattern-action items")

        if item.pattern is None:
            if not isinstance(item.action, Action):
                raise RuntimeError("the current lowering path requires an action block for bare record rules")
            record_items.append(NormalizedRecordItem(pattern=None, action=item.action))
            continue
        if isinstance(item.pattern, BeginPattern):
            if not isinstance(item.action, Action):
                raise RuntimeError("the current lowering path requires an action block for BEGIN rules")
            begin_actions.append(item.action)
            continue
        if isinstance(item.pattern, EndPattern):
            if not isinstance(item.action, Action):
                raise RuntimeError("the current lowering path requires an action block for END rules")
            end_actions.append(item.action)
            continue
        if isinstance(item.pattern, ExprPattern):
            record_items.append(NormalizedRecordItem(pattern=item.pattern, action=item.action))
            continue
        if isinstance(item.pattern, RangePattern):
            range_state_name = f"__range.{len(range_state_names)}"
            range_state_names.append(range_state_name)
            record_items.append(
                NormalizedRecordItem(pattern=item.pattern, action=item.action, range_state_name=range_state_name)
            )
            continue
        raise RuntimeError("the current lowering path only supports BEGIN, END, expression, and range patterns")

    return NormalizedLoweringProgram(
        direct_begin_statements=collect_direct_begin_statements(program),
        begin_actions=tuple(begin_actions),
        record_items=tuple(record_items),
        end_actions=tuple(end_actions),
        variable_indexes=collect_variable_indexes(program, extra_names=tuple(range_state_names)),
        array_names=collect_array_names(program),
    )


def collect_direct_begin_statements(program: Program) -> tuple[Stmt, ...] | None:
    """Return the direct-BEGIN lowering form when the program exactly matches it."""
    non_function_items = [item for item in program.items if not isinstance(item, FunctionDef)]
    if len(non_function_items) != 1:
        return None
    item = non_function_items[0]
    if not isinstance(item, PatternAction):
        return None
    if not isinstance(item.pattern, BeginPattern):
        return None
    if not isinstance(item.action, Action):
        return None
    return item.action.statements


def collect_variable_indexes(program: Program, extra_names: tuple[str, ...] = ()) -> dict[str, int]:
    """Collect stable lowering-state indexes for scalar variables in `program`."""
    names: list[str] = []
    seen: set[str] = set()

    def note_name(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        names.append(name)

    def visit_expression(expression: Expr, local_names: frozenset[str] = frozenset()) -> None:
        match expression:
            case NameExpr(name=name):
                if name in local_names:
                    return
                note_name(name)
            case ArrayIndexExpr(array_name=array_name, index=index, extra_indexes=extra_indexes):
                if array_name not in local_names:
                    note_name(array_name)
                visit_expression(index, local_names)
                for extra_index in extra_indexes:
                    visit_expression(extra_index, local_names)
            case BinaryExpr(left=left, right=right):
                visit_expression(left, local_names)
                visit_expression(right, local_names)
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                visit_expression(test, local_names)
                visit_expression(if_true, local_names)
                visit_expression(if_false, local_names)
            case AssignExpr(target=target, value=value):
                visit_lvalue(target, local_names)
                visit_expression(value, local_names)
            case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
                visit_expression(operand, local_names)
            case FieldExpr(index=index):
                if not isinstance(index, int):
                    visit_expression(index, local_names)
            case CallExpr(args=args):
                for argument in args:
                    visit_expression(argument, local_names)
            case _:
                return

    def visit_lvalue(target: NameLValue | ArrayLValue | FieldLValue, local_names: frozenset[str] = frozenset()) -> None:
        match target:
            case NameLValue(name=name):
                if name in local_names:
                    return
                note_name(name)
            case ArrayLValue(name=name, subscripts=subscripts):
                if name not in local_names:
                    note_name(name)
                for subscript in subscripts:
                    visit_expression(subscript, local_names)
            case FieldLValue(index=index):
                visit_expression(index, local_names)

    def visit_statement(statement: Stmt, local_names: frozenset[str] = frozenset()) -> None:
        match statement:
            case AssignStmt(target=target, value=value):
                visit_lvalue(target, local_names)
                visit_expression(value, local_names)
            case ExprStmt(value=value):
                visit_expression(value, local_names)
            case BlockStmt(statements=statements):
                for nested in statements:
                    visit_statement(nested, local_names)
            case DeleteStmt(target=target):
                visit_lvalue(target, local_names)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                visit_expression(condition, local_names)
                visit_statement(then_branch, local_names)
                if else_branch is not None:
                    visit_statement(else_branch, local_names)
            case WhileStmt(condition=condition, body=body):
                visit_expression(condition, local_names)
                visit_statement(body, local_names)
            case DoWhileStmt(body=body, condition=condition):
                visit_statement(body, local_names)
                visit_expression(condition, local_names)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                for expression in init:
                    visit_expression(expression, local_names)
                if condition is not None:
                    visit_expression(condition, local_names)
                for expression in update:
                    visit_expression(expression, local_names)
                visit_statement(body, local_names)
            case ForInStmt(name=name, iterable=iterable, body=body):
                loop_locals = local_names | frozenset({name})
                if name not in local_names:
                    note_name(name)
                visit_expression(iterable, local_names)
                visit_statement(body, loop_locals)
            case PrintStmt(arguments=arguments, redirect=redirect) | PrintfStmt(arguments=arguments, redirect=redirect):
                for argument in arguments:
                    visit_expression(argument, local_names)
                if redirect is not None:
                    visit_expression(redirect.target, local_names)
            case ReturnStmt(value=value):
                if value is not None:
                    visit_expression(value, local_names)
            case _:
                return

    def visit_pattern(pattern: ExprPattern | RangePattern) -> None:
        match pattern:
            case ExprPattern(test=test):
                visit_expression(test)
            case RangePattern(left=left, right=right):
                if not isinstance(left, ExprPattern | RangePattern) or not isinstance(
                    right, ExprPattern | RangePattern
                ):
                    raise RuntimeError("the current lowering path only supports expression endpoints in range patterns")
                visit_pattern(left)
                visit_pattern(right)

    for item in program.items:
        if isinstance(item, FunctionDef):
            local_names = frozenset(item.params)
            for statement in item.body.statements:
                visit_statement(statement, local_names)
            continue
        if not isinstance(item, PatternAction) or not isinstance(item.action, Action):
            continue
        if isinstance(item.pattern, ExprPattern):
            visit_expression(item.pattern.test)
        if isinstance(item.pattern, RangePattern):
            visit_pattern(item.pattern)
        for statement in item.action.statements:
            visit_statement(statement)

    for extra_name in extra_names:
        note_name(extra_name)

    return {name: index for index, name in enumerate(names)}


def collect_array_names(program: Program) -> frozenset[str]:
    """Collect names used as associative arrays in the currently supported surface."""
    names: set[str] = set()

    def visit_expression(expression: Expr, local_names: frozenset[str] = frozenset()) -> None:
        match expression:
            case ArrayIndexExpr(array_name=array_name):
                if array_name in local_names:
                    return
                names.add(array_name)
                for subscript in expression.subscripts:
                    visit_expression(subscript, local_names)
            case BinaryExpr(left=left, right=right):
                visit_expression(left, local_names)
                visit_expression(right, local_names)
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                visit_expression(test, local_names)
                visit_expression(if_true, local_names)
                visit_expression(if_false, local_names)
            case AssignExpr(target=target, value=value):
                visit_lvalue(target, local_names)
                visit_expression(value, local_names)
            case UnaryExpr(operand=operand) | PostfixExpr(operand=operand):
                visit_expression(operand, local_names)
            case FieldExpr(index=index):
                if not isinstance(index, int):
                    visit_expression(index, local_names)
            case CallExpr(args=args):
                for argument in args:
                    visit_expression(argument, local_names)
            case _:
                return

    def visit_lvalue(target: NameLValue | ArrayLValue | FieldLValue, local_names: frozenset[str] = frozenset()) -> None:
        match target:
            case ArrayLValue(name=name, subscripts=subscripts):
                if name in local_names:
                    return
                names.add(name)
                for subscript in subscripts:
                    visit_expression(subscript, local_names)
            case FieldLValue(index=index):
                visit_expression(index, local_names)
            case _:
                return

    def visit_statement(statement: Stmt, local_names: frozenset[str] = frozenset()) -> None:
        match statement:
            case AssignStmt(target=target, value=value):
                visit_lvalue(target, local_names)
                visit_expression(value, local_names)
            case ExprStmt(value=value):
                visit_expression(value, local_names)
            case BlockStmt(statements=statements):
                for nested in statements:
                    visit_statement(nested, local_names)
            case DeleteStmt(target=target):
                visit_lvalue(target, local_names)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                visit_expression(condition, local_names)
                visit_statement(then_branch, local_names)
                if else_branch is not None:
                    visit_statement(else_branch, local_names)
            case WhileStmt(condition=condition, body=body):
                visit_expression(condition, local_names)
                visit_statement(body, local_names)
            case DoWhileStmt(body=body, condition=condition):
                visit_statement(body, local_names)
                visit_expression(condition, local_names)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                for expression in init:
                    visit_expression(expression, local_names)
                if condition is not None:
                    visit_expression(condition, local_names)
                for expression in update:
                    visit_expression(expression, local_names)
                visit_statement(body, local_names)
            case ForInStmt(iterable=iterable, body=body):
                if isinstance(iterable, NameExpr):
                    if iterable.name not in local_names:
                        names.add(iterable.name)
                else:
                    visit_expression(iterable, local_names)
                visit_statement(body, local_names)
            case PrintStmt(arguments=arguments, redirect=redirect) | PrintfStmt(arguments=arguments, redirect=redirect):
                for argument in arguments:
                    visit_expression(argument, local_names)
                if redirect is not None:
                    visit_expression(redirect.target, local_names)
            case ReturnStmt(value=value):
                if value is not None:
                    visit_expression(value, local_names)
            case _:
                return

    for item in program.items:
        if isinstance(item, FunctionDef):
            local_names = frozenset(item.params)
            for statement in item.body.statements:
                visit_statement(statement, local_names)
            continue
        if not isinstance(item, PatternAction) or item.action is None:
            continue
        if isinstance(item.pattern, ExprPattern):
            visit_expression(item.pattern.test)
        if isinstance(item.pattern, RangePattern):
            if isinstance(item.pattern.left, ExprPattern | RangePattern):
                match item.pattern.left:
                    case ExprPattern(test=test):
                        visit_expression(test)
                    case RangePattern():
                        pass
            if isinstance(item.pattern.right, ExprPattern | RangePattern):
                match item.pattern.right:
                    case ExprPattern(test=test):
                        visit_expression(test)
                    case RangePattern():
                        pass
        for statement in item.action.statements:
            visit_statement(statement)

    return frozenset(names)
