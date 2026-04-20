from __future__ import annotations

from .runtime_abi import emit_gep, emit_gep_constant, emit_gep_inline
from .state import LoweringState


class LLVMIRBuilder:
    """Lightweight helper for recurring LLVM text emission during lowering."""

    def __init__(self, state: LoweringState) -> None:
        self.state = state

    def temp(self, prefix: str) -> str:
        """Return a fresh SSA temporary name."""
        return self.state.next_temp(prefix)

    def label(self, prefix: str) -> str:
        """Return a fresh basic-block label name."""
        return self.state.next_label(prefix)

    def emit(self, instruction: str) -> None:
        """Append one already-formatted instruction line."""
        self.state.instructions.append(instruction)

    def emit_many(self, instructions: list[str]) -> None:
        """Append several already-formatted instruction lines."""
        self.state.instructions.extend(instructions)

    def mark_label(self, label: str) -> None:
        """Append one basic-block label line."""
        self.emit(f"{label}:")

    def branch(self, target: str) -> None:
        """Emit one unconditional branch."""
        self.emit(f"  br label %{target}")

    def cond_branch(self, condition: str, true_label: str, false_label: str) -> None:
        """Emit one conditional branch."""
        self.emit(f"  br i1 {condition}, label %{true_label}, label %{false_label}")

    def call(self, prefix: str, return_type: str, callee: str, args: list[str]) -> str:
        """Emit one call that returns a value and return the fresh result temp."""
        result = self.temp(prefix)
        self.emit(f"  {result} = call {return_type} {callee}({', '.join(args)})")
        return result

    def call_void(self, callee: str, args: list[str]) -> None:
        """Emit one void call."""
        self.emit(f"  call void {callee}({', '.join(args)})")

    def load(self, prefix: str, value_type: str, pointer: str) -> str:
        """Emit one load and return the result temp."""
        result = self.temp(prefix)
        self.emit(f"  {result} = load {value_type}, ptr {pointer}")
        return result

    def store(self, value_type: str, value: str, pointer: str) -> None:
        """Emit one store."""
        self.emit(f"  store {value_type} {value}, ptr {pointer}")

    def binop(self, prefix: str, opcode: str, value_type: str, left: str, right: str) -> str:
        """Emit one binary operation and return the result temp."""
        result = self.temp(prefix)
        self.emit(f"  {result} = {opcode} {value_type} {left}, {right}")
        return result

    def select(self, prefix: str, condition: str, value_type: str, if_true: str, if_false: str) -> str:
        """Emit one select instruction and return the result temp."""
        result = self.temp(prefix)
        self.emit(f"  {result} = select i1 {condition}, {value_type} {if_true}, {value_type} {if_false}")
        return result

    def phi(self, prefix: str, value_type: str, incomings: list[tuple[str, str]]) -> str:
        """Emit one phi instruction and return the result temp."""
        result = self.temp(prefix)
        incoming_text = ", ".join(f"[ {value}, %{label} ]" for value, label in incomings)
        self.emit(f"  {result} = phi {value_type} {incoming_text}")
        return result

    def gep(self, prefix: str, byte_length: int, global_name: str) -> str:
        """Emit one GEP from the start of a global byte array and return the result temp."""
        result = self.temp(prefix)
        self.emit(emit_gep(result, byte_length, global_name))
        return result

    def inline_gep(self, byte_length: int, global_name: str) -> str:
        """Render one inline GEP expression from the start of a global byte array."""
        return emit_gep_inline(byte_length, global_name)

    def constant_gep(self, byte_length: int, global_name: str) -> str:
        """Render one constant-expression GEP from the start of a global byte array."""
        return emit_gep_constant(byte_length, global_name)
