"""Backend-oriented normalization for the currently supported lowering subset."""

from __future__ import annotations

from dataclasses import dataclass

from .parser import (
    Action,
    ArrayIndexExpr,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BlockStmt,
    DeleteStmt,
    EndPattern,
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
    Stmt,
    WhileStmt,
)


@dataclass(frozen=True)
class NormalizedRecordItem:
    """One normalized record-phase item used by reusable lowering."""

    pattern: ExprPattern | None
    action: Action


@dataclass(frozen=True)
class NormalizedLoweringProgram:
    """Stable lowering-ready shape for the current backend subset."""

    direct_begin_statements: tuple[Stmt, ...] | None
    begin_actions: tuple[Action, ...]
    record_items: tuple[NormalizedRecordItem, ...]
    end_actions: tuple[Action, ...]
    variable_indexes: dict[str, int]


def normalize_program_for_lowering(program: Program) -> NormalizedLoweringProgram:
    """Normalize `program` into the stable shape consumed by lowering."""
    begin_actions: list[Action] = []
    record_items: list[NormalizedRecordItem] = []
    end_actions: list[Action] = []

    for item in program.items:
        if isinstance(item, FunctionDef):
            continue
        if not isinstance(item, PatternAction):
            raise RuntimeError("the current lowering path only supports pattern-action items")
        if not isinstance(item.action, Action):
            raise RuntimeError("the current lowering path requires an action block for each supported item")

        if item.pattern is None:
            record_items.append(NormalizedRecordItem(pattern=None, action=item.action))
            continue
        if isinstance(item.pattern, BeginPattern):
            begin_actions.append(item.action)
            continue
        if isinstance(item.pattern, EndPattern):
            end_actions.append(item.action)
            continue
        if isinstance(item.pattern, ExprPattern):
            record_items.append(NormalizedRecordItem(pattern=item.pattern, action=item.action))
            continue
        raise RuntimeError("the current lowering path only supports BEGIN, END, and regex expression patterns")

    return NormalizedLoweringProgram(
        direct_begin_statements=collect_direct_begin_statements(program),
        begin_actions=tuple(begin_actions),
        record_items=tuple(record_items),
        end_actions=tuple(end_actions),
        variable_indexes=collect_variable_indexes(program),
    )


def collect_direct_begin_statements(program: Program) -> tuple[Stmt, ...] | None:
    """Return the direct-BEGIN lowering form when the program exactly matches it."""
    if len(program.items) != 1:
        return None
    item = program.items[0]
    if not isinstance(item, PatternAction):
        return None
    if not isinstance(item.pattern, BeginPattern):
        return None
    if not isinstance(item.action, Action):
        return None
    return item.action.statements


def collect_variable_indexes(program: Program) -> dict[str, int]:
    """Collect stable lowering-state indexes for scalar variables in `program`."""
    names: list[str] = []
    seen: set[str] = set()

    def note_name(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        names.append(name)

    def visit_expression(expression: Expr) -> None:
        match expression:
            case NameExpr(name=name):
                note_name(name)
            case ArrayIndexExpr(index=index):
                visit_expression(index)
            case BinaryExpr(left=left, right=right):
                visit_expression(left)
                visit_expression(right)
            case _:
                return

    def visit_statement(statement: Stmt) -> None:
        match statement:
            case AssignStmt(name=name, index=index, value=value):
                if index is None:
                    note_name(name)
                else:
                    visit_expression(index)
                visit_expression(value)
            case BlockStmt(statements=statements):
                for nested in statements:
                    visit_statement(nested)
            case DeleteStmt(index=index):
                visit_expression(index)
            case IfStmt(condition=condition, then_branch=then_branch):
                visit_expression(condition)
                visit_statement(then_branch)
            case WhileStmt(condition=condition, body=body):
                visit_expression(condition)
                visit_statement(body)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                if init is not None:
                    visit_statement(init)
                if condition is not None:
                    visit_expression(condition)
                if update is not None:
                    visit_statement(update)
                visit_statement(body)
            case ForInStmt(name=name, array_name=array_name, body=body):
                note_name(name)
                note_name(array_name)
                visit_statement(body)
            case PrintStmt(arguments=arguments):
                for argument in arguments:
                    visit_expression(argument)
            case _:
                return

    for item in program.items:
        if not isinstance(item, PatternAction) or not isinstance(item.action, Action):
            continue
        for statement in item.action.statements:
            visit_statement(statement)

    return {name: index for index, name in enumerate(names)}
