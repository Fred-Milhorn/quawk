from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t206_plan_doc_records_the_final_claimed_value_fallback_removal() -> None:
    plan_text = (ROOT / "docs" / "plans" / "claimed-value-fallback-cleanup.md").read_text(encoding="utf-8")
    matrix_text = (ROOT / "docs" / "plans" / "claimed-value-fallback-matrix.md").read_text(encoding="utf-8")

    assert "## T-206 Claimed Fallback Removal Result" in plan_text
    assert "string-valued `-v` plus the supported direct function subset now stays on the" in plan_text
    assert "with `-v x=hello` no longer routes to the host evaluator" in plan_text
    assert "That leaves `T-207` to rebaseline the broader execution-model docs" in plan_text
    assert "| String `-v` plus user-defined functions | `function f(y) { return y + 1 } BEGIN { print x; print f(1) }` | `-v x=hello` | yes | no |" in matrix_text
    assert "no representative row in this matrix now requires public host fallback." in matrix_text


def test_t206_roadmap_advances_to_execution_model_doc_rebaseline() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-197` through `T-207` are complete" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
    assert "| T-206 | P20 | P0 | Remove the remaining claimed public value fallback | T-205 | Ordinary public execution no longer routes claimed programs through the host evaluator for value semantics | done |" in roadmap_text
