# P8 POSIX-core runtime and builtin baselines.
# These cases pin the remaining execution, builtin, and builtin-variable
# surface before the runtime implementation lands.

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


def test_range_pattern_without_action_prints_matching_records() -> None:
    result = run_quawk("/start/,/stop/", stdin="skip\nstart\nkeep\nstop\nafter\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nkeep\nstop\n"
    assert result.stderr == ""


def test_do_while_executes_body_before_testing_condition() -> None:
    result = run_quawk("BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n"
    assert result.stderr == ""


def test_next_skips_to_the_next_record() -> None:
    result = run_quawk('/skip/ { next } { print $0 }', stdin="skip\nkeep\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "keep\n"
    assert result.stderr == ""


def test_nextfile_skips_remaining_records_in_current_file(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a\nstop\nb\n", encoding="utf-8")
    second.write_text("c\n", encoding="utf-8")

    result = run_quawk('/stop/ { nextfile } { print $0 }', str(first), str(second))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "a\nc\n"
    assert result.stderr == ""


def test_exit_returns_requested_status_after_prior_output() -> None:
    result = run_quawk('BEGIN { print "before"; exit 7; print "after" }')

    assert result.returncode == 7
    assert result.stdout == "before\n"
    assert result.stderr == ""


def test_printf_does_not_append_an_implicit_newline() -> None:
    result = run_quawk('BEGIN { printf "%s:%g", "x", 1 }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "x:1"
    assert result.stderr == ""


def test_string_coercion_and_concatenation_follow_awk_rules() -> None:
    result = run_quawk('BEGIN { x = "12"; print x + 1; print x "a" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "13\n12a\n"
    assert result.stderr == ""


def test_split_and_substr_builtins_execute() -> None:
    result = run_quawk('BEGIN { n = split("a b", a); print n; print a[1]; print substr("hello", 2, 3) }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "2\na\nell\n"
    assert result.stderr == ""


def test_dynamic_field_assignment_updates_the_selected_field() -> None:
    result = run_quawk('{ i = 2; $i = 9; print $0 }', stdin="1 2 3\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1 9 3\n"
    assert result.stderr == ""


def test_builtin_variables_nr_fnr_and_nf_update_per_record() -> None:
    result = run_quawk("{ print NR; print FNR; print NF }", stdin="a b\nc d\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1\n2\n2\n2\n2\n"
    assert result.stderr == ""
