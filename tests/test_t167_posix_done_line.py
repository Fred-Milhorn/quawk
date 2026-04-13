from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t167_spec_tracks_remaining_posix_gap_rows_explicitly() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Repeated `$0` reassignment and field rebuild | implemented |" in spec_text
    assert "| Input separator builtin variables | implemented |" in spec_text
    assert "CLI `-F` plus in-program `FS` / `RS` assignment" in spec_text
    assert "| POSIX-standard builtin subset | implemented |" in spec_text
    assert "including bare `length` as POSIX `length($0)`" in spec_text


def test_t167_posix_plan_records_the_done_line_audit_result() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-167 POSIX Done-Line Result" in posix_text
    assert "non-UTF-8 fixture input" in posix_text
    assert "numeric comparison mismatches" in posix_text
    assert "reusable-backend" in posix_text
    assert "`argarray`" in posix_text


def test_t167_roadmap_records_p15_complete_after_the_done_line_audit() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-167 | P14 | P0 | Complete the POSIX done-line audit |" in roadmap_text
    assert "| T-167 | P14 | P0 | Complete the POSIX done-line audit | T-157, T-166 |" in roadmap_text
    assert "| T-167 | P14 | P0 | Complete the POSIX done-line audit | T-157, T-166 | `SPEC.md`, `POSIX.md`, the upstream manifest, and the required tests agree on the remaining in-scope POSIX surface with no untracked gaps | done |" in roadmap_text
    assert "| T-177 | P15 | P0 | Re-expand `SPEC.md` and complete the post-gap POSIX audit |" in roadmap_text
    assert "| T-202 | P19 | P1 | Rebaseline the execution-model docs after the host-boundary audit |" in roadmap_text
    assert "| T-203 | P20 | P0 | Inventory the remaining claimed value-fallback cases |" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons |" in roadmap_text
