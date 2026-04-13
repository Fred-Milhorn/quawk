from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_backend_gap_inventory_records_the_closed_function_body_forms() -> None:
    inventory_text = (ROOT / "docs" / "plans" / "backend-gap-inventory.md").read_text(encoding="utf-8")

    assert "imperative function bodies were closed in T-267" in inventory_text
    assert "imperative function bodies that rely on concatenation or postfix increment" in inventory_text
    assert "now route through the runtime-backed backend path" in inventory_text
