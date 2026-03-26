"""P10 grammar-alignment baselines for remaining doc-vs-implementation drift."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

XF_REASON = "T-123/T-124 grammar-alignment work not implemented"


def run_quawk(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.xfail(strict=True, reason=XF_REASON)
def test_for_loop_parses_expr_list_init_and_update() -> None:
    result = run_quawk(
        "--parse",
        "BEGIN { for (i = 0, j = 1; i < 3; i = i + 1, j = j + 1) print i }",
    )

    assert result.returncode == 0, result.stderr
    assert "ForStmt" in result.stdout
    assert result.stderr == ""


@pytest.mark.xfail(strict=True, reason=XF_REASON)
def test_for_loop_parses_non_assignment_expr_list_items() -> None:
    result = run_quawk(
        "--parse",
        "BEGIN { for (i++, --j; i < 3; i--, ++j) print i }",
    )

    assert result.returncode == 0, result.stderr
    assert "ForStmt" in result.stdout
    assert "PostfixExpr" in result.stdout
    assert "UnaryExpr" in result.stdout
    assert result.stderr == ""


@pytest.mark.xfail(strict=True, reason=XF_REASON)
def test_for_in_parses_general_iterable_expression() -> None:
    result = run_quawk(
        "--parse",
        "BEGIN { for (k in (a)) print k }",
    )

    assert result.returncode == 0, result.stderr
    assert "ForInStmt" in result.stdout
    assert result.stderr == ""


@pytest.mark.xfail(strict=True, reason=XF_REASON)
def test_public_execution_accepts_grammar_valid_general_for_in_expression() -> None:
    result = run_quawk(
        'BEGIN { a["x"] = 1; for (k in (a)) print k }',
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "x\n"
    assert result.stderr == ""
