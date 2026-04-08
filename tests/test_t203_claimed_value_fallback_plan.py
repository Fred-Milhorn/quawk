from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t203_plan_doc_records_the_claimed_value_fallback_follow_on() -> None:
    plan_text = (ROOT / "docs" / "plans" / "claimed-value-fallback-cleanup.md").read_text(encoding="utf-8")

    assert "# Claimed Value-Fallback Cleanup" in plan_text
    assert "The remaining gap is narrower than the old residual matrix" in plan_text
    assert "`requires_host_runtime_value_execution()`" in plan_text
    assert "BEGIN { print x }" in plan_text
    assert "no remaining claimed public feature that requires semantic host execution" in plan_text


def test_t203_roadmap_adds_p20_after_the_p19_rebaseline_task() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "| P20 | Claimed Value-Fallback Cleanup |" in roadmap_text
    assert "- `T-202`: rebaseline the public execution-model docs after the audit" in roadmap_text
    assert "- after `T-202`, begin `P20`:" in roadmap_text
    assert "- `T-203`: inventory the remaining claimed value-fallback cases" in roadmap_text
    assert "| T-203 | P20 | P0 | Inventory the remaining claimed value-fallback cases | T-202 |" in roadmap_text
    assert "| T-207 | P20 | P1 | Rebaseline the execution-model docs after claimed fallback removal | T-206 |" in roadmap_text
    assert "[claimed-value-fallback-cleanup.md](claimed-value-fallback-cleanup.md)" in audit_text
