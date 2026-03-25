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
        "<inline>:2:1: error: duplicate function definition: f\n"
        "function f(y) { return y }\n"
        "^\n"
    )


def test_return_outside_function_reports_semantic_error() -> None:
    result = run_quawk("BEGIN { return 1 }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:9: error: return is only valid inside a function\n"
        "BEGIN { return 1 }\n"
        "        ^\n"
    )


def test_assignment_to_function_name_reports_semantic_error() -> None:
    result = run_quawk("function f(x) { return x }\nBEGIN { f = 1 }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:2:9: error: cannot assign to function name: f\n"
        "BEGIN { f = 1 }\n"
        "        ^\n"
    )


def test_assignment_to_function_name_inside_function_reports_semantic_error() -> None:
    result = run_quawk("function f(x) { f = 1; return x }\nBEGIN { print f(2) }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:17: error: cannot assign to function name: f\n"
        "function f(x) { f = 1; return x }\n"
        "                ^\n"
    )
