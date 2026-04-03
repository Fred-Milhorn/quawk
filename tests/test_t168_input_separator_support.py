from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t168_spec_marks_input_separator_variables_implemented() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Input separator builtin variables | implemented |" in spec_text
    assert "CLI `-F` plus in-program `FS` / `RS` assignment now affect the current claimed field and record surface." in spec_text


def test_t168_posix_notes_that_separator_runtime_gap_is_closed() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-168 Input Separator Result" in posix_text
    assert "in-program `FS` assignment now updates field splitting" in posix_text
    assert "in-program `RS` assignment now updates current record reads" in posix_text


def test_t168_roadmap_marks_the_task_done() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-168 | P15 | P0 | Implement in-program `FS` / `RS` assignment for the current record surface | T-167 | Direct CLI tests and reviewed upstream `p.5` / `p.5a` style cases show runtime separator changes affect record and field splitting as in POSIX | done |" in roadmap_text
