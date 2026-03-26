# P9 backend-parity and inspection baselines.
# These cases pin the representative backend-execution and inspection surface
# that should stop falling back to the host runtime once backend parity lands.

from __future__ import annotations

import subprocess
from pathlib import Path

from quawk import jit
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent

BEGIN_PARITY_PROGRAM = 'BEGIN { n = split("a b", a); print n; print a[1]; print substr("hello", 2, 3) }'
RECORD_PARITY_PROGRAM = '/start/,/stop/ { i = 2; $i = NR; printf "%s:%g\\n", FILENAME, NF; next }'


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
    """Parse inline AWK source into the frontend program model."""
    return parse(lex(ProgramSource.from_inline(source_text)))


def test_execute_routes_completed_begin_programs_through_backend(monkeypatch) -> None:
    program = parse_program(BEGIN_PARITY_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("completed BEGIN programs should not stay on the host runtime once backend parity lands")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 begin backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 begin backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; p9 linked begin backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; p9 linked begin backend module"


def test_execute_with_inputs_routes_completed_record_programs_through_backend(monkeypatch) -> None:
    program = parse_program(RECORD_PARITY_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("completed record programs should not stay on the host runtime once backend parity lands")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 record backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 record backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; p9 linked record backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; p9 linked record backend module"


def test_quawk_ir_flag_prints_backend_ir_for_completed_begin_programs() -> None:
    result = run_quawk("--ir", BEGIN_PARITY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert "define i32 @quawk_main()" in result.stdout
    assert result.stderr == ""


def test_quawk_asm_flag_prints_backend_assembly_for_completed_begin_programs() -> None:
    result = run_quawk("--asm", BEGIN_PARITY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert "quawk_main" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_completed_record_programs() -> None:
    result = run_quawk("--ir", RECORD_PARITY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert "define i32 @quawk_main()" in result.stdout
    assert result.stderr == ""


def test_quawk_asm_flag_prints_backend_assembly_for_completed_record_programs() -> None:
    result = run_quawk("--asm", RECORD_PARITY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert "quawk_record" in result.stdout
    assert result.stderr == ""
