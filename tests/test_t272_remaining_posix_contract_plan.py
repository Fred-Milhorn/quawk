from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t272_spec_records_the_remaining_product_and_corroboration_gaps() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Remaining parser-admitted execution gaps | planned |" in spec_text
    assert "compound assignment" in spec_text
    assert "non-name iterable or RHS forms for `for ... in` and `in`" in spec_text
    assert "non-name `split()` targets" in spec_text
    assert "broader `sub()` / `gsub()` target shapes" in spec_text
    assert "builtin names beyond the current claimed subset" in spec_text
    assert "top-level items outside `PatternAction` / `FunctionDef`" in spec_text
    assert "narrow direct-function execution lane" in spec_text
    assert "| Remaining POSIX compatibility corroboration gaps | planned |" in spec_text
    assert "field-rebuild corroborating anchors" in spec_text
    assert "record-target `gsub` skip" in spec_text
    assert "`rand()` corroboration" in spec_text


def test_t272_plan_and_roadmap_define_follow_on_phases_and_tasks() -> None:
    plan_text = (ROOT / "docs" / "plans" / "remaining-posix-compatibility-plan.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "## Product Gaps" in plan_text
    assert "## Compatibility Corroboration Gaps" in plan_text
    assert "Compound assignment" in plan_text
    assert "Non-name `split()` targets" in plan_text
    assert "Narrow direct-function execution lane" in plan_text
    assert "Field-rebuild corroboration re-audit" in plan_text
    assert "Record-target `gsub` reviewed skip" in plan_text
    assert "`rand()` corroboration strategy" in plan_text

    assert "### P31: Remaining POSIX Contract Closure" in roadmap_text
    assert "### P32: Final POSIX Compatibility Corroboration" in roadmap_text
    assert "| T-272 | P31 | P0 | Author the remaining product-side POSIX gap inventory and classification baseline | T-271 |" in roadmap_text
    assert "| T-274 | P31 | P0 | Implement compound assignment end to end through public execution and inspection | T-272 |" in roadmap_text
    assert "| T-279 | P32 | P0 | Author the remaining POSIX corroboration-gap baseline | T-278 |" in roadmap_text
    assert "| T-283 | P32 | P0 | Complete the final POSIX end-to-end compatibility audit | T-280, T-281, T-282 |" in roadmap_text
