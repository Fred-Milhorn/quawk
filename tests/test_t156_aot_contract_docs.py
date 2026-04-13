from __future__ import annotations

from pathlib import Path

from quawk import architecture_audit

ROOT = Path(__file__).resolve().parent.parent


def test_t156_architecture_audit_is_clean() -> None:
    assert architecture_audit.families_lacking_full_backend_support() == []


def test_t156_spec_rebaselines_the_claimed_aot_contract() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| `--ir` / `--asm` | partial | Supported for every currently claimed AOT-backed family." in spec_text
    assert "| Expressions | partial | The currently claimed AOT-backed subset includes" in spec_text
    assert "| Backend parity for every claimed execution path | implemented |" in spec_text
    assert "ordinary public execution no longer uses host fallback for claimed behavior" in spec_text
    assert "some claimed language families are not lowered yet" not in spec_text


def test_t156_design_doc_states_claimed_behavior_is_backend_only() -> None:
    design_text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")

    assert "every currently claimed execution family to have a compiled backend/runtime path" in design_text
    assert "no longer keeps host fallback for representative unclaimed host-runtime-only forms" in design_text
    assert "temporary host-runtime execution remains in a few language families" not in design_text
    assert "parenthesized array-name wrappers in `for ... in`, `expr in array`, and `split()` target positions" in design_text
