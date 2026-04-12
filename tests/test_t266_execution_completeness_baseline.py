from __future__ import annotations

from pathlib import Path

import pytest

from quawk import jit
from quawk.lexer import lex
from quawk.parser import parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent


def parse_program(source_text: str):
    return parse(lex(ProgramSource.from_inline(source_text)))


REPRESENTATIVE_GAPS = (
    (
        "multi_subscript_array",
        "BEGIN { a[1, 2] = 3; print a[1, 2] }",
        "public execution does not support programs outside the compiled backend/runtime subset",
        "host-runtime-only operations are not supported by the LLVM-backed backend",
    ),
    (
        "side_effectful_ternary",
        "BEGIN { x = 0; print (1 ? ++x : 0); print x }",
        "public execution does not support programs outside the compiled backend/runtime subset",
        "host-runtime-only operations are not supported by the LLVM-backed backend",
    ),
    (
        "dynamic_printf_format",
        'BEGIN { fmt = "%d %d\\n"; printf fmt, 1, 2 }',
        "public execution does not support programs outside the compiled backend/runtime subset",
        "host-runtime-only operations are not supported by the LLVM-backed backend",
    ),
)


@pytest.mark.parametrize(
    ("_case_name", "source_text", "execute_message", "lower_message"),
    REPRESENTATIVE_GAPS,
)
def test_t266_representative_gap_programs_fail_clearly_in_public_execution(
    _case_name: str,
    source_text: str,
    execute_message: str,
    lower_message: str,
) -> None:
    program = parse_program(source_text)

    with pytest.raises(RuntimeError, match=execute_message):
        jit.execute(program)

    with pytest.raises(RuntimeError, match=lower_message):
        jit.lower_to_llvm_ir(program)


def test_t266_matrix_records_the_representative_execution_completeness_gaps() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "execution-completeness-matrix.md").read_text(encoding="utf-8")

    assert "Frontend semantic validation passes today" in matrix_text
    assert "Public execute today" in matrix_text
    assert "Inspection today" in matrix_text
    assert "Public host fallback exists today" in matrix_text
    assert "| Multi-subscript array access |" in matrix_text
    assert "| Side-effectful ternary branch |" in matrix_text
    assert "| Dynamic `printf` format |" in matrix_text
    assert "no row in this matrix currently keeps public Python host fallback alive" in matrix_text
    assert "## T-266 Baseline Result" in matrix_text
    assert "## T-267 Narrowing Result" in matrix_text


def test_t266_plan_and_roadmap_point_to_the_checked_in_baseline() -> None:
    plan_text = (ROOT / "docs" / "plans" / "execution-completeness-plan.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "[execution-completeness-matrix.md](execution-completeness-matrix.md)" in plan_text
    assert "### P30: Execution Completeness Closure" in roadmap_text
    assert "| T-266 | P30 | P0 | Author execution-completeness baseline and representative gap tests | T-265 | Direct tests and a checked-in matrix pin the remaining grammar-valid backend gaps before implementation | done |" in roadmap_text
    assert "| T-267 | P30 | P0 | Widen runtime-backed user-defined function lowering and retire direct-function-only restrictions | T-266 |" in roadmap_text
