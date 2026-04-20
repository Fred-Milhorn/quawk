"""Behavior-oriented coverage for local scalar residency classification (from T-291)."""

from __future__ import annotations

from quawk.ast import Program
from quawk.lexer import lex
from quawk.local_scalar_residency import classify_local_numeric_scalar_residency
from quawk.normalization import normalize_program_for_lowering
from quawk.parser import parse
from quawk.source import ProgramSource
from quawk.type_inference import infer_variable_types

SCALAR_FOLD_LOOP_PROGRAM = (
    "{ n = 4; s = 0; bias = 17; scale = 3; "
    "for (i = 0; i < n; i++) { "
    "base = bias * scale; x = base + i; y = x + 4; z = y - 4; dead = z * 2; "
    "s += z "
    "} "
    "; print s }"
)

FIELD_AGGREGATE_PROGRAM = (
    "{ a = $1 + 0; b = $2 + 0; c = $3 + 0; derived = (b * 3) + c; "
    "if (a < 700) { total += derived; count += 1 } } "
    "END { print total + count }"
)


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def classify(source_text: str):
    program = parse_program(source_text)
    normalized = normalize_program_for_lowering(program)
    type_info = infer_variable_types(program)
    return classify_local_numeric_scalar_residency(program, normalized, type_info)


def test_t291_scalar_fold_loop_names_are_classified_as_record_local_numeric_scalars() -> None:
    residency = classify(SCALAR_FOLD_LOOP_PROGRAM)

    assert residency.begin_local_numeric_names == frozenset()
    assert residency.end_local_numeric_names == frozenset()
    assert residency.record_local_numeric_names == frozenset(
        {"n", "s", "bias", "scale", "i", "base", "x", "y", "z", "dead"}
    )
    assert residency.state_backed_numeric_names == frozenset()


def test_t291_cross_phase_numeric_accumulators_remain_state_backed() -> None:
    residency = classify(FIELD_AGGREGATE_PROGRAM)

    assert residency.record_local_numeric_names == frozenset({"a", "b", "c", "derived"})
    assert residency.end_local_numeric_names == frozenset()
    assert residency.state_backed_numeric_names == frozenset({"total", "count"})


def test_t291_names_shared_across_begin_and_end_do_not_become_local() -> None:
    residency = classify('BEGIN { x = 1 } END { print x }')

    assert residency.begin_local_numeric_names == frozenset()
    assert residency.end_local_numeric_names == frozenset()
    assert residency.state_backed_numeric_names == frozenset({"x"})


def test_t291_user_function_names_remain_state_backed_in_the_conservative_first_pass() -> None:
    residency = classify('function f() { x = 1; y = x + 1; return y } BEGIN { print f() }')

    assert residency.names_for_function("f") == frozenset()
    assert residency.state_backed_numeric_names == frozenset({"x", "y"})
