from __future__ import annotations

from quawk.jit import LoweringState, runtime_name_slot_index, runtime_slot_indexes
from quawk.slot_allocation import SlotAllocation, VariableSlot, render_slot_state_struct_type


def test_runtime_name_slot_index_honors_slot_storage_metadata() -> None:
    allocation = SlotAllocation(
        slots=(
            VariableSlot(name="x", index=0, inferred_type="unknown", storage="slot"),
            VariableSlot(name="y", index=1, inferred_type="unknown", storage="hash"),
            VariableSlot(name="ARGC", index=2, inferred_type="unknown", storage="slot"),
            VariableSlot(name="__range.0", index=3, inferred_type="unknown", storage="slot"),
        ),
        numeric_count=0,
        string_count=0,
        mixed_count=0,
        state_struct_type=render_slot_state_struct_type(4),
    )
    state = LoweringState(
        variable_indexes={"x": 0, "y": 1, "ARGC": 2, "__range.0": 3},
        slot_allocation=allocation,
    )

    assert runtime_name_slot_index("x", state) == 0
    assert runtime_name_slot_index("y", state) is None
    assert runtime_name_slot_index("ARGC", state) is None
    assert runtime_name_slot_index("__range.0", state) is None


def test_runtime_slot_indexes_filter_hash_builtin_and_range_entries() -> None:
    variable_indexes = {"x": 0, "y": 1, "ARGC": 2, "__range.0": 3}
    allocation = SlotAllocation(
        slots=(
            VariableSlot(name="x", index=0, inferred_type="unknown", storage="slot"),
            VariableSlot(name="y", index=1, inferred_type="unknown", storage="hash"),
            VariableSlot(name="ARGC", index=2, inferred_type="unknown", storage="slot"),
            VariableSlot(name="__range.0", index=3, inferred_type="unknown", storage="slot"),
        ),
        numeric_count=0,
        string_count=0,
        mixed_count=0,
        state_struct_type=render_slot_state_struct_type(4),
    )

    assert runtime_slot_indexes(variable_indexes, allocation) == {"x": 0}


def test_runtime_name_slot_index_falls_back_to_variable_indexes_without_metadata() -> None:
    state = LoweringState(variable_indexes={"x": 0, "ARGC": 1})

    assert runtime_name_slot_index("x", state) == 0
    assert runtime_name_slot_index("ARGC", state) is None
