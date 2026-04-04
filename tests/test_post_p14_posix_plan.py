from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_roadmap_defines_p15_remaining_posix_gap_closure() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| P15 | Remaining POSIX Gap Closure |" in roadmap_text
    assert "### P15: Remaining POSIX Gap Closure" in roadmap_text
    assert "| T-168 | P15 | P0 | Implement in-program `FS` / `RS` assignment for the current record surface |" in roadmap_text
    assert "| T-169 | P15 | P1 | Re-audit and promote `FS`-sensitive upstream direct-file cases | T-168 | Clean `p.5`, `p.5a`, `p.35`, `p.36`, `p.48`, `p.50`, `p.51`, and `p.52` cases move to `run` or to narrower residual reasons | done |" in roadmap_text
    assert "| T-177 | P15 | P0 | Re-expand `SPEC.md` and complete the post-gap POSIX audit |" in roadmap_text


def test_posix_plan_records_post_p14_gap_categories_and_order() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## Post-P14 Remaining Gap Plan" in posix_text
    assert "### T-171 Comparison and Expression-Pattern Result" in posix_text
    assert "### T-173 Reusable-Backend Crash Result" in posix_text
    assert "non-UTF-8 input policy" in posix_text
    assert "remaining corroboration-sensitive gaps" in posix_text
    assert "narrowed `$0` field-rebuild corroboration gap after `T-169`" in posix_text
    assert "Recommended execution order for the post-`P14` gap-closure wave:" in posix_text
    assert "Roadmap mapping:" in posix_text
    assert "`T-168`: current record-surface `FS` / `RS` assignment" in posix_text
    assert "`T-169`: re-audit and promote the unlocked `FS`-sensitive direct-file cases" in posix_text
    assert "`p.7`, `p.8`, `p.21a`, and `t.next` are now" in posix_text
    assert "`p.29`, `p.32`, and `t.set0a` are now runnable" in posix_text
    assert "`T-177`: final claim expansion and post-gap audit" in posix_text
