from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t200_matrix_records_the_current_residual_classifications() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")

    assert "| Family | Representative program | Reachable from ordinary `quawk` today | Host semantic execution exists today | Public host fallback exists today | Public backend executes today | `--ir` / `--asm` today | Claimed in `SPEC.md` today | Classification |" in matrix_text
    assert "| Logical-or | `BEGIN { print 1 || 0 }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert "| Broader comparisons | `BEGIN { print 1 != 0 }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert "| Broader arithmetic | `BEGIN { print 6 / 2 }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert "| Ternary | `BEGIN { print (1 ? 2 : 3) }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |" in matrix_text
    assert '| Match operators | `BEGIN { print ("abc" ~ /b/) }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |' in matrix_text
    assert '| `in` | `BEGIN { a["x"] = 1; print ("x" in a) }` | yes | yes | no | no | no | no | unclaimed and backend-incomplete |' in matrix_text
    assert "- no representative row in this matrix is currently classified as `AOT debt`" in matrix_text


def test_t200_audit_doc_records_that_no_claimed_family_is_new_aot_debt() -> None:
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "## T-200 Classification Result" in audit_text
    assert "- no new claimed family is currently classified as `AOT debt`" in audit_text
    assert "the representative logical-or, broader-comparison, broader-arithmetic," in audit_text
    assert "`unclaimed and backend-incomplete`" in audit_text
    assert "the residual boundary problem is a policy and implementation question" in audit_text


def test_t200_roadmap_advances_the_immediate_next_list_to_t201() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-197`, `T-198`, `T-199`, `T-200`, and `T-201` are complete." in roadmap_text
    assert "- `T-202`: rebaseline the public execution-model docs after the audit" in roadmap_text
    assert "| T-200 | P19 | P0 | Classify residual host-routed forms and identify accidental AOT debt | T-198, T-199 | Each residual host-routed form is marked as AOT debt, unclaimed but backend-ready, unclaimed and backend-incomplete, or host-only by design | done |" in roadmap_text
