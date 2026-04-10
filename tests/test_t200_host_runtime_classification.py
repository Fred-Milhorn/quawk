from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t200_matrix_records_the_current_residual_classifications() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")

    assert "| Family | Representative program | Reachable from ordinary `quawk` today | Host semantic execution exists today | Public host fallback exists today | Public backend executes today | `--ir` / `--asm` today | Claimed in `SPEC.md` today | Classification |" in matrix_text
    assert "No representative residual expression rows remain." in matrix_text
    assert "| Logical-or |" not in matrix_text
    assert "| Broader comparisons |" not in matrix_text
    assert "| Broader arithmetic |" not in matrix_text
    assert "| Ternary |" not in matrix_text
    assert "ranked expression-surface host-boundary cleanup is now" in matrix_text


def test_t200_audit_doc_records_that_no_claimed_family_is_new_aot_debt() -> None:
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "## T-200 Classification Result" in audit_text
    assert "- no new claimed family is currently classified as `AOT debt`" in audit_text
    assert "`unclaimed and backend-incomplete`" in audit_text
    assert "the residual boundary problem is a policy and implementation question" in audit_text
    assert "## T-216 Residual Boundary Narrowing Result" in audit_text


def test_t200_roadmap_advances_the_immediate_next_list_to_t212() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "| T-225 | P24 | P1 | Close inspection parity, routing coverage, and corroboration for match operators and membership | T-223, T-224 | `--ir` / `--asm`, focused routing regressions, and direct or reference corroboration cover the widened `P24` surface with no stale host-only gap | done |" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
    assert "| T-200 | P19 | P0 | Classify residual host-routed forms and identify accidental AOT debt | T-198, T-199 | Each residual host-routed form is marked as AOT debt, unclaimed but backend-ready, unclaimed and backend-incomplete, or host-only by design | done |" in roadmap_text
