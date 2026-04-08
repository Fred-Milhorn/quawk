from __future__ import annotations

from pathlib import Path

from quawk.compat import upstream_inventory

ROOT = Path(__file__).resolve().parent.parent


def test_t211_plan_docs_record_p21_backend_and_inspection_closure() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")
    decision_text = (ROOT / "docs" / "plans" / "expression-surface-decision-table.md").read_text(
        encoding="utf-8"
    )

    assert "## T-209 And T-210 Backend Implementation Result" in analysis_text
    assert "## T-211 Inspection And Corroboration Result" in analysis_text
    assert "representative `||`, `<=`, `>`, `>=`, and `!=` programs now succeed under" in analysis_text
    assert "### T-211 P21 Inspection And Corroboration Result" in posix_text
    assert "the existing runnable reference subset already corroborates this wave" in posix_text
    assert "| `||` | yes | yes | yes | yes | yes | yes |" in decision_text
    assert "| Broader comparisons: `<=`, `>`, `>=`, `!=` | yes | yes | yes | yes | yes | yes |" in decision_text


def test_t211_residual_matrix_no_longer_lists_logical_or_or_broader_comparisons() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "| Logical-or |" not in matrix_text
    assert "| Broader comparisons |" not in matrix_text
    assert "## T-211 Residual Narrowing Result" in matrix_text
    assert "## T-211 Residual Boundary Narrowing Result" in audit_text


def test_t211_reference_subset_already_contains_clean_p21_corrobating_anchors() -> None:
    runnable_case_ids = {
        f"{selection.suite}:{selection.case_id}"
        for selection in upstream_inventory.load_upstream_selection_manifest()
        if selection.status == "run"
    }

    assert "one-true-awk:p.7" in runnable_case_ids
    assert "one-true-awk:p.8" in runnable_case_ids
    assert "one-true-awk:p.21a" in runnable_case_ids
    assert "one-true-awk:t.next" in runnable_case_ids


def test_t211_roadmap_marks_p21_backend_work_done_and_advances_to_t212() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P21 logical-or and comparison widening" in roadmap_text
    assert "- `T-212`: rebaseline the public contract after `P21`" in roadmap_text
    assert "| T-209 | P21 | P0 | Implement backend/runtime support for logical-or | T-208 | Representative `||` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-210 | P21 | P0 | Implement backend/runtime support for broader comparisons | T-208 | Representative `<=`, `>`, `>=`, and `!=` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-211 | P21 | P1 | Close inspection parity, routing coverage, and corroboration for the widened logical-or and comparison surface | T-209, T-210 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P21` surface with no stale host-only gap | done |" in roadmap_text
