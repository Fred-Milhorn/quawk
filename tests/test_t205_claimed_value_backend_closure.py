from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t205_plan_doc_records_the_backend_closure_result() -> None:
    plan_text = (ROOT / "docs" / "plans" / "claimed-value-fallback-cleanup.md").read_text(encoding="utf-8")

    assert "## T-205 Value-Semantics Closure Result" in plan_text
    assert "`BEGIN { print x }` now stays on the backend/runtime path" in plan_text
    assert "`BEGIN { y = x; print y }` now stays on the backend/runtime path" in plan_text
    assert "`BEGIN { print x; print x + 1 }` now stays on the backend/runtime path" in plan_text
    assert "`BEGIN { x = 1; print x }` now stays on the backend/runtime path" in plan_text
    assert "That leaves `T-206` to remove the remaining claimed public value fallback" in plan_text


def test_t205_roadmap_advances_to_remaining_claimed_value_fallback_removal() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P21 logical-or and comparison widening" in roadmap_text
    assert "`T-197` through `T-207` are complete." in roadmap_text
    assert "- `T-208`: author the backend-only baseline, target `SPEC.md` rows, and direct tests for `P21`" in roadmap_text
    assert "| T-205 | P20 | P0 | Close the backend/runtime value-semantics gaps for the claimed cases | T-204 | The backend/runtime path matches the claimed unset-value and coercion behavior for the inventoried cases | done |" in roadmap_text
