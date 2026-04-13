from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t283_spec_and_compatibility_record_the_final_audit_closeout() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    compatibility_text = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")

    assert "| Remaining POSIX compatibility corroboration gaps | implemented |" in spec_text
    assert "no stale reviewed gaps remain" in spec_text
    assert "The checked-in POSIX corroboration policy is now final:" in compatibility_text
    assert "and `P32` is" in compatibility_text
    assert "now complete." in compatibility_text


def test_t283_plan_and_posix_pin_the_final_audit_result() -> None:
    plan_text = (ROOT / "docs" / "plans" / "remaining-posix-compatibility-plan.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## T-283 Result" in plan_text
    assert "The final compatibility stop-line audit is now complete:" in plan_text
    assert "## T-283 Final POSIX Compatibility Audit Result" in posix_text
    assert "The final POSIX end-to-end compatibility audit is now complete:" in posix_text
    assert "`P32` is now closed out." in posix_text


def test_t283_roadmap_marks_p32_complete_and_clears_immediate_next_tasks() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-283 | P32 | P0 | Complete the final POSIX end-to-end compatibility audit | T-280, T-281, T-282 | `SPEC.md`, `docs/compatibility.md`, the upstream manifest, and the roadmap agree on the final implemented POSIX surface with no stale reviewed gaps | done |" in roadmap_text
    assert "P30, P31, and P32 are complete. The POSIX compatibility closeout work is fully checked in." in roadmap_text
    assert "No immediate next tasks remain." in roadmap_text
