from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t221_spec_rebaselines_p23_from_unclaimed_to_implemented() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P23 ternary | implemented |" in spec_text
    assert "pure ternary expressions over the current claimed numeric/string subset" in spec_text
    assert "| P24 match operators and membership | implemented |" in spec_text
    assert "| Backend parity for broader frontend-admitted POSIX forms | partial | Broader frontend-admitted but intentionally unclaimed POSIX corners" in spec_text


def test_t221_design_and_posix_record_the_widened_p23_claim() -> None:
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "pure ternary expressions over the current claimed numeric/string subset" in design_text
    assert "`~`, `!~`" in design_text
    assert "`in`" in design_text
    assert "concatenation" in design_text
    assert "### T-221 P23 Public-Contract Rebaseline Result" in posix_text
    assert "the roadmap now treats `P23` as complete and moves the next deliverable to" in posix_text


def test_t221_roadmap_closes_p23_and_moves_to_p24() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "No active widening phase is currently scheduled." in roadmap_text
    assert "- `T-218` through `T-221` close the full `P23` wave" in roadmap_text
    assert "`T-222` through `T-226` now close the full `P24` wave" in roadmap_text
    assert "| T-221 | P23 | P1 | Rebaseline the public contract after ternary widening | T-220 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P23` claim with no implied host dependency | done |" in roadmap_text
