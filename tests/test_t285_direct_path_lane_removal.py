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
    "source_text",
    [
        "BEGIN { print $1 }",
        "BEGIN { x = $1 }",
        'BEGIN { if ("a" "b") x = 1 }',
        "BEGIN { x = !1 }",
        "BEGIN { x = ++y }",
    ],
)
def test_t285_begin_only_programs_no_longer_use_the_direct_lowering_lane(source_text: str) -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(source_text))

    assert "define void @quawk_begin(ptr %rt, ptr %state)" in llvm_ir
    assert "define i32 @quawk_main()" not in llvm_ir


def test_t285_public_inspection_ir_links_a_driver_for_simple_begin_programs(monkeypatch) -> None:
    program = parse_program('BEGIN { print "hello" }')
    captured: dict[str, object] = {}

    def fake_lower_to_llvm_ir(
        lowered_program: Program, initial_variables: jit.InitialVariables | None = None
    ) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; reusable begin-only module"

    def fake_link_reusable_inspection_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        captured["called"] = True
        assert llvm_ir == "; reusable begin-only module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked reusable begin-only module"

    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_inspection_module", fake_link_reusable_inspection_module)

    assert jit.build_public_inspection_llvm_ir(program, [], None, None) == "; linked reusable begin-only module"
    assert captured["called"] is True
