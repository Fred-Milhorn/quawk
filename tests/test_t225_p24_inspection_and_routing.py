from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t225_plan_docs_record_p24_backend_and_inspection_closure() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    decision_text = (ROOT / "docs" / "plans" / "expression-surface-decision-table.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## T-223 And T-224 Backend Implementation Result" in analysis_text
    assert "## T-225 Inspection And Corroboration Result" in analysis_text
    assert "representative `~`, `!~`, and `in` programs now succeed under `--ir` and" in analysis_text
    assert "no clean checked-in reference anchor is pinned for `P24` yet" in analysis_text
    assert "### T-225 P24 Inspection And Corroboration Result" in posix_text
    assert "| Match operators: `~`, `!~` | yes | yes | yes | yes | yes | no |" in decision_text
    assert "| Membership: `expr in array` | yes | yes | yes | yes | yes | no |" in decision_text


def test_t225_residual_matrix_no_longer_lists_match_or_membership() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "| Match operators |" not in matrix_text
    assert "| `in` |" not in matrix_text
    assert "No representative residual expression rows remain." in matrix_text
    assert "## T-225 Residual Narrowing Result" in matrix_text
    assert "## T-225 Residual Boundary Narrowing Result" in audit_text


def test_t225_roadmap_marks_p24_backend_work_done_and_advances_to_t226() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "No active widening phase is currently scheduled." in roadmap_text
    assert "| T-223 | P24 | P0 | Implement backend/runtime support for match operators | T-222 | Representative `~` and `!~` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-224 | P24 | P0 | Implement backend/runtime support for membership tests | T-222 | Representative `in` programs execute correctly through ordinary public backend/runtime execution with no host fallback | done |" in roadmap_text
    assert "| T-225 | P24 | P1 | Close inspection parity, routing coverage, and corroboration for match operators and membership | T-223, T-224 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P24` surface with no stale host-only gap | done |" in roadmap_text
