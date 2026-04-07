from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t189_spec_makes_the_remaining_claimed_gap_and_unclaimed_expression_surface_explicit() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Repeated `$0` reassignment and field rebuild | partial |" in spec_text
    assert "`p.35` / `t.NF`" in spec_text
    assert "| Expressions | partial |" in spec_text
    assert "Broader arithmetic, comparison, logical-or, ternary, match, and `in` forms remain intentionally outside the current claimed AOT contract." in spec_text


def test_t189_posix_doc_records_the_remaining_gap_the_anchor_cases_and_the_decision_gate() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## P18 Remaining Surface Baseline" in posix_text
    assert "Current remaining claimed product gap:" in posix_text
    assert "`$0` / `NF` rebuild behavior is still the one explicit partial row" in posix_text
    assert "Current corroborating anchors for that gap:" in posix_text
    assert "`one-true-awk:p.35`" in posix_text
    assert "`one-true-awk:t.NF`" in posix_text
    assert "Decision-gated broader surface, not current product debt:" in posix_text
    assert "`||`" in posix_text
    assert "`<=`, `>`, `>=`, `!=`" in posix_text
    assert "`-`, `*`, `/`, `%`, `^`" in posix_text
    assert "ternary" in posix_text
    assert "match operators" in posix_text
    assert "`in`" in posix_text


def test_t189_manifest_still_tracks_the_two_remaining_product_gap_anchors_as_reviewed_skips() -> None:
    selection_text = (ROOT / "tests" / "upstream" / "selection.toml").read_text(encoding="utf-8")

    assert 'case_id = "p.35"' in selection_text
    assert 'case_id = "t.NF"' in selection_text
    assert "Still exposes a narrower `$0` field-rebuild mismatch after field mutation" in selection_text
    assert "the actual remaining mismatch is `NF`-driven record rebuild behavior" in selection_text


def test_t189_roadmap_marks_the_baseline_done_and_moves_to_t190() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P18 remaining POSIX surface closure and widening decisions" in roadmap_text
    assert "`T-189` is complete. The next implementation step is the remaining claimed" in roadmap_text
    assert "- `T-190` fix the remaining claimed `$0` / `NF` rebuild mismatch" in roadmap_text
    assert "- `T-189` author the remaining POSIX surface baseline and decision gate" not in roadmap_text
    assert "| T-189 | P18 | P0 | Author the remaining POSIX surface baseline and widening decision gate | T-188 | Tests and docs make the remaining claimed `$0` / `NF` rebuild gap, the `p.35` / `t.NF` corroboration targets, and the currently unclaimed broader POSIX expression families explicit before further implementation | done |" in roadmap_text
