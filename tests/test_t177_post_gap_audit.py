from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t177_spec_reexpands_only_the_fixed_printf_claim() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Full POSIX `printf` parity | implemented |" in spec_text
    assert "tracked for `P14`" not in spec_text
    assert "until the `P14` completion work lands" not in spec_text


def test_t177_posix_plan_pins_the_remaining_reviewed_skips() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-177 Final Claim Expansion And Audit Result" in posix_text
    assert "`p.43`, `p.48b`, `range1`" in posix_text
    assert "`T.argv`, `T.builtin`, `T.expr`, `T.func`, `T.split`, `cmdlinefsbacknl`" in posix_text
    assert "post-`P14` remaining-gap wave is complete" in posix_text


def test_t177_roadmap_marks_p15_closeout_complete() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P24 match and membership widening" in roadmap_text
    assert "| T-177 | P15 | P0 | Re-expand `SPEC.md` and complete the post-gap POSIX audit | T-169, T-170, T-171, T-172, T-173, T-174, T-175, T-176 | Public claims widen only for fixed families, unsuitable anchors such as `p.43`, `p.48b`, and `range1` remain explicit reviewed skips, and the docs plus manifest agree on the resulting surface | done |" in roadmap_text
