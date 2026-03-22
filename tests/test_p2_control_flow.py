# P2 control-flow baseline tests.
# These cases establish the next capability increment before lexer/parser/runtime
# support lands. They remain xfail until comparisons and control flow execute
# through the CLI.

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
    strict=True,
    reason="T-072 baseline: BEGIN if-statement support is not implemented yet",
)
def test_inline_begin_if_comparison_executes() -> None:
    result = run_quawk("BEGIN { if (1 < 2) print 3 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""


@pytest.mark.xfail(
    strict=True,
    reason="T-072 baseline: BEGIN while-loop support is not implemented yet",
)
def test_inline_begin_while_loop_executes() -> None:
    result = run_quawk("BEGIN { x = 0; while (x < 3) { print x; x = x + 1 } }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n2\n"
    assert result.stderr == ""
