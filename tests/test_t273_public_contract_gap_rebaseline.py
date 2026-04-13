from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t273_spec_and_design_name_the_remaining_product_gaps_explicitly() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")

    assert "| Backend parity for broader frontend-admitted POSIX forms | partial | The remaining product-side forms outside the current AOT-backed contract are explicit:" in spec_text
    assert "Parenthesized array-target wrappers" in spec_text
    assert "Substitution targets" in spec_text
    assert "builtin names beyond the current claimed subset are intentionally out of contract" in spec_text
    assert "compound assignment expressions" in spec_text
    assert "named explicitly rather than left as vague \"broader corners\"" in design_text
    assert "parenthesized array-name wrappers in `for ... in`, `expr in array`, and `split()` target positions" in design_text
    assert "substitution targets on scalar variables, fields, and multi-subscript array elements" in design_text
    assert "compound assignment expressions" in design_text
    assert "the T-278 re-audit confirmed that the only remaining product-side forms outside the contract are the explicit top-level-item and builtin-name exclusions above" in design_text


def test_t273_roadmap_records_the_contract_rebaseline() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-273 | P31 | P0 | Rebaseline the public contract for the remaining product-side gaps | T-272 | `SPEC.md`, `docs/design.md`, and the roadmap name the remaining product gaps explicitly instead of relying on vague “broader corners” wording | done |" in roadmap_text
    assert "`T-273` rebaselines the public contract docs so `SPEC.md`," in roadmap_text
    assert "| T-274 | P31 | P0 | Compound assignment end to end through public execution and inspection | T-272 | Representative `+=`, `-=`, `*=`, `/=`, `%=` and `^=` programs execute through the backend/runtime path and inspect cleanly | done |" in roadmap_text
    assert "| T-275 | P31 | P0 | Parenthesized array-target wrappers end to end through public execution and inspection | T-272 | Representative parenthesized `for ... in`, `expr in array`, and `split()` target wrapper programs execute through the backend/runtime path and inspect cleanly | done |" in roadmap_text
    assert "| T-276 | P31 | P0 | Close substitution-target lvalue gaps and classify builtin names | T-272, T-275 | Representative `sub()` / `gsub()` programs over scalar variables, fields, and multi-subscript array lvalues execute correctly, while builtin names beyond the current subset are documented as intentionally out of contract | done |" in roadmap_text
    assert "| T-278 | P31 | P1 | Re-audit the remaining product-side admitted surface after the closure wave | T-274, T-275, T-276, T-277 | Contract docs, backend gap inventory, and direct tests agree that the only remaining product-side gaps are the explicit builtin-name and top-level-item exclusions | done |" in roadmap_text
