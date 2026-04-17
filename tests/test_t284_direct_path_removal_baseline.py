from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_t284_plan_doc_records_the_direct_path_baseline_and_next_steps() -> None:
    plan_text = (ROOT / "docs" / "plans" / "direct-path-removal-plan.md").read_text(encoding="utf-8")

    assert "## T-284 Baseline Result" in plan_text
    assert "Focused routing regressions now pin the representative over-gated rows" in plan_text
    assert "`BEGIN { print $1 }` still fails during lowering" in plan_text
    assert "`BEGIN { x = a[\"k\"] }` still fails" in plan_text
    assert "`BEGIN { x = 1; x += 2 }` still fails" in plan_text
    assert "`T-285` to remove the restricted direct-lowering fallback" in plan_text


def test_t284_roadmap_marks_the_baseline_done_and_advances_to_t285() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "### P33: Direct-Path Removal And Route Cleanup" in roadmap_text
    assert "`T-284` is complete." in roadmap_text
    assert "| T-284 | P33 | P0 | Author the direct-path-removal baseline and representative routing regressions | T-283 | Focused tests and roadmap text make the remaining direct-lane entrypoints, stale guards, and representative over-gated programs explicit before implementation | done |" in roadmap_text
    assert "- `T-284`" not in roadmap_text.split("Immediate next tasks:")[1]
    assert "| T-285 | P33 | P0 | Remove the restricted direct lowering lane and dead direct-only helpers | T-284 | `lower_to_llvm_ir()` no longer emits the standalone direct-lowered `quawk_main()` fallback, and dead direct-function or record-loop helpers are removed or made unreachable by design |" in roadmap_text
