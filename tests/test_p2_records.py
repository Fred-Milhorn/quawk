# P2 record-loop execution tests.
# These cases verify bare actions and simple field reads over input records.

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


def test_bare_action_prints_record_from_stdin() -> None:
    result = run_quawk("{ print $0 }", stdin="alpha\nbeta\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "alpha\nbeta\n"
    assert result.stderr == ""


def test_bare_action_preserves_full_record_text_with_spaces() -> None:
    result = run_quawk("{ print $0 }", stdin="alpha beta gamma\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "alpha beta gamma\n"
    assert result.stderr == ""


def test_bare_action_prints_first_field_from_stdin() -> None:
    result = run_quawk("{ print $1 }", stdin="alpha beta\ngamma delta\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "alpha\ngamma\n"
    assert result.stderr == ""


def test_bare_action_prints_second_field_from_stdin() -> None:
    result = run_quawk("{ print $2 }", stdin="alpha beta\ngamma delta\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "beta\ndelta\n"
    assert result.stderr == ""


def test_bare_action_prints_first_field_from_file() -> None:
    input_path = ROOT / "tests" / "fixtures" / "p2" / "records.txt"
    result = run_quawk("{ print $1 }", str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "alpha\ngamma\n"
    assert result.stderr == ""


def test_bare_action_uses_custom_field_separator() -> None:
    input_path = ROOT / "tests" / "fixtures" / "p2" / "records_colon.txt"
    result = run_quawk("-F:", "{ print $1 }", str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "alpha\ngamma\n"
    assert result.stderr == ""


def test_bare_action_uses_custom_field_separator_for_second_field() -> None:
    input_path = ROOT / "tests" / "fixtures" / "p2" / "records_colon.txt"
    result = run_quawk("-F:", "{ print $2 }", str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "beta\ndelta\n"
    assert result.stderr == ""
