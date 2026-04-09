from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t204_plan_doc_records_the_focused_routing_regression_result() -> None:
    plan_text = (ROOT / "docs" / "plans" / "claimed-value-fallback-cleanup.md").read_text(encoding="utf-8")

    assert "## T-204 Routing Regression Result" in plan_text
    assert "Focused routing regressions now pin the representative claimed rows" in plan_text
    assert "That leaves `T-205` to close the backend/runtime value-semantics gaps" in plan_text


def test_t204_roadmap_advances_p20_to_the_value_semantics_work() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P23 ternary widening" in roadmap_text
    assert "| T-204 | P20 | P1 | Add focused routing regressions for the claimed value-fallback cases | T-203 | Direct tests pin which claimed programs still rely on the host evaluator today and prove the behavioral requirement they preserve | done |" in roadmap_text
