# P9 backend-parity and inspection baselines.
# These cases pin the representative backend-execution and inspection surface
# that should stop falling back to the host runtime once backend parity lands.

from __future__ import annotations

import subprocess
from pathlib import Path

from quawk import jit
from quawk.lexer import lex
from quawk.ast import Program
from quawk.parser import parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent

BEGIN_PARITY_PROGRAM = 'BEGIN { n = split("a b", a); print n; print a[1]; print substr("hello", 2, 3) }'
RECORD_PARITY_PROGRAM = '/start/,/stop/ { i = 2; $i = NR; printf "%s:%g\\n", FILENAME, NF; next }'
ARRAY_DELETE_PROGRAM = 'BEGIN { a["x"] = 1; delete a["x"]; print a["x"] }'
MULTI_SUBSCRIPT_ARRAY_PROGRAM = 'BEGIN { a[1, 2] = 3; print a[1, 2]; delete a[1, 2]; print length(a) }'
SIDE_EFFECTFUL_TERNARY_PROGRAM = "BEGIN { x = 0; print (1 ? ++x : (x = 99)); print x }"
FOR_LOOP_PROGRAM = "BEGIN { for (i = 0; i < 3; i = i + 1) print i }"
FOR_IN_PROGRAM = 'BEGIN { a["x"] = 1; for (k in a) print k }'
LENGTH_PROGRAM = 'BEGIN { a["x"] = 1; a["y"] = 2; print length("hello"); print length(a) }'
IMPERATIVE_FUNCTION_PROGRAM = "function climb(x) { y = x + 1; while (y < 3) y++; print y; return y }\nBEGIN { print climb(1) }"


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


def test_execute_routes_array_delete_programs_through_backend(monkeypatch) -> None:
    program = parse_program(ARRAY_DELETE_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("array delete programs should not stay on the host runtime once T-121 lands")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 array delete module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 array delete module"
        assert linked_program is program
        return "; p9 linked array delete module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; p9 linked array delete module"


def test_quawk_executes_multi_subscript_array_programs() -> None:
    result = run_quawk(MULTI_SUBSCRIPT_ARRAY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n0\n"
    assert result.stderr == ""


def test_quawk_supports_side_effectful_ternary_programs() -> None:
    result = run_quawk(SIDE_EFFECTFUL_TERNARY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1\n"
    assert result.stderr == ""


def test_quawk_ir_flag_lowers_side_effectful_ternary_program_with_branches() -> None:
    result = run_quawk("--ir", SIDE_EFFECTFUL_TERNARY_PROGRAM)

    assert result.returncode == 0, result.stderr
    assert "br i1" in result.stdout
    assert "select i1" not in result.stdout
    assert result.stderr == ""


def test_execute_routes_classic_for_programs_through_backend(monkeypatch) -> None:
    program = parse_program(FOR_LOOP_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("classic for programs should not stay on the host runtime once T-121 lands")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 for loop module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 for loop module"
        assert linked_program is program
        return "; p9 linked for loop module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; p9 linked for loop module"


def test_execute_routes_for_in_programs_through_backend(monkeypatch) -> None:
    program = parse_program(FOR_IN_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("for-in programs should not stay on the host runtime once T-121 lands")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 for in module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 for in module"
        assert linked_program is program
        return "; p9 linked for in module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; p9 linked for in module"


def test_execute_routes_imperative_function_programs_through_backend(monkeypatch) -> None:
    program = parse_program(IMPERATIVE_FUNCTION_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("imperative function programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 imperative function module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 imperative function module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; p9 linked imperative function module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; p9 linked imperative function module"


def test_execute_routes_length_programs_through_backend(monkeypatch) -> None:
    program = parse_program(LENGTH_PROGRAM)
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("length programs should not stay on the host runtime once T-121 lands")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; p9 length module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; p9 length module"
        assert linked_program is program
        return "; p9 linked length module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; p9 linked length module"
