# P4 regex-filter execution tests.
# These cases verify the first regex-driven filtering deliverable through the
# public CLI execution path.

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


def test_inline_regex_filter_executes() -> None:
    result = run_quawk("/foo/ { print $0 }", stdin="foo\nbar\nfood\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "foo\nfood\n"
    assert result.stderr == ""


def test_inline_regex_filter_matches_later_text_in_full_record() -> None:
    result = run_quawk("/AWK/ { print $0 }", stdin='help="Read AWK program"\nhelp="Read text"\n')

    assert result.returncode == 0, result.stderr
    assert result.stdout == 'help="Read AWK program"\n'
    assert result.stderr == ""


def test_file_based_regex_filter_executes() -> None:
    program_path = ROOT / "tests" / "corpus" / "regex_filter" / "program.awk"
    input_path = ROOT / "tests" / "corpus" / "regex_filter" / "input.txt"
    result = run_quawk("-f", str(program_path), str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "foo\nfood\n"
    assert result.stderr == ""
