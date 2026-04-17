from __future__ import annotations

import re
from pathlib import Path

import pytest

from quawk import jit
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


@pytest.mark.parametrize(
    ("source_text", "message"),
    [
        ("BEGIN { print $1 }", "field expressions require the reusable runtime backend"),
        (
            "BEGIN { x = $1 }",
            "the current backend only supports numeric literals, variable reads, and the current arithmetic/boolean subset",
        ),
        (
            'BEGIN { x = a["k"] }',
            "host-runtime-only operations are not supported by the LLVM-backed backend",
        ),
        (
            "BEGIN { x = 1; x += 2 }",
            "host-runtime-only operations are not supported by the LLVM-backed backend",
        ),
        (
            'BEGIN { if ("a" "b") x = 1 }',
            "unsupported binary operator in numeric expression: CONCAT",
        ),
        (
            "BEGIN { x = !1 }",
            "the current backend only supports numeric literals, variable reads, and the current arithmetic/boolean subset",
        ),
        (
            "BEGIN { x = ++y }",
            "the current backend only supports numeric literals, variable reads, and the current arithmetic/boolean subset",
        ),
    ],
)
def test_t284_representative_over_gated_programs_fail_under_current_direct_path(
    source_text: str, message: str
) -> None:
    program = parse_program(source_text)

    with pytest.raises(RuntimeError, match=re.escape(message)):
        jit.lower_to_llvm_ir(program)


@pytest.mark.parametrize(
    ("blocked_program", "reusable_peer"),
    [
        ("BEGIN { x = $1 }", "BEGIN { x = $1; print x }"),
        ('BEGIN { x = a["k"] }', 'BEGIN { x = a["k"]; print x }'),
        ("BEGIN { x = 1; x += 2 }", "BEGIN { x = 1; x += 2; print x }"),
        ("BEGIN { x = !1 }", "BEGIN { x = !1; print x }"),
        ("BEGIN { x = ++y }", "BEGIN { x = ++y; print x }"),
        ('BEGIN { if ("a" "b") x = 1 }', 'BEGIN { print ("a" "b") }'),
    ],
)
def test_t284_closely_related_programs_already_lower_through_reusable_backend_path(
    blocked_program: str, reusable_peer: str
) -> None:
    with pytest.raises(RuntimeError):
        jit.lower_to_llvm_ir(parse_program(blocked_program))

    llvm_ir = jit.lower_to_llvm_ir(parse_program(reusable_peer))

    assert "define void @quawk_begin(ptr %rt, ptr %state)" in llvm_ir
    assert "define void @quawk_end(ptr %rt, ptr %state)" in llvm_ir


def test_t284_plan_doc_records_the_direct_path_baseline_and_next_steps() -> None:
    plan_text = (ROOT / "docs" / "plans" / "direct-path-removal-plan.md").read_text(encoding="utf-8")

    assert "## T-284 Baseline Result" in plan_text
    assert "Focused routing regressions now pin the representative over-gated rows" in plan_text
    assert "`BEGIN { print $1 }` still fails during lowering" in plan_text
    assert "`BEGIN { x = a[\"k\"] }` still fails" in plan_text
    assert "`BEGIN { x = 1; x += 2 }` still fails" in plan_text
    assert "`T-285` to remove the restricted direct-lowering fallback" in plan_text


def test_t284_roadmap_marks_the_baseline_done_and_advances_to_t285() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "### P33: Direct-Path Removal And Route Cleanup" in roadmap_text
    assert "`T-284` is complete." in roadmap_text
    assert "| T-284 | P33 | P0 | Author the direct-path-removal baseline and representative routing regressions | T-283 | Focused tests and roadmap text make the remaining direct-lane entrypoints, stale guards, and representative over-gated programs explicit before implementation | done |" in roadmap_text
    assert "- `T-284`" not in roadmap_text.split("Immediate next tasks:")[1]
    assert "- `T-285` Remove the restricted direct lowering lane and route compiled" in roadmap_text
