from __future__ import annotations

from dataclasses import dataclass, field

from ..ast import FunctionDef
from ..slot_allocation import SlotAllocation
from ..type_inference import LatticeType


@dataclass
class LoweringState:
    """Mutable state for lowering one program into LLVM IR text."""

    globals: list[str] = field(default_factory=list)
    allocas: list[str] = field(default_factory=list)
    entry_instructions: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    temp_index: int = 0
    label_index: int = 0
    string_index: int = 0
    variable_slots: dict[str, str] = field(default_factory=dict)
    uses_puts: bool = False
    uses_printf: bool = False
    numeric_format_declared: bool = False
    runtime_param: str | None = None
    state_param: str | None = None
    variable_indexes: dict[str, int] = field(default_factory=dict)
    slot_allocation: SlotAllocation | None = None
    type_info: dict[str, LatticeType] = field(default_factory=dict)
    action_exit_label: str | None = None
    phase_exit_label: str | None = None
    break_label: str | None = None
    continue_label: str | None = None
    array_names: frozenset[str] = field(default_factory=frozenset)
    loop_string_bindings: dict[str, str] = field(default_factory=dict)
    function_defs: dict[str, FunctionDef] = field(default_factory=dict)
    return_slot: str | None = None
    return_string_slot: str | None = None
    return_label: str | None = None
    initial_string_values: dict[str, str] = field(default_factory=dict)
    local_names: frozenset[str] = field(default_factory=frozenset)
    function_param_strings: dict[str, str] = field(default_factory=dict)
    local_numeric_names: frozenset[str] = field(default_factory=frozenset)

    def next_temp(self, prefix: str) -> str:
        """Return a fresh SSA temporary name with the given prefix."""
        name = f"%{prefix}.{self.temp_index}"
        self.temp_index += 1
        return name

    def next_label(self, prefix: str) -> str:
        """Return a fresh LLVM basic-block label name."""
        name = f"{prefix}.{self.label_index}"
        self.label_index += 1
        return name


InitialVariableValue = float | str
InitialVariables = list[tuple[str, InitialVariableValue]]
