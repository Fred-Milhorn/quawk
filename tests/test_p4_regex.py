# P4 regex-filter execution baseline tests.
# These cases define the first regex-driven deliverable before parser/runtime
# support lands for regex pattern actions.

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


@pytest.mark.xfail(
    strict=True,
    reason="T-087 baseline: regex-driven record filtering is not implemented yet",
)
def test_inline_regex_filter_executes() -> None:
    result = run_quawk("/foo/ { print $0 }", stdin="foo\nbar\nfood\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "foo\nfood\n"
    assert result.stderr == ""


@pytest.mark.xfail(
    strict=True,
    reason="T-087 baseline: file-based regex-driven record filtering is not implemented yet",
)
def test_file_based_regex_filter_executes() -> None:
    program_path = ROOT / "tests" / "corpus" / "regex_filter" / "program.awk"
    input_path = ROOT / "tests" / "corpus" / "regex_filter" / "input.txt"
    result = run_quawk("-f", str(program_path), str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "foo\nfood\n"
    assert result.stderr == ""
