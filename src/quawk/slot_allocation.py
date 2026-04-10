"""Compile-time slot allocation structures and pass helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SlotInferredType = Literal["numeric", "string", "mixed", "unknown"]
SlotStorage = Literal["slot", "hash"]

_VALID_INFERRED_TYPES: frozenset[str] = frozenset({"numeric", "string", "mixed", "unknown"})
_VALID_STORAGE: frozenset[str] = frozenset({"slot", "hash"})


@dataclass(frozen=True)
class VariableSlot:
    """Compile-time slot metadata for one variable."""

    name: str
    index: int
    inferred_type: SlotInferredType
    storage: SlotStorage

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("variable slot name must be non-empty")
        if self.index < 0:
            raise ValueError("variable slot index must be non-negative")
        if self.inferred_type not in _VALID_INFERRED_TYPES:
            raise ValueError(f"invalid slot inferred_type: {self.inferred_type}")
        if self.storage not in _VALID_STORAGE:
            raise ValueError(f"invalid slot storage: {self.storage}")


@dataclass(frozen=True)
class SlotAllocation:
    """Stable slot-allocation metadata consumed by later lowering phases."""

    slots: tuple[VariableSlot, ...]
    numeric_count: int
    string_count: int
    mixed_count: int
    state_struct_type: str

    def __post_init__(self) -> None:
        if self.numeric_count < 0 or self.string_count < 0 or self.mixed_count < 0:
            raise ValueError("slot counts must be non-negative")

        total_typed_slots = self.numeric_count + self.string_count + self.mixed_count
        if total_typed_slots > len(self.slots):
            raise ValueError("typed slot counts exceed available slots")

        if not self.state_struct_type:
            raise ValueError("state_struct_type must be non-empty")

        seen_names: set[str] = set()
        seen_indexes: set[int] = set()
        for slot in self.slots:
            if slot.name in seen_names:
                raise ValueError(f"duplicate slot name: {slot.name}")
            if slot.index in seen_indexes:
                raise ValueError(f"duplicate slot index: {slot.index}")
            seen_names.add(slot.name)
            seen_indexes.add(slot.index)

    @property
    def variable_count(self) -> int:
        """Return the number of compile-time tracked variables."""
        return len(self.slots)

    def get_slot(self, name: str) -> VariableSlot | None:
        """Return slot metadata for `name`, or `None` when unallocated."""
        for slot in self.slots:
            if slot.name == name:
                return slot
        return None


def render_slot_state_struct_type(slot_count: int, *, state_name: str = "%quawk.state") -> str:
    """Render one LLVM state type declaration for a fixed slot count."""
    if slot_count < 0:
        raise ValueError("slot_count must be non-negative")
    if slot_count == 0:
        return f"{state_name} = type {{}}"
    fields = ", ".join("double" for _ in range(slot_count))
    return f"{state_name} = type {{ {fields} }}"


def allocate_slots_for_variable_indexes(variable_indexes: dict[str, int]) -> SlotAllocation:
    """Build deterministic slot allocation metadata from stable variable indexes."""
    slots = tuple(
        VariableSlot(name=name, index=index, inferred_type="unknown", storage="slot")
        for name, index in sorted(variable_indexes.items(), key=lambda item: item[1])
    )
    return SlotAllocation(
        slots=slots,
        numeric_count=0,
        string_count=0,
        mixed_count=0,
        state_struct_type=render_slot_state_struct_type(len(slots)),
    )
