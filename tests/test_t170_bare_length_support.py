from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t170_spec_marks_current_builtin_subset_implemented() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Current builtin subset | implemented |" in spec_text
    assert "including bare `length` as POSIX `length($0)`" in spec_text


def test_t170_posix_notes_and_roadmap_advance_past_bare_length() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "### T-170 Bare Length Result" in posix_text
    assert "`p.30` is now runnable in the upstream subset" in posix_text
    assert "| T-170 | P15 | P0 | Fix bare `length` POSIX semantics and re-expand the builtin claim | T-167 | Bare `length` behaves as `length($0)` and the reviewed `p.30` anchor becomes clean | done |" in roadmap_text
