from __future__ import annotations

from pathlib import Path

from quawk.compat import upstream_inventory

ROOT = Path(__file__).resolve().parent.parent


def test_t216_plan_docs_record_p22_backend_and_inspection_closure() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")
    decision_text = (ROOT / "docs" / "plans" / "expression-surface-decision-table.md").read_text(
        encoding="utf-8"
    )

    assert "## T-214 And T-215 Backend Implementation Result" in analysis_text
    assert "## T-216 Inspection And Corroboration Result" in analysis_text
    assert "representative `-`, `*`, `/`, `%`, and `^` programs now succeed under" in analysis_text
    assert "### T-216 P22 Inspection And Corroboration Result" in posix_text
    assert "the existing runnable reference subset already corroborates this wave" in posix_text
    assert "| Broader arithmetic: `-`, `*`, `/`, `%`, `^` | yes | yes | yes | yes | yes | yes |" in decision_text


def test_t216_residual_matrix_no_longer_lists_broader_arithmetic() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "| Broader arithmetic |" not in matrix_text
    assert "## T-216 Residual Narrowing Result" in matrix_text
    assert "## T-216 Residual Boundary Narrowing Result" in audit_text


def test_t216_reference_subset_already_contains_clean_p22_corrobating_anchors() -> None:
    runnable_case_ids = {
        f"{selection.suite}:{selection.case_id}"
        for selection in upstream_inventory.load_upstream_selection_manifest()
        if selection.status == "run"
    }

    assert "one-true-awk:p.25" in runnable_case_ids
    assert "one-true-awk:p.34" in runnable_case_ids
    assert "one-true-awk:p.36" in runnable_case_ids
    assert "one-true-awk:p.44" in runnable_case_ids


def test_t216_roadmap_marks_p22_backend_work_done_and_advances_to_t217() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "No active widening phase is currently scheduled." in roadmap_text
    assert "`T-222` through `T-226` now close the full `P24` wave" in roadmap_text
    assert "| T-214 | P22 | P0 | Implement backend/runtime support for subtraction, multiplication, and division | T-213 | Representative `-`, `*`, and `/` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-215 | P22 | P0 | Implement backend/runtime support for modulo and exponentiation | T-213 | Representative `%` and `^` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-216 | P22 | P1 | Close inspection parity, routing coverage, and corroboration for the widened arithmetic surface | T-214, T-215 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P22` surface with no stale host-only gap | done |" in roadmap_text
    assert "| T-217 | P22 | P1 | Rebaseline the public contract after arithmetic widening | T-216 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P22` claim with no implied host dependency | done |" in roadmap_text
