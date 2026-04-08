from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t192_spec_and_posix_keep_broader_expression_surface_unclaimed() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "The `T-192` decision keeps broader arithmetic, comparison, logical-or, ternary, match, and `in` forms intentionally outside the current claimed AOT contract" in spec_text
    assert "### T-192 Expression-Surface Decision Result" in posix_text
    assert "The broader intentionally unclaimed POSIX expression surface is not approved" in posix_text
    assert "do not start `T-193` through `T-196` in the current roadmap wave" in posix_text


def test_t192_roadmap_blocks_follow_on_expression_tasks() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-192` is complete. The decision was to keep the broader intentionally" in roadmap_text
    assert "Next deliverable: P19 residual host-runtime boundary audit" in roadmap_text
    assert "The decision was to keep the broader intentionally" in roadmap_text
    assert "| T-193 | P18 | P1 | Author tests and claim updates for the next POSIX expression wave if widening is approved | T-192 | If widening is approved, failing tests and explicit `SPEC.md` target rows are checked in for the exact next operator/forms wave before implementation starts | blocked |" in roadmap_text
    assert "| T-196 | P18 | P1 | Rebaseline the public POSIX contract after the remaining gap and any approved widening land | T-191, T-192, T-195 | `SPEC.md`, `POSIX.md`, `docs/compatibility.md`, and the roadmap agree on the resulting claimed POSIX surface with no stale implied debt | blocked |" in roadmap_text
    assert "| T-197 | P19 | P0 | Author the residual host-runtime boundary audit baseline and scope | T-192 | `docs/plans/host-runtime-boundary-audit.md`, `POSIX.md`, and the roadmap make the backend-first purpose, audit scope, and required outputs explicit before new implementation decisions start | done |" in roadmap_text
    assert "| T-198 | P19 | P0 | Inventory public routes to the Python host runtime and produce the residual host-only matrix | T-197 | A checked-in matrix identifies residual host-routed forms, their claimed status, backend/inspection status, and whether they are reachable from ordinary public execution | done |" in roadmap_text
    assert "| T-192 | P18 | P0 | Decide and document whether to widen the broader unclaimed POSIX expression surface | T-191 | `SPEC.md`, `POSIX.md`, and the roadmap state clearly whether operators such as `||`, broader comparisons, arithmetic, ternary, match operators, and `in` remain intentionally unclaimed or are approved for the next implementation wave | done |" in roadmap_text
