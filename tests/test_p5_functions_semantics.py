# P5 function-semantics baselines.
# These tests pin the first user-defined function behavior and the initial
# legality checks before parser/semantic implementation lands.

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_function_definition_and_call_execute() -> None:
    result = run_quawk("function f(x) { return x + 1 } BEGIN { print f(2) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""


def test_multi_parameter_function_call_executes_with_argument_order_preserved() -> None:
    result = run_quawk("function add(x, y) { return x + y }\nBEGIN { print add(2, 3) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "5\n"
    assert result.stderr == ""


def test_multi_parameter_function_call_keeps_parameters_distinct_from_each_other_and_globals() -> None:
    result = run_quawk(
        "function pair_sum(x, y) { x = x + 1; return x + y }\nBEGIN { y = 100; print pair_sum(2, 3); print y }"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "6\n100\n"
    assert result.stderr == ""


def test_three_parameter_function_call_preserves_position() -> None:
    result = run_quawk("function pick(a, b, c) { return b }\nBEGIN { print pick(10, 20, 30) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "20\n"
    assert result.stderr == ""


def test_zero_argument_function_with_local_only_string_parameter_prints_the_local_value() -> None:
    result = run_quawk('function f(    id) { id = "abc"; print id }\nBEGIN { f() }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "abc\n"
    assert result.stderr == ""


def test_zero_argument_function_with_multiple_local_only_parameters_keeps_each_local_distinct() -> None:
    result = run_quawk(
        'function load(    id, state) { id = substr("USW00023183AZ", 1, 11); state = substr("USW00023183AZ", 12, 2); '
        'print id; print state }\nBEGIN { load() }'
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "USW00023183\nAZ\n"
    assert result.stderr == ""


def test_function_local_string_assignment_from_parameter_preserves_text() -> None:
    result = run_quawk('function copy(x,    tmp) { tmp = x; print tmp }\nBEGIN { copy("abc") }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "abc\n"
    assert result.stderr == ""


def test_function_local_string_assignment_expression_preserves_text() -> None:
    result = run_quawk('function copy(x,    tmp) { print (tmp = x) }\nBEGIN { copy("abc") }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "abc\n"
    assert result.stderr == ""


def test_user_defined_function_return_of_local_string_preserves_text_at_the_caller() -> None:
    result = run_quawk('function f(    id) { id = "abc"; return id }\nBEGIN { print f() }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "abc\n"
    assert result.stderr == ""


def test_function_return_preserves_simple_concatenated_string_text() -> None:
    result = run_quawk('function join3(a, b, c) { return a "-" b "-" c }\nBEGIN { print join3("A", "B", "C") }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "A-B-C\n"
    assert result.stderr == ""


def test_function_return_preserves_helper_built_padding_text() -> None:
    result = run_quawk(
        'function pad2(x) { if (x < 10) return "0" x; return x "" }\n'
        "BEGIN { print pad2(7); print pad2(12) }"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "07\n12\n"
    assert result.stderr == ""


def test_function_return_preserves_composite_date_and_report_fragment_text() -> None:
    result = run_quawk(
        'function pad2(x) { if (x < 10) return "0" x; return x "" }\n'
        'function date_string(y, m, d) { return y "-" pad2(m) "-" pad2(d) }\n'
        'function hottest_line(value, when, name) { return "Hottest day: " value " C  " when "  " name }\n'
        'BEGIN { print date_string(2023, 7, 19); print hottest_line("48.3", "2023-07-19", "PHOENIX AP") }'
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "2023-07-19\nHottest day: 48.3 C  2023-07-19  PHOENIX AP\n"
    assert result.stderr == ""


def test_duplicate_function_definitions_report_semantic_error() -> None:
    result = run_quawk("function f(x) { return x }\nfunction f(y) { return y }\nBEGIN { print f(1) }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:2:1: error[SEM001]: duplicate function definition: f\n"
        "function f(y) { return y }\n"
        "^\n"
    )


def test_duplicate_function_parameter_names_report_semantic_error() -> None:
    result = run_quawk("function f(x, x) { return x }\nBEGIN { print 1 }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:15: error[SEM003]: duplicate parameter name in function f: x\n"
        "function f(x, x) { return x }\n"
        "              ^\n"
    )


def test_function_parameter_name_conflicting_with_function_name_reports_semantic_error() -> None:
    result = run_quawk("function f(f) { return f }\nBEGIN { print 1 }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:12: error[SEM002]: function parameter conflicts with function name: f\n"
        "function f(f) { return f }\n"
        "           ^\n"
    )


def test_call_to_undefined_function_reports_semantic_error() -> None:
    result = run_quawk("BEGIN { print missing(1) }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:15: error[SEM010]: call to undefined function: missing\n"
        "BEGIN { print missing(1) }\n"
        "              ^\n"
    )


def test_return_outside_function_reports_semantic_error() -> None:
    result = run_quawk("BEGIN { return 1 }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:9: error[SEM009]: return is only valid inside a function\n"
        "BEGIN { return 1 }\n"
        "        ^\n"
    )


def test_assignment_to_function_name_reports_semantic_error() -> None:
    result = run_quawk("function f(x) { return x }\nBEGIN { f = 1 }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:2:9: error[SEM008]: cannot assign to function name: f\n"
        "BEGIN { f = 1 }\n"
        "        ^\n"
    )


def test_assignment_to_function_name_inside_function_reports_semantic_error() -> None:
    result = run_quawk("function f(x) { f = 1; return x }\nBEGIN { print f(2) }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:17: error[SEM008]: cannot assign to function name: f\n"
        "function f(x) { f = 1; return x }\n"
        "                ^\n"
    )


def test_break_outside_loop_reports_semantic_error() -> None:
    result = run_quawk("BEGIN { break }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:9: error[SEM004]: break is only valid inside a loop\n"
        "BEGIN { break }\n"
        "        ^\n"
    )


def test_continue_outside_loop_reports_semantic_error() -> None:
    result = run_quawk("BEGIN { continue }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:9: error[SEM005]: continue is only valid inside a loop\n"
        "BEGIN { continue }\n"
        "        ^\n"
    )


def test_builtin_arity_errors_report_semantic_error_code() -> None:
    result = run_quawk("BEGIN { print substr(\"abc\") }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:15: error[SEM011]: builtin substr expects two or three arguments\n"
        "BEGIN { print substr(\"abc\") }\n"
        "              ^\n"
    )


def test_numeric_and_system_builtin_arity_errors_report_semantic_error_code() -> None:
    result = run_quawk("BEGIN { print rand(1); print system(); print atan2(1); print srand(1, 2) }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:15: error[SEM011]: builtin rand expects zero arguments\n"
        "BEGIN { print rand(1); print system(); print atan2(1); print srand(1, 2) }\n"
        "              ^\n"
    )


def test_sub_requires_assignable_third_argument() -> None:
    result = run_quawk('BEGIN { print sub(/a/, "b", 1 + 2) }')

    assert result.returncode == 2
    assert result.stderr == (
        '<inline>:1:29: error[SEM011]: builtin sub requires an assignable third argument\n'
        'BEGIN { print sub(/a/, "b", 1 + 2) }\n'
        '                            ^\n'
    )


def test_break_and_continue_inside_loop_pass_semantic_checks() -> None:
    result = run_quawk("--parse", "BEGIN { while (1) { break; continue } }")

    assert result.returncode == 0, result.stderr
    assert "BreakStmt" in result.stdout
    assert "ContinueStmt" in result.stdout
    assert result.stderr == ""
