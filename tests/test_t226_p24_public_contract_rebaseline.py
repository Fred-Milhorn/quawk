from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t226_spec_rebaselines_p24_from_unclaimed_to_implemented() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P24 match operators and membership | implemented |" in spec_text
    assert "| P24 inspection and routing parity | implemented |" in spec_text
    assert "`~`, `!~`" in spec_text
    assert "`in`" in spec_text
    assert "concatenation" in spec_text
    assert "The remaining match and `in` forms stay intentionally outside the current claimed AOT contract" not in spec_text


def test_t226_design_and_posix_record_the_widened_p24_claim() -> None:
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "`~`, `!~`" in design_text
    assert "`in`" in design_text
    assert "concatenation" in design_text
    assert "### T-226 P24 Public-Contract Rebaseline Result" in posix_text
    assert "the roadmap now treats `P24` as complete" in posix_text


def test_t226_roadmap_closes_p24_and_leaves_no_active_widening_phase() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-226 | P24 | P1 | Rebaseline the public contract after match and membership widening | T-225 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P24` claim with no implied host dependency | done |" in roadmap_text
