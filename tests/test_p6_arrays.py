# P6 associative-array execution baselines.
# These cases specify the first array read/write deliverable through the public
# CLI path before the implementation lands.

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_inline_begin_array_assignment_and_read_executes() -> None:
    result = run_quawk('BEGIN { a["x"] = 1; print a["x"] }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""


def test_file_based_begin_array_assignment_and_read_executes() -> None:
    program_path = ROOT / "tests" / "fixtures" / "p6" / "begin_array_assign_print.awk"
    result = run_quawk("-f", str(program_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""


def test_inline_begin_array_missing_index_defaults_to_zero() -> None:
    result = run_quawk('BEGIN { print a["missing"] }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n"
    assert result.stderr == ""


def test_inline_begin_array_delete_removes_indexed_value() -> None:
    result = run_quawk('BEGIN { a["x"] = 1; delete a["x"]; print a["x"] }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n"
    assert result.stderr == ""


def test_inline_begin_classic_for_loop_executes() -> None:
    result = run_quawk("BEGIN { for (i = 0; i < 3; i = i + 1) print i }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n2\n"
    assert result.stderr == ""


def test_inline_begin_for_in_loop_iterates_array_keys() -> None:
    result = run_quawk('BEGIN { a["x"] = 1; for (k in a) print k }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "x\n"
    assert result.stderr == ""
