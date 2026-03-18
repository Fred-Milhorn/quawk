from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.xfail(
    reason="P1 minimal execution slice is not implemented yet", strict=True
)
def test_inline_begin_print_literal_executes() -> None:
    result = run_quawk('BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello\n"
    assert result.stderr == ""


@pytest.mark.xfail(
    reason="P1 minimal execution slice is not implemented yet", strict=True
)
def test_file_based_begin_print_literal_executes() -> None:
    program_path = ROOT / "tests" / "fixtures" / "p1" / "begin_print_literal.awk"
    result = run_quawk("-f", str(program_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello\n"
    assert result.stderr == ""
