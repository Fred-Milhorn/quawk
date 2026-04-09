from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t212_spec_rebaselines_p21_from_planned_to_implemented() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P21 logical-or and broader comparisons | implemented |" in spec_text
    assert "| P21 inspection and routing parity | implemented |" in spec_text
    assert "| P21 logical-or and broader comparison target | planned |" not in spec_text
    assert "| P21 inspection and routing target | planned |" not in spec_text
    assert "`!=`, `&&`, `||`" in spec_text
    assert "`-`, `*`, `/`, `%`, `^`" in spec_text
    assert "The remaining match and `in` forms stay intentionally outside the current claimed AOT contract" in spec_text


def test_t212_design_and_posix_record_the_widened_p21_claim() -> None:
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "`!=`, `&&`, `||`" in design_text
    assert "`-`, `*`, `/`, `%`, `^`" in design_text
    assert "match operators and `in`" in design_text
    assert "### T-212 P21 Public-Contract Rebaseline Result" in posix_text
    assert "the roadmap now treats `P21` as complete and moves the next deliverable to" in posix_text


def test_t212_roadmap_closes_p21_and_moves_to_p22() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P24 match and membership widening" in roadmap_text
    assert "`T-208` through `T-212` close the full" in roadmap_text
    assert "`P21` wave" in roadmap_text
    assert "- `T-222`: author the backend-only baseline and direct tests for match operators and membership" in roadmap_text
    assert "| T-212 | P21 | P1 | Rebaseline the public contract after logical-or and comparison widening | T-211 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P21` claim with no implied host dependency | done |" in roadmap_text
