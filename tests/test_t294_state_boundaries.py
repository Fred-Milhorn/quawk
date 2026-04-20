from __future__ import annotations

import subprocess
from pathlib import Path

from quawk import jit
from quawk.lexer import lex
from quawk.local_scalar_residency import classify_local_numeric_scalar_residency
from quawk.normalization import normalize_program_for_lowering
from quawk.ast import Program
from quawk.parser import parse
from quawk.source import ProgramSource
from quawk.type_inference import LatticeType, infer_variable_types

ROOT = Path(__file__).resolve().parent.parent

SUB_TARGET_PROGRAM = 'BEGIN { x = 1; print sub(/1/, "a", x); print x }'
CROSS_PHASE_COPY_PROGRAM = "BEGIN { x = 7; y = x } END { print y }"


def run_quawk(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def extract_function_body(llvm_ir: str, function_name: str) -> str:
    marker = f"define void @{function_name}(ptr %rt, ptr %state) {{"
    start = llvm_ir.index(marker)
    end = llvm_ir.index("\n}\n", start) + 3
    return llvm_ir[start:end]


def test_t294_sub_target_name_becomes_mixed_and_stays_out_of_local_numeric_storage() -> None:
    program = parse_program(SUB_TARGET_PROGRAM)
    type_info = infer_variable_types(program)
    residency = classify_local_numeric_scalar_residency(
        program,
        normalize_program_for_lowering(program),
        type_info,
    )
    llvm_ir = jit.lower_to_llvm_ir(program)
    begin_ir = extract_function_body(llvm_ir, "quawk_begin")

    assert type_info["x"] is LatticeType.MIXED
    assert residency.begin_local_numeric_names == frozenset()
    assert "%localvar.x." not in begin_ir
    assert "@qk_substitute(" in begin_ir


def test_t294_sub_target_runtime_value_remains_visible_after_substitution() -> None:
    result = run_quawk(SUB_TARGET_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\na\n"
    assert result.stderr == ""


def test_t294_cross_phase_copy_uses_numeric_value_from_promoted_local_source() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(CROSS_PHASE_COPY_PROGRAM))
    begin_ir = extract_function_body(llvm_ir, "quawk_begin")

    assert "%localvar.x." in begin_ir
    assert "%varptr.y." in begin_ir
    assert "@qk_scalar_copy(" not in begin_ir
    assert "load double, ptr %localvar.x." in begin_ir


def test_t294_cross_phase_copy_executes_with_state_backed_target_value() -> None:
    result = run_quawk(CROSS_PHASE_COPY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "7\n"
    assert result.stderr == ""
