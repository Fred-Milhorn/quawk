from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t202_docs_record_the_post_audit_execution_model_boundary() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "| Backend parity for every claimed execution path | partial |" in spec_text
    assert "A narrower claimed value-semantics fallback path still remains" in spec_text
    assert "every currently claimed execution family to have a compiled backend/runtime path" in design_text
    assert "a narrower claimed value-fallback path still remains for some public cases" in design_text
    assert "### T-202 Execution-Model Rebaseline Result" in posix_text
    assert "representative unclaimed host-runtime-only programs now fail clearly" in posix_text
    assert "the next ranked architecture wave in `P20`" in posix_text


def test_t202_roadmap_closes_p19_and_advances_to_p20() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P20 claimed value-fallback cleanup" in roadmap_text
    assert "`T-197` through `T-202` are complete." in roadmap_text
    assert "`P19` is complete." in roadmap_text
    assert "- `T-203`: inventory the remaining claimed value-fallback cases" in roadmap_text
    assert "| T-202 | P19 | P1 | Rebaseline the execution-model docs after the host-boundary audit | T-201 |" in roadmap_text
    assert "| T-202 | P19 | P1 | Rebaseline the execution-model docs after the host-boundary audit | T-201 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the resulting host-runtime boundary and the ranked next follow-up wave | done |" in roadmap_text
