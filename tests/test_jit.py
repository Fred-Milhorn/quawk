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


def test_read_input_sources_decodes_non_utf8_files_with_surrogateescape(tmp_path) -> None:
    input_path = tmp_path / "latin1.txt"
    input_path.write_bytes(b"a\xffb c\n")

    assert jit.read_input_sources([str(input_path)]) == [(str(input_path), "a\udcffb c\n")]


def test_getline_input_stream_decodes_non_utf8_files_with_surrogateescape(tmp_path) -> None:
    input_path = tmp_path / "latin1.txt"
    input_path.write_bytes(b"a\xffb c\n")
    state = jit.RuntimeState()

    stream = jit.getline_input_stream(state, str(input_path))

    assert stream.content == "a\udcffb c\n"


def test_execute_host_runtime_prints_unset_globals_as_empty_strings(capsys) -> None:
    program = parse_program("function f(x) { return x }\nBEGIN { print y }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_array_assignment_and_indexed_read(capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; print a["x"]; print a["missing"] }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "1\n\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_array_delete(capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; delete a["x"]; print a["x"] }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "\n"
    assert captured.err == ""


def test_execute_host_runtime_coerces_string_scalars_in_arithmetic_and_concat(capsys) -> None:
    program = parse_program('BEGIN { x = "12"; print x + 1; print x "a" }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "13\n12a\n"
    assert captured.err == ""


def test_execute_host_runtime_uses_string_truthiness_and_string_comparison(capsys) -> None:
    program = parse_program('BEGIN { x = "0"; y = ""; print x && 1; print !y; z = "2"; print z < 10 }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "1\n1\n1\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_classic_for_loops(capsys) -> None:
    program = parse_program("BEGIN { for (i = 0; i < 3; i = i + 1) print i }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "0\n1\n2\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_classic_for_expression_lists(capsys) -> None:
    program = parse_program("BEGIN { for (i = 0, j = 5; i < 3; i++, --j) print i }")

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "0\n1\n2\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_for_in_loops(capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; for (k in a) print k }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "x\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_parenthesized_for_in_iterable(capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; for (k in (a)) print k }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "x\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_length_builtin_for_strings_and_arrays(capsys) -> None:
    program = parse_program('BEGIN { a["x"] = 1; a["y"] = 2; print length("hello"); print length(a) }')

    jit.execute_host_runtime(program, [], None)
    captured = capsys.readouterr()
    assert captured.out == "5\n2\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_split_and_substr_builtins(capsys) -> None:
    program = parse_program('BEGIN { n = split("a b", a); print n; print a[1]; print substr("hello", 2, 3) }')

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "2\na\nell\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_string_and_regex_builtins(capsys) -> None:
    program = parse_program(
        'BEGIN { x = "bananas"; print index(x, "na"); print match(x, /ana/); print RSTART; print RLENGTH; '
        'print sub(/ana/, "[&]", x); print x; print gsub(/a/, "A", x); print x; '
        'print sprintf("%s:%c", tolower("AbC"), 66); print toupper("ab") }'
    )

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "3\n2\n2\n3\n1\nb[ana]nas\n3\nb[AnA]nAs\nabc:B\nAB\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_numeric_and_system_builtins(capsys) -> None:
    program = parse_program(
        "BEGIN { print int(3.9); print atan2(0, -1); print cos(0); print sin(0); "
        'print srand(1); print rand(); print system("exit 7") }'
    )

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "3\n3.14159\n1\n0\n1\n0.51387\n7\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_string_v_preassignments(capsys) -> None:
    program = parse_program('BEGIN { print x; print x + 1 }')

    assert jit.execute_host_runtime(program, [], None, [("x", "12")]) == 0
    captured = capsys.readouterr()
    assert captured.out == "12\n13\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_getline_into_named_target(capsys, monkeypatch) -> None:
    program = parse_program('BEGIN { print getline x; print x }')

    monkeypatch.setattr("sys.stdin", io.StringIO("alpha\n"))

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "1\nalpha\n"
    assert captured.err == ""


def test_execute_host_runtime_updates_nr_fnr_and_nf(capsys, monkeypatch) -> None:
    program = parse_program("{ print NR; print FNR; print NF }")

    monkeypatch.setattr("sys.stdin", io.StringIO("a b\nc d\n"))

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "1\n1\n2\n2\n2\n2\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_do_while(capsys) -> None:
    program = parse_program("BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }")

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "0\n1\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_range_patterns_and_default_print(capsys, monkeypatch) -> None:
    program = parse_program("/start/,/stop/")

    monkeypatch.setattr("sys.stdin", io.StringIO("skip\nstart\nkeep\nstop\nafter\n"))

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "start\nkeep\nstop\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_next_and_nextfile(capsys, monkeypatch, tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a\nstop\nb\n", encoding="utf-8")
    second.write_text("c\n", encoding="utf-8")

    program = parse_program('/stop/ { nextfile }\n/skip/ { next }\n{ print $0 }')
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    assert jit.execute_host_runtime(program, [str(first), str(second)], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "a\nc\n"
    assert captured.err == ""


def test_execute_host_runtime_supports_printf_and_dynamic_field_assignment(capsys, monkeypatch) -> None:
    program = parse_program('{ i = 2; $i = 9; print $0 }\nBEGIN { printf "%s:%g", "x", 1 }')

    monkeypatch.setattr("sys.stdin", io.StringIO("1 2 3\n"))

    assert jit.execute_host_runtime(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "x:11 9 3\n"
    assert captured.err == ""


def test_execute_host_runtime_returns_exit_status_and_runs_end(capsys) -> None:
    program = parse_program('BEGIN { print "before"; exit 7 }\nEND { print "done" }')

    assert jit.execute_host_runtime(program, [], None) == 7
    captured = capsys.readouterr()
    assert captured.out == "before\ndone\n"
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
