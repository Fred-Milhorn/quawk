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
