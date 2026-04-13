from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t272_spec_records_the_remaining_product_and_corroboration_gaps() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Remaining parser-admitted execution gaps | planned |" in spec_text
    assert "compound assignment expressions" in spec_text
    assert "Parenthesized array-target wrappers" in spec_text
    assert "Substitution targets" in spec_text
    assert "builtin names beyond the current claimed subset are intentionally out of contract" in spec_text
    assert "retirement of the narrow direct-function execution lane" in spec_text
    assert "| Remaining POSIX compatibility corroboration gaps | planned |" in spec_text
    assert "field-rebuild corroborating anchors" in spec_text
    assert "record-target `gsub` skip" in spec_text
    assert "`rand()` corroboration" in spec_text


def test_t272_plan_and_roadmap_define_follow_on_phases_and_tasks() -> None:
    plan_text = (ROOT / "docs" / "plans" / "remaining-posix-compatibility-plan.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "## Product Gaps" in plan_text
    assert "## T-272 Baseline Result" in plan_text
    assert "## T-274 Result" in plan_text
    assert "## T-275 Result" in plan_text
    assert "## T-276 Result" in plan_text
    assert "## Compatibility Corroboration Gaps" in plan_text
    assert "Compound assignment | implemented | POSIX-required, closed by `T-274`" in plan_text
    assert "Parenthesized array-target wrappers for `for ... in`, `expr in array`, and `split()`" in plan_text
    assert "`sub()` / `gsub()` array-element lvalues beyond the current admitted subset" in plan_text
    assert "builtin names beyond the current claimed subset are not part of the product-side contract" in plan_text
    assert "Narrow direct-function execution lane" in plan_text
    assert "Field-rebuild corroboration re-audit" in plan_text
    assert "Record-target `gsub` reviewed skip" in plan_text
    assert "`rand()` corroboration strategy" in plan_text

    assert "### P31: Remaining POSIX Contract Closure" in roadmap_text
    assert "### P32: Final POSIX Compatibility Corroboration" in roadmap_text
    assert "| T-272 | P31 | P0 | Author the remaining product-side POSIX gap inventory and classification baseline | T-271 |" in roadmap_text
    assert "| T-272 | P31 | P0 | Author the remaining product-side POSIX gap inventory and classification baseline | T-271 | `SPEC.md`, the roadmap, and a checked-in plan explicitly classify compound assignment, non-name array-target forms, broader substitution targets, extra builtin names, top-level item shapes, and the direct-function lane before implementation choices start | done |" in roadmap_text
    assert "| T-273 | P31 | P0 | Rebaseline the public contract for the remaining product-side gaps | T-272 | `SPEC.md`, `docs/design.md`, and the roadmap name the remaining product gaps explicitly instead of relying on vague “broader corners” wording | done |" in roadmap_text
    assert "| T-274 | P31 | P0 | Compound assignment end to end through public execution and inspection | T-272 | Representative `+=`, `-=`, `*=`, `/=`, `%=` and `^=` programs execute through the backend/runtime path and inspect cleanly | done |" in roadmap_text
    assert "| T-275 | P31 | P0 | Parenthesized array-target wrappers end to end through public execution and inspection | T-272 | Representative parenthesized `for ... in`, `expr in array`, and `split()` target wrapper programs execute through the backend/runtime path and inspect cleanly | done |" in roadmap_text
    assert "| T-276 | P31 | P0 | Close substitution-target lvalue gaps and classify builtin names | T-272, T-275 | Representative `sub()` / `gsub()` programs over scalar variables, fields, and multi-subscript array lvalues execute correctly, while builtin names beyond the current subset are documented as intentionally out of contract | done |" in roadmap_text
    assert "| T-279 | P32 | P0 | Author the remaining POSIX corroboration-gap baseline | T-278 |" in roadmap_text
    assert "| T-283 | P32 | P0 | Complete the final POSIX end-to-end compatibility audit | T-280, T-281, T-282 |" in roadmap_text
