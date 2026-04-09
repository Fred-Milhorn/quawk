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


def test_t207_roadmap_closes_p20_and_sets_up_the_future_expression_waves() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P24 match and membership widening" in roadmap_text
    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "`T-208` through `T-212` close the full" in roadmap_text
    assert "| T-207 | P20 | P1 | Rebaseline the execution-model docs after claimed fallback removal | T-206 | `SPEC.md`, `docs/design.md`, the roadmap, and focused regressions agree that the full claimed surface no longer uses public host fallback | done |" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 |" in roadmap_text
    assert "- `T-222`: author the backend-only baseline and direct tests for match operators and membership" in roadmap_text
    assert "| T-226 | P24 | P1 | Rebaseline the public contract after match and membership widening | T-225 |" in roadmap_text
