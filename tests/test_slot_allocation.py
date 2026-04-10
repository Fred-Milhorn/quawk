from __future__ import annotations

import pytest

from quawk.slot_allocation import SlotAllocation, VariableSlot


def test_variable_slot_keeps_the_declared_metadata() -> None:
    slot = VariableSlot(name="x", index=0, inferred_type="numeric", storage="slot")

    assert slot.name == "x"
    assert slot.index == 0
    assert slot.inferred_type == "numeric"
    assert slot.storage == "slot"


def test_slot_allocation_get_slot_by_name() -> None:
    allocation = SlotAllocation(
        slots=(
            VariableSlot(name="i", index=0, inferred_type="numeric", storage="slot"),
            VariableSlot(name="msg", index=1, inferred_type="string", storage="slot"),
        ),
        numeric_count=1,
        string_count=1,
        mixed_count=0,
        state_struct_type="%quawk.state = type { double, ptr }",
    )

    assert allocation.variable_count == 2
    assert allocation.get_slot("i") == VariableSlot(name="i", index=0, inferred_type="numeric", storage="slot")
    assert allocation.get_slot("missing") is None


def test_slot_allocation_rejects_duplicate_slot_names() -> None:
    with pytest.raises(ValueError, match="duplicate slot name"):
        SlotAllocation(
            slots=(
                VariableSlot(name="x", index=0, inferred_type="numeric", storage="slot"),
                VariableSlot(name="x", index=1, inferred_type="mixed", storage="hash"),
            ),
            numeric_count=1,
            string_count=0,
            mixed_count=1,
            state_struct_type="%quawk.state = type { double, ptr }",
        )


def test_slot_allocation_rejects_typed_counts_larger_than_slots() -> None:
    with pytest.raises(ValueError, match="typed slot counts exceed available slots"):
        SlotAllocation(
            slots=(VariableSlot(name="x", index=0, inferred_type="numeric", storage="slot"),),
            numeric_count=1,
            string_count=1,
            mixed_count=0,
            state_struct_type="%quawk.state = type { double }",
        )
