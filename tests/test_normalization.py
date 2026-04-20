from __future__ import annotations

from quawk.lexer import lex
from quawk.normalization import normalize_program_for_lowering
from quawk.ast import ExprPattern
from quawk.parser import parse
from quawk.source import ProgramSource


def parse_program(source_text: str):
    return parse(lex(ProgramSource.from_inline(source_text)))


def test_normalize_begin_only_program_exposes_direct_begin_statements() -> None:
    normalized = normalize_program_for_lowering(parse_program("BEGIN { x = 1; print x }"))

    assert normalized.direct_begin_statements is not None
    assert len(normalized.direct_begin_statements) == 2
    assert normalized.begin_actions
    assert normalized.record_items == ()
    assert normalized.end_actions == ()
    assert normalized.variable_indexes == {"x": 0}
    assert normalized.slot_allocation.variable_count == 1
    assert normalized.slot_allocation.get_slot("x") is not None
    assert normalized.slot_allocation.get_slot("x").index == 0


def test_normalize_mixed_program_partitions_runtime_phases() -> None:
    normalized = normalize_program_for_lowering(
        parse_program('BEGIN { x = 1 }\n/foo/ { print x }\nEND { print "done" }')
    )

    assert normalized.direct_begin_statements is None
    assert len(normalized.begin_actions) == 1
    assert len(normalized.record_items) == 1
    assert isinstance(normalized.record_items[0].pattern, ExprPattern)
    assert len(normalized.end_actions) == 1
    assert normalized.variable_indexes == {"x": 0}
    assert normalized.slot_allocation.get_slot("x") is not None
    assert normalized.slot_allocation.get_slot("x").index == 0


def test_normalize_multiple_begin_actions_do_not_use_direct_begin_form() -> None:
    normalized = normalize_program_for_lowering(parse_program('BEGIN { print 1 }\nBEGIN { print 2 }'))

    assert normalized.direct_begin_statements is None
    assert len(normalized.begin_actions) == 2


def test_normalize_range_program_includes_range_state_slot_allocation() -> None:
    normalized = normalize_program_for_lowering(parse_program("/a/,/b/ { print $0 }"))

    assert "__range.0" in normalized.variable_indexes
    range_slot = normalized.slot_allocation.get_slot("__range.0")
    assert range_slot is not None
    assert range_slot.index == normalized.variable_indexes["__range.0"]
