# P6 associative-array execution baselines.
# These cases specify the first array read/write deliverable through the public
# CLI path before the implementation lands.

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


@pytest.mark.xfail(strict=True, reason="T-108 not implemented: associative arrays and indexed access")
def test_inline_begin_array_assignment_and_read_executes() -> None:
    result = run_quawk('BEGIN { a["x"] = 1; print a["x"] }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""


@pytest.mark.xfail(strict=True, reason="T-108 not implemented: associative arrays and indexed access")
def test_file_based_begin_array_assignment_and_read_executes() -> None:
    program_path = ROOT / "tests" / "fixtures" / "p6" / "begin_array_assign_print.awk"
    result = run_quawk("-f", str(program_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""
