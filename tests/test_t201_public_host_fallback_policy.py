from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t201_docs_record_the_no_fallback_public_execution_policy() -> None:
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")

    assert "## T-201 Public Fallback Policy Result" in audit_text
    assert "ordinary public `quawk` execution does not keep temporary host fallback" in audit_text
    assert "those programs now fail clearly outside the current AOT-backed contract" in audit_text
    assert "Ordinary public `quawk` execution now fails clearly for representative host-runtime-only programs" in spec_text
    assert "ordinary public `quawk` execution should fail clearly" in design_text


def test_t201_matrix_records_no_public_host_fallback_for_representative_rows() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")

    assert "| Logical-or | `BEGIN { print 1 || 0 }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert "| Broader comparisons | `BEGIN { print 1 != 0 }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert "| Broader arithmetic | `BEGIN { print 6 / 2 }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert "- ordinary public execution no longer uses host fallback for these rows" in matrix_text


def test_t201_roadmap_advances_the_immediate_next_list_to_t202() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P21 logical-or and comparison widening" in roadmap_text
    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "- `T-209`: implement backend/runtime support for `||`" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
    assert "| T-201 | P19 | P0 | Decide public behavior for unclaimed host-routed programs | T-200 | The roadmap, `SPEC.md`, and `docs/design.md` state whether ordinary `quawk` keeps temporary host fallback for those forms or fails explicitly outside the AOT-backed contract | done |" in roadmap_text
