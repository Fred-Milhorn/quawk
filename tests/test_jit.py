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


def test_execute_with_inputs_resolves_later_fields(capsys, monkeypatch) -> None:
    program = parse_program('{ print $3 }')

    monkeypatch.setattr("sys.stdin", io.StringIO("alpha beta gamma\ndelta epsilon zeta\n"))

    assert jit.execute_with_inputs(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "gamma\nzeta\n"
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
    assert 'c"\\73\\74\\61\\72\\74\\00"' in llvm_ir
    assert 'c"\\62\\65\\74\\61\\00"' in llvm_ir
    assert 'c"\\64\\65\\6C\\74\\61\\00"' in llvm_ir
    assert 'c"\\64\\6F\\6E\\65\\00"' in llvm_ir
    assert llvm_ir.count("call i32 @puts(") == 4


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
    assert 'c"\\66\\6F\\6F\\00"' in llvm_ir
    assert 'c"\\66\\6F\\6F\\64\\00"' in llvm_ir
    assert 'c"\\62\\61\\72\\00"' not in llvm_ir
    assert llvm_ir.count("call i32 @puts(") == 2
