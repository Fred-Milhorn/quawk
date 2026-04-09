from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t217_spec_rebaselines_p22_from_unclaimed_to_implemented() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P22 broader arithmetic | implemented |" in spec_text
    assert "| P22 inspection and routing parity | implemented |" in spec_text
    assert "`+`, `-`, `*`, `/`, `%`, `^`, `<`, `<=`, `>`, `>=`, `==`, `!=`, `&&`, `||`" in spec_text
    assert "The remaining match and `in` forms stay intentionally outside the current claimed AOT contract" in spec_text


def test_t217_design_and_posix_record_the_widened_p22_claim() -> None:
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "`+`, `-`, `*`, `/`, `%`, `^`, `<`, `<=`, `>`, `>=`, `==`, `!=`, `&&`, `||`" in design_text
    assert "broader frontend-admitted but not yet claimed POSIX forms, such as match operators and `in`" in design_text
    assert "### T-217 P22 Public-Contract Rebaseline Result" in posix_text
    assert "the roadmap now treats `P22` as complete and moves the next deliverable to" in posix_text


def test_t217_roadmap_closes_p22_and_moves_to_p23() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P24 match and membership widening" in roadmap_text
    assert "`T-213` through `T-217` now close the full `P22` wave" in roadmap_text
    assert "- `T-222`: author the backend-only baseline and direct tests for match operators and membership" in roadmap_text
    assert "| T-217 | P22 | P1 | Rebaseline the public contract after arithmetic widening | T-216 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P22` claim with no implied host dependency | done |" in roadmap_text
