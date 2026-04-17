from __future__ import annotations

from pathlib import Path

import pytest

from quawk import jit
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def test_t287_lowering_reports_compiled_reusable_backend_boundary_for_unsupported_programs() -> None:
    program = parse_program("BEGIN { delete x }")

    with pytest.raises(RuntimeError, match="the compiled reusable backend does not yet support this program"):
        jit.lower_to_llvm_ir(program)


def test_t287_public_execution_reports_compiled_reusable_backend_boundary_for_unsupported_programs() -> None:
    program = parse_program("BEGIN { delete x }")

    with pytest.raises(RuntimeError, match="public execution only supports programs in the compiled reusable backend subset"):
        jit.ensure_public_execution_supported(program)


def test_t287_runtime_gap_diagnostics_remain_specific_to_reusable_lowering() -> None:
    program = parse_program("BEGIN { print foo(1) }")

    with pytest.raises(RuntimeError, match="unsupported numeric expression in runtime-backed backend"):
        jit.lower_to_llvm_ir(program)


def test_t287_jit_diagnostics_no_longer_reference_the_retired_direct_backend() -> None:
    jit_text = (ROOT / "src" / "quawk" / "jit.py").read_text(encoding="utf-8")

    assert "direct LLVM-backed backend" not in jit_text
    assert "host-runtime-only operations are not supported by the LLVM-backed backend" not in jit_text
