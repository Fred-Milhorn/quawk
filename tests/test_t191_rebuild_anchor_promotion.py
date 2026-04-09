from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t191_manifest_promotes_p35_and_t_nf_to_runnable_reference_cases() -> None:
    selection_text = (ROOT / "tests" / "upstream" / "selection.toml").read_text(encoding="utf-8")

    assert 'case_id = "p.35"\npath = "third_party/onetrueawk/testdir/p.35"\nstatus = "run"' in selection_text
    assert 'case_id = "t.NF"\npath = "third_party/onetrueawk/testdir/t.NF"\nstatus = "run"' in selection_text


def test_t191_posix_and_roadmap_advance_to_the_expression_surface_decision_gate() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "### T-191 Rebuild-Anchor Corroboration Result" in posix_text
    assert "`one-true-awk:p.35` is now runnable" in posix_text
    assert "`one-true-awk:t.NF` is now runnable" in posix_text
    assert "| T-192 | P18 | P0 | Decide and document whether to widen the broader unclaimed POSIX expression surface |" in roadmap_text
    assert "| T-191 | P18 | P1 | Re-audit and promote the `p.35` / `t.NF` corroborating anchors | T-190 | The reviewed `p.35` / `t.NF` anchors move to `run` or are narrowed to smaller explicit non-product corroboration reasons after the behavior fix | done |" in roadmap_text
