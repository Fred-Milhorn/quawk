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


def test_t275_parenthesized_array_target_wrappers_execute_through_public_execution() -> None:
    expected = {
        'BEGIN { a["x"] = 1; for (k in (a)) print k }': "x\n",
        'BEGIN { a["x"] = 1; print ("x" in (a)) }': "1\n",
        'BEGIN { n = split("a b", (a)); print n; print a[1] }': "2\na\n",
    }

    for source_text, stdout in expected.items():
        result = run_quawk(source_text)

        assert result.returncode == 0, result.stderr
        assert result.stdout == stdout
        assert result.stderr == ""


def test_t275_parenthesized_array_target_wrappers_support_inspection() -> None:
    programs = [
        'BEGIN { a["x"] = 1; for (k in (a)) print k }',
        'BEGIN { a["x"] = 1; print ("x" in (a)) }',
        'BEGIN { n = split("a b", (a)); print n; print a[1] }',
    ]

    for flag in ("--ir", "--asm"):
        for source_text in programs:
            result = run_quawk(flag, source_text)

            assert result.returncode == 0, result.stderr
            assert result.stdout != ""
            assert result.stderr == ""
