# Input-aware execution tests for mixed programs.
# These cases pin the record-sensitive execution path below the CLI layer,
# including the LLVM-backed lowering added for the P3 mixed-program step.

from __future__ import annotations

import io

from quawk import jit
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource


def parse_program(source_text: str) -> Program:
    """Parse inline AWK source into the frontend program model."""
    return parse(lex(ProgramSource.from_inline(source_text)))


def test_execute_with_inputs_sequences_begin_record_and_end(capsys, monkeypatch) -> None:
    program = parse_program('BEGIN { print "start" }\n{ print $1 }\nEND { print "done" }')

    monkeypatch.setattr("sys.stdin", io.StringIO("alpha beta\ngamma delta\n"))

    assert jit.execute_with_inputs(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "start\nalpha\ngamma\ndone\n"
    assert captured.err == ""


def test_execute_with_inputs_runs_begin_and_end_without_input(capsys) -> None:
    program = parse_program('BEGIN { x = 1 + 2; print x }\nEND { print "done" }')

    assert jit.execute_with_inputs(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "3\ndone\n"
    assert captured.err == ""


def test_execute_host_runtime_prints_equality_result(capsys) -> None:
    program = parse_program("BEGIN { print 1 == 1 }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "1\n"
    assert captured.err == ""


def test_execute_host_runtime_prints_parenthesized_logical_and_result(capsys) -> None:
    program = parse_program("BEGIN { print (1 < 2) && (2 < 3) }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "1\n"
    assert captured.err == ""


def test_execute_host_runtime_short_circuits_logical_and(capsys) -> None:
    program = parse_program("BEGIN { print (1 == 2) && missing }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "0\n"
    assert captured.err == ""


def test_execute_host_runtime_calls_user_defined_function(capsys) -> None:
    program = parse_program("function f(x) { return x + 1 }\nBEGIN { print f(2) }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "3\n"
    assert captured.err == ""


def test_execute_host_runtime_keeps_function_parameters_local(capsys) -> None:
    program = parse_program("function f(x) { x = x + 1; return x }\nBEGIN { x = 10; print f(2); print x }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "3\n10\n"
    assert captured.err == ""


def test_execute_host_runtime_defaults_unset_globals_to_zero(capsys) -> None:
    program = parse_program("function f(x) { return x }\nBEGIN { print y }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "0\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_array_assignment_and_indexed_read(capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; print a["x"]; print a["missing"] }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "1\n0\n"
    assert captured.err == ""


def test_execute_with_inputs_resolves_later_fields(capsys, monkeypatch) -> None:
    program = parse_program('{ print $3 }')

    monkeypatch.setattr("sys.stdin", io.StringIO("alpha beta gamma\ndelta epsilon zeta\n"))

    assert jit.execute_with_inputs(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "gamma\nzeta\n"
    assert captured.err == ""


def test_execute_routes_array_programs_through_host_runtime(monkeypatch, capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; print a["x"] }')

    def fail_lower_to_llvm_ir(*args: object, **kwargs: object) -> str:
        raise AssertionError("array programs should not lower through the LLVM backend yet")

    monkeypatch.setattr(jit, "lower_to_llvm_ir", fail_lower_to_llvm_ir)

    assert jit.execute(program) == 0
    captured = capsys.readouterr()
    assert captured.out == "1\n"
    assert captured.err == ""


def test_execute_with_inputs_lowers_mixed_programs_to_llvm(monkeypatch) -> None:
    program = parse_program('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')
    captured_ir: dict[str, str] = {}

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)
    monkeypatch.setattr("sys.stdin", io.StringIO("alpha beta\ngamma delta\n"))

    assert jit.execute_with_inputs(program, [], None) == 0
    llvm_ir = captured_ir["module"]
    assert "define i32 @quawk_main()" in llvm_ir
    assert "define void @quawk_begin(ptr %rt, ptr %state)" in llvm_ir
    assert "define void @quawk_record(ptr %rt, ptr %state)" in llvm_ir
    assert "define void @quawk_end(ptr %rt, ptr %state)" in llvm_ir
    assert "@qk_runtime_create" in llvm_ir
    assert "@qk_next_record" in llvm_ir
    assert "@qk_get_field" in llvm_ir
    assert 'c"\\62\\65\\74\\61\\00"' not in llvm_ir
    assert 'c"\\64\\65\\6C\\74\\61\\00"' not in llvm_ir


def test_execute_host_runtime_filters_records_with_regex_pattern(capsys, monkeypatch) -> None:
    program = parse_program("/foo/ { print $0 }")

    monkeypatch.setattr("sys.stdin", io.StringIO("foo\nbar\nfood\n"))

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "foo\nfood\n"
    assert captured.err == ""


def test_execute_host_runtime_sequences_begin_regex_and_end(capsys, monkeypatch) -> None:
    program = parse_program('BEGIN { print "start" }\n/foo/ { print $0 }\nEND { print "done" }')

    monkeypatch.setattr("sys.stdin", io.StringIO("foo\nbar\nfood\n"))

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "start\nfoo\nfood\ndone\n"
    assert captured.err == ""


def test_execute_with_inputs_lowers_regex_filter_program_to_llvm(monkeypatch) -> None:
    program = parse_program("/foo/ { print $0 }")
    captured_ir: dict[str, str] = {}

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)
    monkeypatch.setattr("sys.stdin", io.StringIO("foo\nbar\nfood\n"))

    assert jit.execute_with_inputs(program, [], None) == 0
    llvm_ir = captured_ir["module"]
    assert "define i32 @quawk_main()" in llvm_ir
    assert "define void @quawk_record(ptr %rt, ptr %state)" in llvm_ir
    assert "@qk_runtime_create" in llvm_ir
    assert "@qk_next_record" in llvm_ir
    assert "@qk_regex_match_current_record" in llvm_ir
    assert 'c"\\62\\61\\72\\00"' not in llvm_ir
    assert 'c"\\66\\6F\\6F\\64\\00"' not in llvm_ir


def test_lower_to_llvm_ir_supports_reusable_mixed_program_lowering() -> None:
    program = parse_program('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')

    llvm_ir = jit.lower_to_llvm_ir(program)
    assert "define void @quawk_begin(" in llvm_ir
    assert "define void @quawk_record(" in llvm_ir
    assert "define void @quawk_end(" in llvm_ir
    assert "@qk_get_field" in llvm_ir


def test_lower_to_llvm_ir_supports_reusable_regex_program_lowering() -> None:
    program = parse_program("/foo/ { print $0 }")

    llvm_ir = jit.lower_to_llvm_ir(program)
    assert "define void @quawk_record(" in llvm_ir
    assert "@qk_regex_match_current_record" in llvm_ir


def test_execute_with_inputs_routes_mixed_programs_through_reusable_lowering(monkeypatch) -> None:
    program = parse_program('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')
    captured_ir: dict[str, str] = {}

    def fail_collect_records(*args: object, **kwargs: object) -> list[jit.RecordContext]:
        raise AssertionError("public execution should not collect all records before lowering")

    def fail_input_specialized_lowering(*args: object, **kwargs: object) -> str:
        raise AssertionError("public execution should not use input-specialized lowering")

    def fake_lower_to_llvm_ir(lowered_program: Program) -> str:
        assert lowered_program is program
        return "; reusable mixed module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; reusable mixed module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked mixed module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "collect_record_contexts", fail_collect_records)
    monkeypatch.setattr(jit, "lower_input_aware_program_to_llvm_ir", fail_input_specialized_lowering)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked mixed module"


def test_execute_with_inputs_routes_regex_programs_through_reusable_lowering(monkeypatch) -> None:
    program = parse_program("/foo/ { print $0 }")
    captured_ir: dict[str, str] = {}

    def fail_collect_records(*args: object, **kwargs: object) -> list[jit.RecordContext]:
        raise AssertionError("public execution should not collect all records before lowering")

    def fail_input_specialized_lowering(*args: object, **kwargs: object) -> str:
        raise AssertionError("public execution should not use input-specialized lowering")

    def fake_lower_to_llvm_ir(lowered_program: Program) -> str:
        assert lowered_program is program
        return "; reusable regex module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; reusable regex module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked regex module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "collect_record_contexts", fail_collect_records)
    monkeypatch.setattr(jit, "lower_input_aware_program_to_llvm_ir", fail_input_specialized_lowering)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked regex module"
