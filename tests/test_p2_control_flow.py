# P2 control-flow execution tests.
# These cases verify comparisons and control flow through the full
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


def test_inline_begin_if_comparison_executes() -> None:
    result = run_quawk("BEGIN { if (1 < 2) print 3 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""


def test_inline_begin_while_loop_executes() -> None:
    result = run_quawk("BEGIN { x = 0; while (x < 3) { print x; x = x + 1 } }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n2\n"
    assert result.stderr == ""


def test_file_based_begin_while_loop_executes() -> None:
    program_path = ROOT / "tests" / "fixtures" / "p2" / "begin_while_print.awk"
    result = run_quawk("-f", str(program_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n2\n"
    assert result.stderr == ""
