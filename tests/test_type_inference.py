"""Tests for the type lattice (T-235)."""

from __future__ import annotations

import pytest

from quawk.lexer import lex
from quawk.parser import PatternAction, PrintStmt, parse
from quawk.source import ProgramSource
from quawk.type_inference import LatticeType, can_be_numeric, can_be_string, infer_expression_type, join, join_all


def parse_begin_print_expr(source_expression: str):
    program = parse(lex(ProgramSource.from_inline(f"BEGIN {{ print {source_expression} }}")))
    item = program.items[0]
    assert isinstance(item, PatternAction)
    assert item.action is not None
    statement = item.action.statements[0]
    assert isinstance(statement, PrintStmt)
    assert statement.arguments
    return statement.arguments[0]


# ---------------------------------------------------------------------------
# LatticeType members
# ---------------------------------------------------------------------------

class TestLatticeTypeMembers:

    def test_members_have_expected_values(self) -> None:
        assert LatticeType.UNKNOWN.value == "unknown"
        assert LatticeType.NUMERIC.value == "numeric"
        assert LatticeType.STRING.value == "string"
        assert LatticeType.MIXED.value == "mixed"

    def test_str_representation(self) -> None:
        assert str(LatticeType.NUMERIC) == "numeric"
        assert str(LatticeType.UNKNOWN) == "unknown"


# ---------------------------------------------------------------------------
# join
# ---------------------------------------------------------------------------

class TestJoin:

    @pytest.mark.parametrize(
        "left, right",
        [
            (LatticeType.UNKNOWN, LatticeType.UNKNOWN),
            (LatticeType.NUMERIC, LatticeType.NUMERIC),
            (LatticeType.STRING, LatticeType.STRING),
            (LatticeType.MIXED, LatticeType.MIXED),
        ],
    )
    def test_identical_types_return_same(self, left: LatticeType, right: LatticeType) -> None:
        assert join(left, right) is left

    def test_unknown_with_numeric(self) -> None:
        assert join(LatticeType.UNKNOWN, LatticeType.NUMERIC) is LatticeType.NUMERIC
        assert join(LatticeType.NUMERIC, LatticeType.UNKNOWN) is LatticeType.NUMERIC

    def test_unknown_with_string(self) -> None:
        assert join(LatticeType.UNKNOWN, LatticeType.STRING) is LatticeType.STRING
        assert join(LatticeType.STRING, LatticeType.UNKNOWN) is LatticeType.STRING

    def test_numeric_with_string(self) -> None:
        assert join(LatticeType.NUMERIC, LatticeType.STRING) is LatticeType.MIXED
        assert join(LatticeType.STRING, LatticeType.NUMERIC) is LatticeType.MIXED

    def test_mixed_subsumes_numeric(self) -> None:
        assert join(LatticeType.MIXED, LatticeType.NUMERIC) is LatticeType.MIXED
        assert join(LatticeType.NUMERIC, LatticeType.MIXED) is LatticeType.MIXED

    def test_mixed_subsumes_string(self) -> None:
        assert join(LatticeType.MIXED, LatticeType.STRING) is LatticeType.MIXED
        assert join(LatticeType.STRING, LatticeType.MIXED) is LatticeType.MIXED

    def test_mixed_subsumes_unknown(self) -> None:
        assert join(LatticeType.MIXED, LatticeType.UNKNOWN) is LatticeType.MIXED

    def test_mixed_with_mixed(self) -> None:
        assert join(LatticeType.MIXED, LatticeType.MIXED) is LatticeType.MIXED

    def test_join_is_commutative(self) -> None:
        all_types = list(LatticeType)
        for a in all_types:
            for b in all_types:
                assert join(a, b) is join(b, a)

    def test_join_is_associative(self) -> None:
        all_types = list(LatticeType)
        for a in all_types:
            for b in all_types:
                for c in all_types:
                    assert join(join(a, b), c) is join(a, join(b, c))

    def test_unknown_is_identity(self) -> None:
        all_types = list(LatticeType)
        for t in all_types:
            assert join(LatticeType.UNKNOWN, t) is t
            assert join(t, LatticeType.UNKNOWN) is t

    def test_mixed_is_top(self) -> None:
        all_types = list(LatticeType)
        for t in all_types:
            assert join(LatticeType.MIXED, t) is LatticeType.MIXED


# ---------------------------------------------------------------------------
# join_all
# ---------------------------------------------------------------------------

class TestJoinAll:

    def test_empty_sequence_returns_unknown(self) -> None:
        assert join_all([]) is LatticeType.UNKNOWN

    def test_single_element(self) -> None:
        assert join_all([LatticeType.NUMERIC]) is LatticeType.NUMERIC

    def test_multiple_same(self) -> None:
        assert join_all([LatticeType.NUMERIC, LatticeType.NUMERIC]) is LatticeType.NUMERIC

    def test_fold_numeric_then_string(self) -> None:
        assert join_all([LatticeType.NUMERIC, LatticeType.STRING]) is LatticeType.MIXED

    def test_fold_three_distinct(self) -> None:
        assert join_all([LatticeType.NUMERIC, LatticeType.STRING, LatticeType.MIXED]) is LatticeType.MIXED

    def test_fold_with_unknowns(self) -> None:
        assert join_all([LatticeType.UNKNOWN, LatticeType.NUMERIC, LatticeType.UNKNOWN]) is LatticeType.NUMERIC

    def test_fold_tuple_input(self) -> None:
        assert join_all((LatticeType.NUMERIC, LatticeType.STRING)) is LatticeType.MIXED


# ---------------------------------------------------------------------------
# can_be_numeric / can_be_string
# ---------------------------------------------------------------------------

class TestCanBeNumeric:

    def test_unknown(self) -> None:
        assert can_be_numeric(LatticeType.UNKNOWN) is True

    def test_numeric(self) -> None:
        assert can_be_numeric(LatticeType.NUMERIC) is True

    def test_string(self) -> None:
        assert can_be_numeric(LatticeType.STRING) is False

    def test_mixed(self) -> None:
        assert can_be_numeric(LatticeType.MIXED) is True


class TestCanBeString:

    def test_unknown(self) -> None:
        assert can_be_string(LatticeType.UNKNOWN) is True

    def test_numeric(self) -> None:
        assert can_be_string(LatticeType.NUMERIC) is False

    def test_string(self) -> None:
        assert can_be_string(LatticeType.STRING) is True

    def test_mixed(self) -> None:
        assert can_be_string(LatticeType.MIXED) is True


# ---------------------------------------------------------------------------
# infer_expression_type (T-236)
# ---------------------------------------------------------------------------

class TestInferExpressionType:

    def test_numeric_literal_is_numeric(self) -> None:
        expression = parse_begin_print_expr("1")
        assert infer_expression_type(expression) is LatticeType.NUMERIC

    def test_string_literal_is_string(self) -> None:
        expression = parse_begin_print_expr('"x"')
        assert infer_expression_type(expression) is LatticeType.STRING

    def test_name_defaults_to_unknown(self) -> None:
        expression = parse_begin_print_expr("x")
        assert infer_expression_type(expression) is LatticeType.UNKNOWN

    def test_name_uses_variable_environment(self) -> None:
        expression = parse_begin_print_expr("x")
        assert infer_expression_type(expression, {"x": LatticeType.NUMERIC}) is LatticeType.NUMERIC

    def test_addition_over_unknown_name_and_numeric_literal_is_numeric(self) -> None:
        expression = parse_begin_print_expr("x + 1")
        assert infer_expression_type(expression) is LatticeType.NUMERIC

    def test_addition_with_known_string_operand_is_mixed(self) -> None:
        expression = parse_begin_print_expr("x + 1")
        assert infer_expression_type(expression, {"x": LatticeType.STRING}) is LatticeType.MIXED

    def test_concat_is_string(self) -> None:
        expression = parse_begin_print_expr('"a" "b"')
        assert infer_expression_type(expression) is LatticeType.STRING

    def test_ternary_joins_branch_types(self) -> None:
        expression = parse_begin_print_expr('1 ? "x" : 2')
        assert infer_expression_type(expression) is LatticeType.MIXED
