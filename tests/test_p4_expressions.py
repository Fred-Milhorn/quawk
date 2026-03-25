# P4 broader-expression execution tests.
# These cases pin the next expression-support deliverable at the public CLI
# layer before parser/runtime/lowering work is added.

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


def test_inline_equality_expression_executes() -> None:
    result = run_quawk("BEGIN { print 1 == 1 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""


def test_inline_parenthesized_logical_and_expression_executes() -> None:
    result = run_quawk("BEGIN { print (1 < 2) && (2 < 3) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n"
    assert result.stderr == ""
