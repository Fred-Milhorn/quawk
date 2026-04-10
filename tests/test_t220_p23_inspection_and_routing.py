from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t220_plan_docs_record_p23_backend_and_inspection_closure() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    decision_text = (ROOT / "docs" / "plans" / "expression-surface-decision-table.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## T-219 Backend Implementation Result" in analysis_text
    assert "## T-220 Inspection And Corroboration Result" in analysis_text
    assert "representative ternary programs now succeed under `--ir` and `--asm`" in analysis_text
    assert "no clean checked-in reference anchor is pinned for `P23` yet" in analysis_text
    assert "### T-220 P23 Inspection And Corroboration Result" in posix_text
    assert "| Ternary: `test ? a : b` | yes | yes | yes | yes | yes | no |" in decision_text


def test_t220_residual_matrix_no_longer_lists_ternary() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "| Ternary |" not in matrix_text
    assert "## T-220 Residual Narrowing Result" in matrix_text
    assert "## T-220 Residual Boundary Narrowing Result" in audit_text


def test_t220_roadmap_marks_p23_backend_work_done_and_advances_to_t221() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-219 | P23 | P0 | Implement backend/runtime support for ternary expressions | T-218 | Representative ternary programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-220 | P23 | P1 | Close inspection parity, routing coverage, and corroboration for ternary | T-219 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover ternary with no stale host-only gap | done |" in roadmap_text
    assert "| T-221 | P23 | P1 | Rebaseline the public contract after ternary widening | T-220 | `SPEC.md`, `POSIX.md`, `docs/design.md`, and the roadmap agree on the widened backend-only `P23` claim with no implied host dependency | done |" in roadmap_text
