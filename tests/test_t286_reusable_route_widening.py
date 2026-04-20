from __future__ import annotations

import pytest

from quawk import jit
from quawk.lexer import lex
from quawk.ast import Program
from quawk.parser import parse
from quawk.source import ProgramSource


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


@pytest.mark.parametrize(
    ("source_text", "marker"),
    [
        ('BEGIN { x = a["k"] }', "call ptr @qk_array_get("),
        ("BEGIN { x = 1; x += 2 }", "fadd double %state.current."),
    ],
)
def test_t286_previously_over_gated_begin_only_programs_now_route_through_reusable_backend(
    source_text: str, marker: str
) -> None:
    program = parse_program(source_text)

    llvm_ir = jit.build_public_inspection_llvm_ir(program, [], None, None)

    assert "define void @quawk_begin(ptr %rt, ptr %state)" in llvm_ir
    assert "define i32 @quawk_main()" in llvm_ir
    assert marker in llvm_ir


@pytest.mark.parametrize(
    "source_text",
    [
        'BEGIN { x = a["k"] }',
        "BEGIN { x = 1; x += 2 }",
    ],
)
def test_t286_public_execution_no_longer_rejects_previously_over_gated_begin_only_programs(
    source_text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert jit.execute(parse_program(source_text)) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
