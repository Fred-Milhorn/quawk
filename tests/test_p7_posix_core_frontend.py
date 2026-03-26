# P7 POSIX-core frontend baselines.
# These cases pin the remaining POSIX-core parser and semantic surface before
# the lexer/parser/semantic implementation lands.

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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


def test_expr_pattern_without_action_parses() -> None:
    result = run_quawk("--parse", "1 < 2")

    assert result.returncode == 0, result.stderr
    assert "ExprPattern" in result.stdout
    assert result.stderr == ""


def test_range_pattern_parses() -> None:
    result = run_quawk("--parse", "/start/,/stop/ { print $0 }")

    assert result.returncode == 0, result.stderr
    assert "RangePattern" in result.stdout
    assert result.stderr == ""


def test_if_else_statement_parses() -> None:
    result = run_quawk("--parse", "BEGIN { if (1 < 2) print 1; else print 2 }")

    assert result.returncode == 0, result.stderr
    assert "IfStmt" in result.stdout
    assert "Else" in result.stdout
    assert result.stderr == ""


def test_do_while_statement_parses() -> None:
    result = run_quawk("--parse", "BEGIN { x = 0; do { x = x + 1 } while (x < 3) }")

    assert result.returncode == 0, result.stderr
    assert "DoWhileStmt" in result.stdout
    assert result.stderr == ""


def test_next_nextfile_and_exit_statements_parse() -> None:
    result = run_quawk("--parse", "{ next }\n{ nextfile }\nBEGIN { exit 1 }")

    assert result.returncode == 0, result.stderr
    assert "NextStmt" in result.stdout
    assert "NextFileStmt" in result.stdout
    assert "ExitStmt" in result.stdout
    assert result.stderr == ""


def test_printf_and_expression_statement_parse() -> None:
    result = run_quawk('--parse', 'BEGIN { printf "%s %g\\n", "x", 1; 1 + 2 }')

    assert result.returncode == 0, result.stderr
    assert "PrintfStmt" in result.stdout
    assert "ExprStmt" in result.stdout
    assert result.stderr == ""


def test_dynamic_field_expression_and_field_assignment_parse() -> None:
    result = run_quawk("--parse", "BEGIN { i = 1; print $i; $i = 2 }")

    assert result.returncode == 0, result.stderr
    assert "FieldExpr" in result.stdout
    assert "FieldLValue" in result.stdout
    assert result.stderr == ""


def test_multi_subscript_array_and_whole_array_delete_parse() -> None:
    result = run_quawk("--parse", "BEGIN { a[1, 2] = 3; delete a }")

    assert result.returncode == 0, result.stderr
    assert "ArrayLValue" in result.stdout
    assert "DeleteStmt" in result.stdout
    assert result.stderr == ""


def test_assignment_expression_and_compound_assignment_parse() -> None:
    result = run_quawk("--parse", "BEGIN { print (x = 1); x += 2 }")

    assert result.returncode == 0, result.stderr
    assert "AssignExpr" in result.stdout
    assert "AddAssign" in result.stdout
    assert result.stderr == ""


def test_conditional_logical_or_and_remaining_comparisons_parse() -> None:
    result = run_quawk("--parse", "BEGIN { print (1 ? 2 : 3) || (4 != 5) || (6 <= 7) || (8 > 9) || (10 >= 11) }")

    assert result.returncode == 0, result.stderr
    assert "ConditionalExpr" in result.stdout
    assert "LOGICAL_OR" in result.stdout
    assert "NOT_EQUAL" in result.stdout
    assert "LESS_EQUAL" in result.stdout
    assert "GREATER" in result.stdout
    assert "GREATER_EQUAL" in result.stdout
    assert result.stderr == ""


def test_match_in_and_concat_operators_parse() -> None:
    result = run_quawk("--parse", 'BEGIN { print (a ~ /x/); print (a !~ /y/); print (1 in a); print 1 "x" }')

    assert result.returncode == 0, result.stderr
    assert "MATCH" in result.stdout
    assert "NOT_MATCH" in result.stdout
    assert "IN" in result.stdout
    assert "CONCAT" in result.stdout
    assert result.stderr == ""


def test_remaining_arithmetic_unary_and_postfix_operators_parse() -> None:
    result = run_quawk("--parse", "BEGIN { print 8 - 3 * 2 / 1 % 4 ^ 2; print !-x; ++x; x++ }")

    assert result.returncode == 0, result.stderr
    assert "SUB" in result.stdout
    assert "MUL" in result.stdout
    assert "DIV" in result.stdout
    assert "MOD" in result.stdout
    assert "POW" in result.stdout
    assert "UnaryExpr" in result.stdout
    assert "PostfixExpr" in result.stdout
    assert result.stderr == ""


@pytest.mark.xfail(strict=True, reason="T-114 not implemented: next legality outside record actions")
def test_next_outside_record_action_reports_semantic_error() -> None:
    result = run_quawk("BEGIN { next }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:9: error: next is only valid in record actions\n"
        "BEGIN { next }\n"
        "        ^\n"
    )


@pytest.mark.xfail(strict=True, reason="T-114 not implemented: nextfile legality outside record actions")
def test_nextfile_outside_record_action_reports_semantic_error() -> None:
    result = run_quawk("END { nextfile }")

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:7: error: nextfile is only valid in record actions\n"
        "END { nextfile }\n"
        "      ^\n"
    )
