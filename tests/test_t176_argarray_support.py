from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t176_posix_plan_records_the_argarray_result() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-176 CLI-Sensitive Corroboration Result" in posix_text
    assert "`argarray` selection now runs as a focused equivalent" in posix_text
    assert "stable `ARGC` / `ARGV[1..]` and" in posix_text
    assert "`T-177`" in posix_text


def test_t176_roadmap_marks_the_cli_corroboration_task_done() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-176 | P15 | P1 | Improve CLI-sensitive corroboration coverage | T-167 |" in roadmap_text
    assert "| T-176 | P15 | P1 | Improve CLI-sensitive corroboration coverage | T-167 | `argarray` is either runnable with a clean adapter or superseded by an equivalent corroborating anchor for `ARGV` / multifile behavior | done |" in roadmap_text
