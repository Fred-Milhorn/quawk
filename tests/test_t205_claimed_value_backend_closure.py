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

    assert "Next deliverable: P24 match and membership widening" in roadmap_text
    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "- `T-222`: author the backend-only baseline and direct tests for match operators and membership" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
    assert "| T-205 | P20 | P0 | Close the backend/runtime value-semantics gaps for the claimed cases | T-204 | The backend/runtime path matches the claimed unset-value and coercion behavior for the inventoried cases | done |" in roadmap_text
