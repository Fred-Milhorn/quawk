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


def test_t199_roadmap_advances_the_immediate_next_list_to_t200() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-197`, `T-198`, `T-199`, `T-200`, and `T-201` are complete." in roadmap_text
    assert "- `T-202`: rebaseline the public execution-model docs after the audit" in roadmap_text
    assert "| T-199 | P19 | P1 | Add focused routing regressions for representative residual host-routed forms | T-198 | Direct tests pin whether representative forms route to the backend, fall back to the host, or fail under `--ir` / `--asm` today | done |" in roadmap_text
