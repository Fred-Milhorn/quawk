from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t273_spec_and_design_name_the_remaining_product_gaps_explicitly() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")

    assert "| Backend parity for broader frontend-admitted POSIX forms | partial | The remaining product-side forms outside the current AOT-backed contract are explicit:" in spec_text
    assert "compound assignment; parser-admitted non-name iterable or RHS forms for `for ... in` and `in`; non-name `split()` targets" in spec_text
    assert "named explicitly rather than left as vague \"broader corners\"" in design_text
    assert "compound assignment; non-name iterable or RHS forms for `for ... in` and `in`; non-name `split()` targets" in design_text
    assert "the remaining unclaimed product-side forms that can still fail inspection are the explicit T-272 list above" in design_text


def test_t273_roadmap_records_the_contract_rebaseline() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`T-274`: implement compound assignment end to end through public execution" in roadmap_text
    assert "| T-273 | P31 | P0 | Rebaseline the public contract for the remaining product-side gaps | T-272 | `SPEC.md`, `docs/design.md`, and the roadmap name the remaining product gaps explicitly instead of relying on vague “broader corners” wording | done |" in roadmap_text
    assert "`T-273` rebaselines the public contract docs so `SPEC.md`," in roadmap_text
