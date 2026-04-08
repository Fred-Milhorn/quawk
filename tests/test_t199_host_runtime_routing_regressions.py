from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t199_audit_doc_records_the_focused_routing_regression_result() -> None:
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "## T-199 Routing Regression Result" in audit_text
    assert "ordinary public execution is now pinned to fail clearly" in audit_text
    assert "rather than use host" in audit_text
    assert "representative `--ir` and `--asm` requests still fail" in audit_text
    assert "this routing behavior is now explicit regression coverage" in audit_text


def test_t199_roadmap_now_points_at_the_p21_contract_rebaseline() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P22 arithmetic widening" in roadmap_text
    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "- `T-213`: author the backend-only baseline and direct tests for the broader arithmetic wave" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
    assert "| T-199 | P19 | P1 | Add focused routing regressions for representative residual host-routed forms | T-198 | Direct tests pin whether representative forms route to the backend, fall back to the host, or fail under `--ir` / `--asm` today | done |" in roadmap_text
