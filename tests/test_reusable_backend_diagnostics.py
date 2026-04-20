"""Behavior-oriented coverage for reusable backend diagnostics and gating (from T-287)."""

from __future__ import annotations

import pytest

from quawk import jit
from quawk.ast import Program
from quawk.lexer import lex
from quawk.parser import parse
from quawk.source import ProgramSource


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def test_t287_lowering_no_longer_blocks_supported_programs_behind_generic_backend_subset_gates() -> None:
    program = parse_program("BEGIN { delete x }")

    llvm_ir = jit.lower_to_llvm_ir(program)

    assert "define void @quawk_begin(ptr %rt, ptr %state)" in llvm_ir
    assert "@qk_array_clear" in llvm_ir


def test_t287_public_execution_no_longer_blocks_supported_programs_behind_generic_backend_subset_gates() -> None:
    program = parse_program("BEGIN { delete x }")

    assert jit.execute(program) == 0


def test_t287_runtime_gap_diagnostics_remain_specific_to_reusable_lowering() -> None:
    program = parse_program("BEGIN { print foo(1) }")

    with pytest.raises(RuntimeError, match="unsupported numeric expression in runtime-backed backend"):
        jit.lower_to_llvm_ir(program)
