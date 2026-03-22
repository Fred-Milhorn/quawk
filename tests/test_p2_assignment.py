# P2 assignment execution tests.
# These cases verify the scalar-variable increment through the full
# CLI-to-LLVM execution path.

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


def test_inline_begin_assignment_executes() -> None:
    result = run_quawk("BEGIN { x = 1; print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""


def test_inline_begin_assignment_with_addition_executes() -> None:
    result = run_quawk("BEGIN { x = 1 + 2; print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""


def test_file_based_begin_assignment_executes() -> None:
    program_path = ROOT / "tests" / "fixtures" / "p2" / "begin_assign_print.awk"
    result = run_quawk("-f", str(program_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""
