from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t198_audit_doc_records_the_current_public_host_runtime_routes() -> None:
    audit_text = (ROOT / "docs" / "plans" / "host-runtime-boundary-audit.md").read_text(encoding="utf-8")

    assert "## T-197 Baseline Result" in audit_text
    assert "## T-198 Inventory Result" in audit_text
    assert "`execute()`" in audit_text
    assert "`execute_with_inputs()`" in audit_text
    assert "`lower_to_llvm_ir()`" in audit_text
    assert "`requires_host_runtime_execution(program)`" in audit_text
    assert "`requires_host_runtime_value_execution(program)`" in audit_text
    assert "Desired steady state for an implemented AWK feature:" in audit_text
    assert "- host semantic execution exists: `no`" in audit_text
    assert "- public host fallback exists: `no`" in audit_text
    assert "- public backend execution exists: `yes`" in audit_text
    assert "[residual-host-runtime-matrix.md](residual-host-runtime-matrix.md)" in audit_text
    assert "the remaining residual host routing is concentrated in the intentionally" in audit_text
    assert "unclaimed broader expression surface" in audit_text


def test_t198_matrix_records_the_representative_residual_host_routed_forms() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "residual-host-runtime-matrix.md").read_text(encoding="utf-8")

    assert "Host semantic execution exists today" in matrix_text
    assert "Public host fallback exists today" in matrix_text
    assert "Public backend executes today" in matrix_text
    assert "| Broader arithmetic | `BEGIN { print 6 / 2 }` | yes | yes | no | no | no | no |" in matrix_text
    assert "| Ternary | `BEGIN { print (1 ? 2 : 3) }` | yes | yes | no | no | no | no |" in matrix_text
    assert '| Match operators | `BEGIN { print ("abc" ~ /b/) }` | yes | yes | no | no | no | no |' in matrix_text
    assert '| `in` | `BEGIN { a["x"] = 1; print ("x" in a) }` | yes | yes | no | no | no | no |' in matrix_text
    assert "| Logical-or |" not in matrix_text
    assert "| Broader comparisons |" not in matrix_text
    assert "`requires_host_runtime_execution(program) == True`" in matrix_text
    assert "`supports_runtime_backend_subset(program) == False`" in matrix_text
    assert "`lower_to_llvm_ir(program)` currently raises the standard" in matrix_text
    assert "## T-211 Residual Narrowing Result" in matrix_text


def test_t198_posix_and_roadmap_point_to_the_checked_in_inventory_and_next_work() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "[docs/plans/residual-host-runtime-matrix.md](docs/plans/residual-host-runtime-matrix.md)" in posix_text
    assert "### P19: Residual Host-Runtime Boundary Audit" in roadmap_text
    assert "Next deliverable: P21 logical-or and comparison widening" in roadmap_text
    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "- `T-212`: rebaseline the public contract after `P21`" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
    assert "| T-197 | P19 | P0 | Author the residual host-runtime boundary audit baseline and scope | T-192 | `docs/plans/host-runtime-boundary-audit.md`, `POSIX.md`, and the roadmap make the backend-first purpose, audit scope, and required outputs explicit before new implementation decisions start | done |" in roadmap_text
    assert "| T-198 | P19 | P0 | Inventory public routes to the Python host runtime and produce the residual host-only matrix | T-197 | A checked-in matrix identifies residual host-routed forms, their claimed status, backend/inspection status, and whether they are reachable from ordinary public execution | done |" in roadmap_text
