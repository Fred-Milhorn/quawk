from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t202_docs_record_the_post_audit_execution_model_boundary() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "| Backend parity for every claimed execution path | implemented |" in spec_text
    assert "every currently claimed execution family to have a compiled backend/runtime path" in design_text
    assert "ordinary public `quawk` execution no longer keeps host fallback for claimed behavior either" in design_text
    assert "### T-202 Execution-Model Rebaseline Result" in posix_text
    assert "representative unclaimed host-runtime-only programs now fail clearly" in posix_text
    assert "the former claimed value-fallback debt from `P20` is now closed" in posix_text


def test_t202_roadmap_closes_p19_and_sets_up_the_future_widening_wave() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P21 logical-or and comparison widening" in roadmap_text
    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "widen the" in roadmap_text
    assert "intentionally unclaimed expression surface in ranked backend-first" in roadmap_text
    assert "phases." in roadmap_text
    assert "| P21 | Logical-Or and Comparison Widening |" in roadmap_text
    assert "| T-202 | P19 | P1 | Rebaseline the execution-model docs after the host-boundary audit | T-201 |" in roadmap_text
    assert "| T-202 | P19 | P1 | Rebaseline the execution-model docs after the host-boundary audit | T-201 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the resulting host-runtime boundary and the ranked next follow-up wave | done |" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 |" in roadmap_text
