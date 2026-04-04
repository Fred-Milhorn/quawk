from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t175_posix_plan_records_the_splitvar_result() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-175 Split Target-Variable Result" in posix_text
    assert "`split()` now treats an explicit third argument as a regexp separator" in posix_text
    assert "`splitvar` is now runnable" in posix_text
    assert "`argarray`" in posix_text


def test_t175_roadmap_marks_the_splitvar_task_done() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-175 | P15 | P1 | Fix the remaining `split` target-variable mismatch and re-audit corroboration | T-167 |" in roadmap_text
    assert "| T-175 | P15 | P1 | Fix the remaining `split` target-variable mismatch and re-audit corroboration | T-167 | `splitvar` becomes clean or is replaced by a narrower classified skip backed by direct repo-owned tests | done |" in roadmap_text
