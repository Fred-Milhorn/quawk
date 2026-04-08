from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t207_docs_record_the_final_post_p20_execution_model_state() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "| Backend parity for every claimed execution path | implemented |" in spec_text
    assert "ordinary public execution no longer uses host fallback for claimed behavior" in spec_text
    assert "ordinary public `quawk` execution no longer keeps host fallback for claimed behavior either" in design_text
    assert "claimed public execution no longer keeps temporary host fallback for richer value semantics" in design_text
    assert "### T-207 Execution-Model Final Rebaseline Result" in posix_text
    assert "the former claimed value-fallback debt from `P20` is now closed" in posix_text


def test_t207_roadmap_closes_p20_and_clears_the_immediate_next_list() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: none currently scheduled" in roadmap_text
    assert "`T-197` through `T-207` are complete." in roadmap_text
    assert "backend/runtime closure wave are now complete in `P20`" in roadmap_text
    assert "- none currently scheduled; define a new prioritized phase before adding more implementation work" in roadmap_text
    assert "| T-207 | P20 | P1 | Rebaseline the execution-model docs after claimed fallback removal | T-206 | `SPEC.md`, `docs/design.md`, the roadmap, and focused regressions agree that the full claimed surface no longer uses public host fallback | done |" in roadmap_text
