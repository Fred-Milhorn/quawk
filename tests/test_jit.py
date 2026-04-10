# Input-aware execution tests for mixed programs.
# These cases pin the record-sensitive execution path below the CLI layer,
# including the LLVM-backed lowering added for the P3 mixed-program step.

from __future__ import annotations

import io
from typing import Callable

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


def test_execute_routes_array_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { a["x"] = 1; print a["x"] }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("array programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; array backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; array backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked array backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked array backend module"


def test_execute_routes_supported_function_programs_through_backend(monkeypatch) -> None:
    program = parse_program("function f(x) { return x + 1 }\nBEGIN { print f(2) }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported function programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; function backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; function backend module"


def test_execute_routes_supported_scalar_string_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { x = "12"; print x + 1; print x "a" }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported scalar-string programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; scalar-string backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; scalar-string backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked scalar-string backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked scalar-string backend module"


def test_execute_routes_supported_print_surface_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { OFS = ","; ORS = "!"; print 1, 2; print }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported print-surface programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; print backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; print backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked print backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked print backend module"


def test_execute_routes_supported_formatting_variable_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { OFMT = "%.2f"; CONVFMT = "%.3f"; print 1.2345; print 1.2345 "" }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported formatting-variable programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; formatting backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; formatting backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked formatting backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked formatting backend module"


def test_execute_with_inputs_routes_supported_input_separator_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { FS = ":"; RS = ";" } { print $1 }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported input-separator programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; separators backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; separators backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked separators backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked separators backend module"


def test_execute_with_inputs_routes_supported_bare_length_programs_through_backend(monkeypatch) -> None:
    program = parse_program("{ print length, $0 }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported bare-length programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; bare-length backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; bare-length backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked bare-length backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked bare-length backend module"


def test_execute_routes_supported_output_redirect_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { print "x" > "out"; printf "%s", "y" >> "out"; close("out") }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported output-redirect programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; redirect backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; redirect backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked redirect backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked redirect backend module"


def test_execute_routes_parenthesized_printf_with_substr_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { x = "A"; printf("%-39s\\n", substr(x, 1, 39)) }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported parenthesized printf programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; printf backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; printf backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked printf backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked printf backend module"


def test_execute_routes_supported_string_and_regex_builtin_programs_through_backend(monkeypatch) -> None:
    program = parse_program(
        'BEGIN { x = "bananas"; print index(x, "na"); print match(x, /ana/); '
        'print sub(/ana/, "[&]", x); print sprintf("%s:%c", tolower("AbC"), 66); print toupper("ab") }'
    )
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported string and regex builtin programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; string-regex builtin backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; string-regex builtin backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked string-regex builtin backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked string-regex builtin backend module"


def test_execute_routes_supported_numeric_and_system_builtin_programs_through_backend(monkeypatch) -> None:
    program = parse_program(
        'BEGIN { print int(3.9); print atan2(0, -1); print cos(0); print srand(1); print rand(); print system("exit 7") }'
    )
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported numeric and system builtin programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; numeric-system builtin backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; numeric-system builtin backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked numeric-system builtin backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked numeric-system builtin backend module"


def test_execute_with_inputs_routes_supported_nextfile_programs_through_backend(monkeypatch) -> None:
    program = parse_program('/stop/ { nextfile }\n{ print $0 }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported nextfile programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; nextfile backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; nextfile backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked nextfile backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked nextfile backend module"


def test_execute_with_inputs_routes_supported_exit_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { print "before"; exit 7 }\nEND { print "done" }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported exit programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; exit backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; exit backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked exit backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 7

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 7
    assert captured_ir["module"] == "; linked exit backend module"


def test_execute_routes_supported_do_while_programs_through_backend(monkeypatch) -> None:
    program = parse_program("BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported do-while programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; dowhile backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; dowhile backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked dowhile backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked dowhile backend module"


def test_execute_with_inputs_routes_supported_next_programs_through_backend(monkeypatch) -> None:
    program = parse_program('/skip/ { next }\n{ print $0 }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported next programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; next backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; next backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked next backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked next backend module"


def test_execute_with_inputs_routes_supported_numeric_concat_programs_through_backend(monkeypatch) -> None:
    program = parse_program('{ print NR " " 10 / NR }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("numeric concat record programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; numeric concat backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; numeric concat backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked numeric concat backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked numeric concat backend module"


def test_execute_with_inputs_routes_supported_record_rebuild_programs_through_backend(monkeypatch) -> None:
    program = parse_program('{$0 = $2; print; print NF, $0; print $1}')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("record rebuild programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; record rebuild backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; record rebuild backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked record rebuild backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked record rebuild backend module"


def test_execute_with_inputs_routes_supported_nf_rebuild_programs_through_backend(monkeypatch) -> None:
    program = parse_program('{ OFS = "|"; NF = 2; print; $5 = "five"; print }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("NF rebuild programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; nf rebuild backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; nf rebuild backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked nf rebuild backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked nf rebuild backend module"


def test_execute_with_inputs_routes_supported_expression_pattern_programs_through_backend(monkeypatch) -> None:
    program = parse_program("1 { print $0 }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported expression-pattern programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; expr-pattern backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; expr-pattern backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked expr-pattern backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked expr-pattern backend module"


def test_execute_with_inputs_routes_comparison_expression_patterns_through_backend(monkeypatch) -> None:
    program = parse_program('$2 == "Asia" { print $1 }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("comparison expression-pattern programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; comparison expr-pattern backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; comparison expr-pattern backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked comparison expr-pattern backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked comparison expr-pattern backend module"


def test_execute_with_inputs_routes_supported_default_print_expression_patterns_through_backend(monkeypatch) -> None:
    program = parse_program("1")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("supported default-print expression patterns should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; default-print backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; default-print backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked default-print backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute_with_inputs(program, [], None) == 0
    assert captured_ir["module"] == "; linked default-print backend module"


def test_execute_routes_for_loop_programs_through_backend(monkeypatch) -> None:
    program = parse_program("BEGIN { for (i = 0; i < 2; i = i + 1) print i }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("for-loop programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; for backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; for backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked for backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked for backend module"


def test_execute_routes_builtin_only_programs_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { print length("abc") }')
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("builtin-only programs should not stay on the host runtime now")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables is None
        return "; builtin backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; builtin backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        return "; linked builtin backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    assert captured_ir["module"] == "; linked builtin backend module"


def test_execute_routes_string_v_preassignments_through_backend(monkeypatch) -> None:
    program = parse_program("BEGIN { print x }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("string -v programs without function definitions should not stay on the host runtime")

    def fake_lower_to_llvm_ir(lowered_program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
        assert lowered_program is program
        assert initial_variables == [("x", "hello")]
        return "; string-v backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; string-v backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables == [("x", "hello")]
        return "; linked string-v backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "link_reusable_execution_module", fake_link_reusable_execution_module)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program, [("x", "hello")]) == 0
    assert captured_ir["module"] == "; linked string-v backend module"


def test_execute_routes_representative_claimed_value_backend_subset_programs_through_backend(
    monkeypatch,
) -> None:
    cases = {
        "unset_scalar_print": parse_program("BEGIN { print x }"),
        "unset_scalar_assignment": parse_program("BEGIN { y = x; print y }"),
        "unset_scalar_mixed_views": parse_program("BEGIN { print x; print x + 1 }"),
        "plain_scalar_name_after_assignment": parse_program("BEGIN { x = 1; print x }"),
    }
    built: list[Program] = []

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("the representative claimed value rows should use the backend/runtime path now")

    def fake_build_public_execution_llvm_ir(
        program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert input_files == []
        assert field_separator is None
        assert initial_variables is None
        built.append(program)
        return f"; claimed value backend module {len(built)}"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        assert llvm_ir.startswith("; claimed value backend module ")
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "build_public_execution_llvm_ir", fake_build_public_execution_llvm_ir)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    for program in cases.values():
        assert jit.execute(program) == 0

    assert built == list(cases.values())


def test_execute_routes_remaining_string_v_plus_function_claimed_value_case_through_backend(
    monkeypatch,
) -> None:
    program = parse_program("function f(y) { return y + 1 }\nBEGIN { print x; print f(1) }")
    captured_ir: dict[str, str] = {}

    def fail_execute_host_runtime(*args: object, **kwargs: object) -> int:
        raise AssertionError("string -v plus supported function programs should not stay on the host runtime")

    def fake_lower_to_llvm_ir(
        lowered_program: Program,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert lowered_program is program
        assert initial_variables == [("x", "hello")]
        return "; string-v function backend module"

    def fake_link_reusable_execution_module(
        llvm_ir: str,
        linked_program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert llvm_ir == "; string-v function backend module"
        assert linked_program is program
        assert input_files == []
        assert field_separator is None
        assert initial_variables == [("x", "hello")]
        return "; linked string-v function backend module"

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)
    monkeypatch.setattr(jit, "lower_to_llvm_ir", fake_lower_to_llvm_ir)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program, [("x", "hello")]) == 0
    assert captured_ir["module"] == "; string-v function backend module"


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


def test_execute_routes_p24_match_and_membership_programs_through_backend(monkeypatch) -> None:
    programs = {
        "match_operator": 'BEGIN { print ("abc" ~ /b/); print ("abc" !~ /d/) }',
        "in_operator": 'BEGIN { a["x"] = 1; print ("x" in a); print ("y" in a) }',
    }

    def fail_execute_host_runtime(
        program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> int:
        raise AssertionError("P24 programs should not fall back to the Python host runtime now")

    monkeypatch.setattr(jit, "execute_host_runtime", fail_execute_host_runtime)

    for name, source_text in programs.items():
        program = parse_program(source_text)
        captured_ir: dict[str, str] = {}

        def fake_execute_llvm_ir(llvm_ir: str) -> int:
            captured_ir["module"] = llvm_ir
            return 0

        monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

        assert jit.execute(program) == 0
        llvm_ir = captured_ir["module"]
        if name == "match_operator":
            assert "@qk_regex_match_text" in llvm_ir
        else:
            assert "@qk_array_contains" in llvm_ir


def test_execute_routes_p21_logical_or_program_through_backend(monkeypatch) -> None:
    program = parse_program("BEGIN { print (1 || 0) }")
    captured_ir: dict[str, str] = {}

    def fake_execute_host_runtime(
        program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> int:
        raise AssertionError("P21 logical-or programs should not fall back to the Python host runtime now")

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fake_execute_host_runtime)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    llvm_ir = captured_ir["module"]
    assert "phi i1" in llvm_ir
    assert "@qk_print_number" in llvm_ir or "@qk_print_string" in llvm_ir


def test_execute_routes_p21_comparison_program_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { x = "abc"; y = "10"; print (x > y); print (x != y) }')
    captured_ir: dict[str, str] = {}

    def fake_execute_host_runtime(
        program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> int:
        raise AssertionError("P21 comparison programs should not fall back to the Python host runtime now")

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fake_execute_host_runtime)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    llvm_ir = captured_ir["module"]
    assert "@qk_compare_values" in llvm_ir


def test_execute_routes_p22_arithmetic_program_through_backend(monkeypatch) -> None:
    program = parse_program("BEGIN { print (8 - 3); print (2 * 4); print (8 / 2); print (7 % 4); print (2 ^ 3) }")
    captured_ir: dict[str, str] = {}

    def fake_execute_host_runtime(
        program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> int:
        raise AssertionError("P22 arithmetic programs should not fall back to the Python host runtime now")

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fake_execute_host_runtime)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    llvm_ir = captured_ir["module"]
    assert "fsub double" in llvm_ir
    assert "fmul double" in llvm_ir
    assert "fdiv double" in llvm_ir
    assert "@llvm.trunc.f64" in llvm_ir
    assert "@llvm.pow.f64" in llvm_ir


def test_execute_routes_p23_ternary_program_through_backend(monkeypatch) -> None:
    program = parse_program('BEGIN { print (1 ? 2 : 3); print (0 ? "yes" : "no") }')
    captured_ir: dict[str, str] = {}

    def fake_execute_host_runtime(
        program: Program,
        input_files: list[str],
        field_separator: str | None,
        initial_variables: jit.InitialVariables | None = None,
    ) -> int:
        raise AssertionError("P23 ternary programs should not fall back to the Python host runtime now")

    def fake_execute_llvm_ir(llvm_ir: str) -> int:
        captured_ir["module"] = llvm_ir
        return 0

    monkeypatch.setattr(jit, "execute_host_runtime", fake_execute_host_runtime)
    monkeypatch.setattr(jit, "execute_llvm_ir", fake_execute_llvm_ir)

    assert jit.execute(program) == 0
    llvm_ir = captured_ir["module"]
    assert "select i1" in llvm_ir


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


def test_lower_to_llvm_ir_emits_numeric_comparison_fast_path_for_inferred_numeric_names() -> None:
    program = parse_program("{ x = 1; y = 2; print (x < y) }")

    llvm_ir = jit.lower_to_llvm_ir(program)
    assert "fcmp olt double" in llvm_ir
    assert "call i1 @qk_compare_values" not in llvm_ir


def test_lower_to_llvm_ir_emits_numeric_arithmetic_fast_path_ops() -> None:
    program = parse_program("{ x = 8; y = 2; print (x + y); print (x - y); print (x * y); print (x / y) }")

    llvm_ir = jit.lower_to_llvm_ir(program)
    assert "fadd double" in llvm_ir
    assert "fsub double" in llvm_ir
    assert "fmul double" in llvm_ir
    assert "fdiv double" in llvm_ir


def test_lower_to_llvm_ir_emits_string_concat_fast_path_without_capture_for_known_strings() -> None:
    program = parse_program('{ print ("foo" "bar") }')

    llvm_ir = jit.lower_to_llvm_ir(program)
    assert "call ptr @qk_concat" in llvm_ir
    assert "call ptr @qk_capture_string_arg" not in llvm_ir
    assert "call ptr @qk_format_number" not in llvm_ir


def test_lower_to_llvm_ir_uses_state_load_store_for_inferred_numeric_slot_names() -> None:
    program = parse_program("{ x = 1; y = x + 2; x += y; print x }")

    llvm_ir = jit.lower_to_llvm_ir(program)
    assert "getelementptr inbounds %quawk.state, ptr %state, i32 0, i32 0" in llvm_ir
    assert "getelementptr inbounds %quawk.state, ptr %state, i32 0, i32 1" in llvm_ir
    assert "call double @qk_slot_get_number" not in llvm_ir
    assert "call void @qk_slot_set_number" not in llvm_ir


def test_lower_to_llvm_ir_passes_inferred_type_info_to_direct_function_lowering(monkeypatch) -> None:
    program = parse_program("function f(x) { return x + 1 }\nBEGIN { print f(2) }")
    inferred_types = {"x": object()}
    captured: dict[str, object] = {}

    def fake_infer_variable_types(lowered_program: Program) -> dict[str, object]:
        assert lowered_program is program
        return inferred_types

    def fake_lower_direct_function_program_to_llvm_ir(
        lowered_program: Program,
        normalized_program: object,
        type_info: dict[str, object],
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert lowered_program is program
        assert type_info is inferred_types
        assert initial_variables is None
        captured["ok"] = True
        return "; direct function module"

    monkeypatch.setattr(jit, "infer_variable_types", fake_infer_variable_types)
    monkeypatch.setattr(jit, "lower_direct_function_program_to_llvm_ir", fake_lower_direct_function_program_to_llvm_ir)

    assert jit.lower_to_llvm_ir(program) == "; direct function module"
    assert captured["ok"] is True


def test_lower_to_llvm_ir_passes_inferred_type_info_to_reusable_lowering(monkeypatch) -> None:
    program = parse_program('BEGIN { a["x"] = 1; print a["x"] }')
    inferred_types = {"a": object()}
    captured: dict[str, object] = {}

    def fake_infer_variable_types(lowered_program: Program) -> dict[str, object]:
        assert lowered_program is program
        return inferred_types

    def fake_lower_reusable_program_to_llvm_ir(
        lowered_program: Program,
        normalized_program: object,
        type_info: dict[str, object],
    ) -> str:
        assert lowered_program is program
        assert type_info is inferred_types
        captured["ok"] = True
        return "; reusable module"

    monkeypatch.setattr(jit, "infer_variable_types", fake_infer_variable_types)
    monkeypatch.setattr(jit, "lower_reusable_program_to_llvm_ir", fake_lower_reusable_program_to_llvm_ir)

    assert jit.lower_to_llvm_ir(program) == "; reusable module"
    assert captured["ok"] is True


def test_execute_with_inputs_routes_mixed_programs_through_reusable_lowering(monkeypatch) -> None:
    program = parse_program('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')
    captured_ir: dict[str, str] = {}

    def fail_collect_records(*args: object, **kwargs: object) -> list[jit.RecordContext]:
        raise AssertionError("public execution should not collect all records before lowering")

    def fail_input_specialized_lowering(*args: object, **kwargs: object) -> str:
        raise AssertionError("public execution should not use input-specialized lowering")

    def fake_lower_to_llvm_ir(
        lowered_program: Program,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert lowered_program is program
        assert initial_variables is None
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

    def fake_lower_to_llvm_ir(
        lowered_program: Program,
        initial_variables: jit.InitialVariables | None = None,
    ) -> str:
        assert lowered_program is program
        assert initial_variables is None
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
