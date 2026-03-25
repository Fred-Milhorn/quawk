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
        if isinstance(expression, NameExpr):
            note_name(expression.name)
            return
        if isinstance(expression, ArrayIndexExpr):
            visit_expression(expression.index)
            return
        if isinstance(expression, BinaryExpr):
            visit_expression(expression.left)
            visit_expression(expression.right)

    def visit_statement(statement: Stmt) -> None:
        if isinstance(statement, AssignStmt):
            if statement.index is None:
                note_name(statement.name)
            else:
                visit_expression(statement.index)
            visit_expression(statement.value)
            return
        if isinstance(statement, BlockStmt):
            for nested in statement.statements:
                visit_statement(nested)
            return
        if isinstance(statement, DeleteStmt):
            visit_expression(statement.index)
            return
        if isinstance(statement, IfStmt):
            visit_expression(statement.condition)
            visit_statement(statement.then_branch)
            return
        if isinstance(statement, WhileStmt):
            visit_expression(statement.condition)
            visit_statement(statement.body)
            return
        if isinstance(statement, ForStmt):
            if statement.init is not None:
                visit_statement(statement.init)
            if statement.condition is not None:
                visit_expression(statement.condition)
            if statement.update is not None:
                visit_statement(statement.update)
            visit_statement(statement.body)
            return
        if isinstance(statement, ForInStmt):
            note_name(statement.name)
            note_name(statement.array_name)
            visit_statement(statement.body)
            return
        if isinstance(statement, PrintStmt):
            for argument in statement.arguments:
                visit_expression(argument)

    for item in program.items:
        if not isinstance(item, PatternAction) or not isinstance(item.action, Action):
            continue
        for statement in item.action.statements:
            visit_statement(statement)

    return {name: index for index, name in enumerate(names)}
