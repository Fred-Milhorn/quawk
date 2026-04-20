"""Behavior-oriented coverage for execution-model documentation rebaseline (from T-289)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t289_design_and_inventory_rebaseline_the_compiled_execution_model() -> None:
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    inventory_text = (ROOT / "docs" / "plans" / "backend-gap-inventory.md").read_text(encoding="utf-8")
    plan_text = (ROOT / "docs" / "plans" / "direct-path-removal-plan.md").read_text(encoding="utf-8")

    assert "the reusable LLVM/backend split is now the only compiled execution and inspection route" in design_text
    assert "Public execution currently accepts a program only if it fits the reusable" in inventory_text
    assert "The earlier narrow direct-function lane is retired" in inventory_text
    assert "direct-function backend subset" not in inventory_text
    assert "## T-289 Result" in plan_text
    assert "the reusable backend/runtime split is the" in plan_text


def test_t289_roadmap_marks_p33_complete_and_clears_t289_from_immediate_tasks() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-284` through `T-289` are complete. `P33` is complete." in roadmap_text
    assert "- `T-289`" not in roadmap_text.split("Immediate next tasks:")[1]
    assert "- No scheduled `P33` follow-on tasks remain; choose the next backlog priority." in roadmap_text
    assert (
        "| T-289 | P33 | P1 | Rebaseline the execution-model docs after direct-path collapse | T-288 | "
        "`docs/design.md`, the roadmap, and any direct-path inventory notes agree that the reusable backend "
        "path is the only compiled execution route and no stale direct-lane wording remains | done |"
    ) in roadmap_text
