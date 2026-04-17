from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("source_text", "expected_stdout", "ir_markers", "asm_markers"),
    [
        (
            "BEGIN { print $1 }",
            "\n",
            ("define i32 @quawk_main()", "@qk_get_field_inline", "@qk_print_string_fragment"),
            ("quawk_main", "quawk_begin", "qk_get_field_inline"),
        ),
        (
            "BEGIN { x = !1; print x }",
            "0\n",
            ("define i32 @quawk_main()", "select i1 %truthy.", "@qk_print_number_fragment"),
            ("quawk_main", "quawk_begin", "qk_print_number_fragment"),
        ),
        (
            "BEGIN { x = ++y; print x }",
            "1\n",
            ("define i32 @quawk_main()", "@qk_scalar_get_number_inline", "@qk_scalar_set_number_inline"),
            ("quawk_main", "quawk_begin", "qk_scalar_get_number_inline", "qk_scalar_set_number_inline"),
        ),
        (
            "BEGIN { x = 1; x += 2; print x }",
            "3\n",
            ("define i32 @quawk_main()", "fadd double %state.current.", "@qk_print_number_fragment"),
            ("quawk_main", "quawk_begin", "qk_print_number_fragment"),
        ),
        (
            'BEGIN { if ("a" "b") x = 1; print x }',
            "1\n",
            ("define i32 @quawk_main()", "@qk_concat", "@qk_print_number_fragment"),
            ("quawk_main", "quawk_begin", "qk_concat"),
        ),
        (
            'BEGIN { x = a["k"]; print x }',
            "\n",
            ("define i32 @quawk_main()", "@qk_array_get", "@qk_print_string_fragment"),
            ("quawk_main", "quawk_begin", "qk_array_get"),
        ),
    ],
)
def test_t288_representative_programs_have_execution_and_inspection_parity(
    source_text: str,
    expected_stdout: str,
    ir_markers: tuple[str, ...],
    asm_markers: tuple[str, ...],
) -> None:
    execution = run_quawk(source_text)

    assert execution.returncode == 0, execution.stderr
    assert execution.stdout == expected_stdout
    assert execution.stderr == ""

    llvm_ir = run_quawk("--ir", source_text)

    assert llvm_ir.returncode == 0, llvm_ir.stderr
    for marker in ir_markers:
        assert marker in llvm_ir.stdout
    assert llvm_ir.stderr == ""

    assembly = run_quawk("--asm", source_text)

    assert assembly.returncode == 0, assembly.stderr
    for marker in asm_markers:
        assert marker in assembly.stdout
    assert assembly.stderr == ""
