# P3 mixed-program execution tests.
# These cases verify the current `BEGIN` / record / `END` execution subset and
# keep the remaining mixed-program gaps visible.

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


def test_inline_mixed_begin_record_end_executes_for_supported_fields() -> None:
    result = run_quawk(
        'BEGIN { print "start" } { print $1 } END { print "done" }',
        stdin="alpha beta\ngamma delta\n",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nalpha\ngamma\ndone\n"
    assert result.stderr == ""


def test_file_based_mixed_begin_record_end_executes_for_supported_fields() -> None:
    program_path = ROOT / "tests" / "corpus" / "mixed_begin_record_end_first_field" / "program.awk"
    input_path = ROOT / "tests" / "corpus" / "mixed_begin_record_end_first_field" / "input.txt"
    result = run_quawk("-f", str(program_path), str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nalpha\ngamma\ndone\n"
    assert result.stderr == ""


def test_inline_mixed_begin_record_end_executes() -> None:
    result = run_quawk(
        'BEGIN { print "start" } { print $2 } END { print "done" }',
        stdin="alpha beta\ngamma delta\n",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nbeta\ndelta\ndone\n"
    assert result.stderr == ""


def test_file_based_mixed_begin_record_end_executes() -> None:
    program_path = ROOT / "tests" / "corpus" / "mixed_begin_record_end" / "program.awk"
    input_path = ROOT / "tests" / "corpus" / "mixed_begin_record_end" / "input.txt"
    result = run_quawk("-f", str(program_path), str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nbeta\ndelta\ndone\n"
    assert result.stderr == ""


def test_mixed_begin_record_end_executes_with_empty_input() -> None:
    result = run_quawk('BEGIN { print "start" } { print $2 } END { print "done" }', stdin="")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\ndone\n"
    assert result.stderr == ""


def test_mixed_begin_record_end_honors_custom_field_separator() -> None:
    input_path = ROOT / "tests" / "fixtures" / "p2" / "records_colon.txt"
    result = run_quawk(
        "-F:",
        'BEGIN { print "start" } { print $2 } END { print "done" }',
        str(input_path),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nbeta\ndelta\ndone\n"
    assert result.stderr == ""
