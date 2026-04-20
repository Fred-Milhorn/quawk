"""Conservative residency classification for backend-local numeric scalars."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .ast import (
    Action,
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignOp,
    AssignStmt,
    BinaryExpr,
    BlockStmt,
    CallExpr,
    ConditionalExpr,
    DeleteStmt,
    DoWhileStmt,
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
)
from .ast_walk import lvalue_expressions
from .builtins import is_builtin_variable_name
from .normalization import NormalizedLoweringProgram, NormalizedRecordItem, normalize_program_for_lowering
from .type_inference import LatticeType, infer_variable_types


@dataclass(frozen=True)
class LocalScalarResidency:
    """Per-lowered-function classification for numeric scalars that can stay local."""

    begin_local_numeric_names: frozenset[str]
    record_local_numeric_names: frozenset[str]
    end_local_numeric_names: frozenset[str]
    function_local_numeric_names: Mapping[str, frozenset[str]]
    state_backed_numeric_names: frozenset[str]

    def __post_init__(self) -> None:
        frozen_function_names = MappingProxyType(
            {
                name: frozenset(local_names)
                for name, local_names in sorted(self.function_local_numeric_names.items())
            }
        )
        object.__setattr__(self, "function_local_numeric_names", frozen_function_names)

    @property
    def all_local_numeric_names(self) -> frozenset[str]:
        """Return the union of all currently local-resident numeric scalar names."""
        combined = (
            set(self.begin_local_numeric_names)
            | set(self.record_local_numeric_names)
            | set(self.end_local_numeric_names)
        )
        for local_names in self.function_local_numeric_names.values():
            combined.update(local_names)
        return frozenset(combined)

    def names_for_phase(self, phase: str) -> frozenset[str]:
        """Return the local numeric names for one reusable lowered phase."""
        if phase == "begin":
            return self.begin_local_numeric_names
        if phase == "record":
            return self.record_local_numeric_names
        if phase == "end":
            return self.end_local_numeric_names
        raise ValueError(f"unknown lowered phase: {phase}")

    def names_for_function(self, name: str) -> frozenset[str]:
        """Return the local numeric names for one lowered user function."""
        return self.function_local_numeric_names.get(name, frozenset())


@dataclass(frozen=True)
class _AnalysisResult:
    assigned_after: frozenset[str]
    encountered_names: frozenset[str]
    assigned_names: frozenset[str]
    read_before_assignment_names: frozenset[str]


@dataclass(frozen=True)
class _UnitSummary:
    encountered_names: frozenset[str]
    assigned_names: frozenset[str]
    read_before_assignment_names: frozenset[str]


def classify_local_numeric_scalar_residency(
    program: Program,
    normalized_program: NormalizedLoweringProgram | None = None,
    type_info: Mapping[str, LatticeType] | None = None,
) -> LocalScalarResidency:
    """Classify which inferred-numeric scalars can stay local to one lowered function.

    This first pass is intentionally conservative:
    - only inferred-numeric scalar names are considered
    - names shared across lowered units remain state-backed
    - user-defined function names remain state-backed for now
    - a name must be assigned before every read within its lowered unit
    """

    lowering_program = normalize_program_for_lowering(program) if normalized_program is None else normalized_program
    inferred_types = infer_variable_types(program) if type_info is None else type_info
    tracked_numeric_names = frozenset(
        name
        for name in lowering_program.variable_indexes
        if inferred_types.get(name) is LatticeType.NUMERIC
        and name not in lowering_program.array_names
        and not is_builtin_variable_name(name)
        and not _is_reusable_runtime_state_name(name)
    )

    if not tracked_numeric_names:
        return LocalScalarResidency(
            begin_local_numeric_names=frozenset(),
            record_local_numeric_names=frozenset(),
            end_local_numeric_names=frozenset(),
            function_local_numeric_names={},
            state_backed_numeric_names=frozenset(),
        )

    def empty_result(assigned: frozenset[str]) -> _AnalysisResult:
        return _AnalysisResult(
            assigned_after=assigned,
            encountered_names=frozenset(),
            assigned_names=frozenset(),
            read_before_assignment_names=frozenset(),
        )

    def combine_results(assigned_after: frozenset[str], *results: _AnalysisResult) -> _AnalysisResult:
        encountered: set[str] = set()
        assigned_names: set[str] = set()
        read_before: set[str] = set()
        for result in results:
            encountered.update(result.encountered_names)
            assigned_names.update(result.assigned_names)
            read_before.update(result.read_before_assignment_names)
        return _AnalysisResult(
            assigned_after=assigned_after,
            encountered_names=frozenset(encountered),
            assigned_names=frozenset(assigned_names),
            read_before_assignment_names=frozenset(read_before),
        )

    def read_name(name: str, assigned: frozenset[str], local_names: frozenset[str]) -> _AnalysisResult:
        if name in local_names or name not in tracked_numeric_names:
            return empty_result(assigned)
        return _AnalysisResult(
            assigned_after=assigned,
            encountered_names=frozenset({name}),
            assigned_names=frozenset(),
            read_before_assignment_names=frozenset() if name in assigned else frozenset({name}),
        )

    def assign_name(
        name: str,
        assigned: frozenset[str],
        local_names: frozenset[str],
        *,
        requires_prior_value: bool,
    ) -> _AnalysisResult:
        if name in local_names or name not in tracked_numeric_names:
            return empty_result(assigned)
        read_before = frozenset({name}) if requires_prior_value and name not in assigned else frozenset()
        return _AnalysisResult(
            assigned_after=assigned | frozenset({name}),
            encountered_names=frozenset({name}),
            assigned_names=frozenset({name}),
            read_before_assignment_names=read_before,
        )

    def analyze_lvalue_indexes(
        target: NameLValue | ArrayLValue | FieldLValue,
        assigned: frozenset[str],
        local_names: frozenset[str],
    ) -> _AnalysisResult:
        return analyze_expression_sequence(tuple(lvalue_expressions(target)), assigned, local_names)

    def analyze_expression_sequence(
        expressions: tuple[Expr, ...] | list[Expr],
        assigned: frozenset[str],
        local_names: frozenset[str],
    ) -> _AnalysisResult:
        current_assigned = assigned
        results: list[_AnalysisResult] = []
        for expression in expressions:
            result = analyze_expression(expression, current_assigned, local_names)
            results.append(result)
            current_assigned = result.assigned_after
        return combine_results(current_assigned, *results)

    def analyze_expression(
        expression: Expr,
        assigned: frozenset[str],
        local_names: frozenset[str],
    ) -> _AnalysisResult:
        match expression:
            case NameExpr(name=name):
                return read_name(name, assigned, local_names)
            case ArrayIndexExpr(index=index, extra_indexes=extra_indexes):
                index_result = analyze_expression(index, assigned, local_names)
                extra_result = analyze_expression_sequence(extra_indexes, index_result.assigned_after, local_names)
                return combine_results(extra_result.assigned_after, index_result, extra_result)
            case BinaryExpr(left=left, right=right):
                left_result = analyze_expression(left, assigned, local_names)
                right_result = analyze_expression(right, left_result.assigned_after, local_names)
                return combine_results(right_result.assigned_after, left_result, right_result)
            case ConditionalExpr(test=test, if_true=if_true, if_false=if_false):
                test_result = analyze_expression(test, assigned, local_names)
                true_result = analyze_expression(if_true, test_result.assigned_after, local_names)
                false_result = analyze_expression(if_false, test_result.assigned_after, local_names)
                return combine_results(
                    true_result.assigned_after & false_result.assigned_after,
                    test_result,
                    true_result,
                    false_result,
                )
            case AssignExpr(target=target, op=op, value=value):
                target_index_result = analyze_lvalue_indexes(target, assigned, local_names)
                value_result = analyze_expression(value, target_index_result.assigned_after, local_names)
                if isinstance(target, NameLValue):
                    assignment_result = assign_name(
                        target.name,
                        value_result.assigned_after,
                        local_names,
                        requires_prior_value=op is not AssignOp.PLAIN,
                    )
                    return combine_results(assignment_result.assigned_after, target_index_result, value_result, assignment_result)
                return combine_results(value_result.assigned_after, target_index_result, value_result)
            case UnaryExpr(op=UnaryOp.PRE_INC | UnaryOp.PRE_DEC, operand=NameExpr(name=name)):
                read_result = read_name(name, assigned, local_names)
                assign_result = assign_name(name, read_result.assigned_after, local_names, requires_prior_value=False)
                return combine_results(assign_result.assigned_after, read_result, assign_result)
            case UnaryExpr(operand=operand):
                return analyze_expression(operand, assigned, local_names)
            case PostfixExpr(op=PostfixOp.POST_INC | PostfixOp.POST_DEC, operand=NameExpr(name=name)):
                read_result = read_name(name, assigned, local_names)
                assign_result = assign_name(name, read_result.assigned_after, local_names, requires_prior_value=False)
                return combine_results(assign_result.assigned_after, read_result, assign_result)
            case PostfixExpr(operand=operand):
                return analyze_expression(operand, assigned, local_names)
            case FieldExpr(index=index):
                if isinstance(index, int):
                    return empty_result(assigned)
                return analyze_expression(index, assigned, local_names)
            case CallExpr(args=args):
                return analyze_expression_sequence(args, assigned, local_names)
            case GetlineExpr(target=target, source=source):
                source_result = empty_result(assigned) if source is None else analyze_expression(source, assigned, local_names)
                if target is None:
                    return source_result
                target_result = analyze_lvalue_indexes(target, source_result.assigned_after, local_names)
                return combine_results(target_result.assigned_after, source_result, target_result)
            case _:
                return empty_result(assigned)

    def analyze_statement_sequence(
        statements: tuple[Stmt, ...] | list[Stmt],
        assigned: frozenset[str],
        local_names: frozenset[str],
    ) -> _AnalysisResult:
        current_assigned = assigned
        results: list[_AnalysisResult] = []
        for statement in statements:
            result = analyze_statement(statement, current_assigned, local_names)
            results.append(result)
            current_assigned = result.assigned_after
        return combine_results(current_assigned, *results)

    def analyze_statement(
        statement: Stmt,
        assigned: frozenset[str],
        local_names: frozenset[str],
    ) -> _AnalysisResult:
        match statement:
            case AssignStmt(target=target, op=op, value=value):
                target_index_result = analyze_lvalue_indexes(target, assigned, local_names)
                value_result = analyze_expression(value, target_index_result.assigned_after, local_names)
                if isinstance(target, NameLValue):
                    assignment_result = assign_name(
                        target.name,
                        value_result.assigned_after,
                        local_names,
                        requires_prior_value=op is not AssignOp.PLAIN,
                    )
                    return combine_results(assignment_result.assigned_after, target_index_result, value_result, assignment_result)
                return combine_results(value_result.assigned_after, target_index_result, value_result)
            case ExprStmt(value=value):
                return analyze_expression(value, assigned, local_names)
            case PrintStmt(arguments=arguments, redirect=redirect) | PrintfStmt(arguments=arguments, redirect=redirect):
                arguments_result = analyze_expression_sequence(arguments, assigned, local_names)
                if redirect is None:
                    return arguments_result
                redirect_result = analyze_expression(redirect.target, arguments_result.assigned_after, local_names)
                return combine_results(redirect_result.assigned_after, arguments_result, redirect_result)
            case BlockStmt(statements=statements):
                return analyze_statement_sequence(statements, assigned, local_names)
            case IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch):
                condition_result = analyze_expression(condition, assigned, local_names)
                then_result = analyze_statement(then_branch, condition_result.assigned_after, local_names)
                if else_branch is None:
                    return combine_results(condition_result.assigned_after & then_result.assigned_after, condition_result, then_result)
                else_result = analyze_statement(else_branch, condition_result.assigned_after, local_names)
                return combine_results(
                    then_result.assigned_after & else_result.assigned_after,
                    condition_result,
                    then_result,
                    else_result,
                )
            case WhileStmt(condition=condition, body=body):
                condition_result = analyze_expression(condition, assigned, local_names)
                body_result = analyze_statement(body, condition_result.assigned_after, local_names)
                return combine_results(condition_result.assigned_after, condition_result, body_result)
            case DoWhileStmt(body=body, condition=condition):
                body_result = analyze_statement(body, assigned, local_names)
                condition_result = analyze_expression(condition, body_result.assigned_after, local_names)
                return combine_results(assigned, body_result, condition_result)
            case ForStmt(init=init, condition=condition, update=update, body=body):
                init_result = analyze_expression_sequence(init, assigned, local_names)
                if condition is None:
                    condition_result = empty_result(init_result.assigned_after)
                else:
                    condition_result = analyze_expression(condition, init_result.assigned_after, local_names)
                body_result = analyze_statement(body, condition_result.assigned_after, local_names)
                update_result = analyze_expression_sequence(update, body_result.assigned_after, local_names)
                return combine_results(condition_result.assigned_after, init_result, condition_result, body_result, update_result)
            case ForInStmt(name=name, iterable=iterable, body=body):
                iterable_result = analyze_expression(iterable, assigned, local_names)
                body_result = analyze_statement(body, iterable_result.assigned_after, local_names | frozenset({name}))
                return combine_results(iterable_result.assigned_after, iterable_result, body_result)
            case DeleteStmt(target=target):
                return analyze_lvalue_indexes(target, assigned, local_names)
            case ReturnStmt(value=value):
                if value is None:
                    return empty_result(assigned)
                return analyze_expression(value, assigned, local_names)
            case _:
                return empty_result(assigned)

    def analyze_action(action: Action, local_names: frozenset[str]) -> _UnitSummary:
        result = analyze_statement_sequence(action.statements, frozenset(), local_names)
        return _UnitSummary(
            encountered_names=result.encountered_names,
            assigned_names=result.assigned_names,
            read_before_assignment_names=result.read_before_assignment_names,
        )

    def analyze_action_sequence_summary(actions: tuple[Action, ...]) -> _UnitSummary:
        current_assigned = frozenset()
        results: list[_AnalysisResult] = []
        for action in actions:
            action_result = analyze_statement_sequence(action.statements, current_assigned, frozenset())
            results.append(action_result)
            current_assigned = action_result.assigned_after
        combined = combine_results(current_assigned, *results)
        return _UnitSummary(
            encountered_names=combined.encountered_names,
            assigned_names=combined.assigned_names,
            read_before_assignment_names=combined.read_before_assignment_names,
        )

    def analyze_pattern(pattern: ExprPattern | RangePattern, assigned: frozenset[str]) -> _AnalysisResult:
        match pattern:
            case ExprPattern(test=test):
                return analyze_expression(test, assigned, frozenset())
            case RangePattern(left=left, right=right):
                left_result = analyze_pattern(left, assigned)
                right_result = analyze_pattern(right, assigned)
                return combine_results(assigned, left_result, right_result)

    def analyze_record_items(record_items: tuple[NormalizedRecordItem, ...]) -> _UnitSummary:
        current_assigned = frozenset()
        results: list[_AnalysisResult] = []
        for record_item in record_items:
            if record_item.pattern is None:
                action_result = empty_result(current_assigned)
                if record_item.action is not None:
                    action_result = analyze_statement_sequence(record_item.action.statements, current_assigned, frozenset())
                results.append(action_result)
                current_assigned = action_result.assigned_after
                continue

            pattern_result = analyze_pattern(record_item.pattern, current_assigned)
            results.append(pattern_result)
            current_assigned = pattern_result.assigned_after
            if record_item.action is None:
                continue
            action_result = analyze_statement_sequence(record_item.action.statements, current_assigned, frozenset())
            results.append(action_result)
            current_assigned = current_assigned & action_result.assigned_after

        combined = combine_results(current_assigned, *results)
        return _UnitSummary(
            encountered_names=combined.encountered_names,
            assigned_names=combined.assigned_names,
            read_before_assignment_names=combined.read_before_assignment_names,
        )

    def names_from_summary(summary: _UnitSummary, shared_numeric_names: frozenset[str], *, allow_local: bool) -> frozenset[str]:
        if not allow_local:
            return frozenset()
        return frozenset(
            name
            for name in summary.assigned_names
            if name not in shared_numeric_names and name not in summary.read_before_assignment_names
        )

    begin_summary = analyze_action_sequence_summary(lowering_program.begin_actions)
    record_summary = analyze_record_items(lowering_program.record_items)
    end_summary = analyze_action_sequence_summary(lowering_program.end_actions)
    function_summaries = {
        item.name: analyze_action(item.body, frozenset(item.params))
        for item in program.items
        if isinstance(item, FunctionDef)
    }

    usage_by_name: dict[str, set[str]] = {}

    def note_summary(unit_name: str, summary: _UnitSummary) -> None:
        for name in summary.encountered_names:
            usage_by_name.setdefault(name, set()).add(unit_name)

    note_summary("begin", begin_summary)
    note_summary("record", record_summary)
    note_summary("end", end_summary)
    for function_name, summary in function_summaries.items():
        note_summary(f"function:{function_name}", summary)

    shared_numeric_names = frozenset(name for name, units in usage_by_name.items() if len(units) > 1)
    begin_local_names = names_from_summary(begin_summary, shared_numeric_names, allow_local=True)
    record_local_names = names_from_summary(record_summary, shared_numeric_names, allow_local=True)
    end_local_names = names_from_summary(end_summary, shared_numeric_names, allow_local=True)
    function_local_names = {
        function_name: names_from_summary(summary, shared_numeric_names, allow_local=False)
        for function_name, summary in function_summaries.items()
    }

    all_local_names = begin_local_names | record_local_names | end_local_names
    state_backed_numeric_names = frozenset(sorted(tracked_numeric_names - all_local_names))
    return LocalScalarResidency(
        begin_local_numeric_names=begin_local_names,
        record_local_numeric_names=record_local_names,
        end_local_numeric_names=end_local_names,
        function_local_numeric_names=function_local_names,
        state_backed_numeric_names=state_backed_numeric_names,
    )


def _is_reusable_runtime_state_name(name: str) -> bool:
    """Report whether one lowering-only runtime state name is reserved."""
    return name.startswith("__range.")
