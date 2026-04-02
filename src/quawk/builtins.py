"""Builtin-function metadata for the currently supported subset."""

from __future__ import annotations

BUILTIN_FUNCTION_NAMES = frozenset({"length", "split", "substr"})
BUILTIN_VARIABLE_NAMES = frozenset({"NR", "FNR", "NF", "FILENAME", "OFS", "ORS"})

BUILTIN_ARITY_RULES: dict[str, tuple[int, ...]] = {
    "length": (0, 1),
    "split": (2, 3),
    "substr": (2, 3),
}


def is_builtin_function_name(name: str) -> bool:
    """Report whether `name` is a supported builtin in the current subset."""
    return name in BUILTIN_FUNCTION_NAMES


def is_builtin_variable_name(name: str) -> bool:
    """Report whether `name` is a supported builtin variable in the current subset."""
    return name in BUILTIN_VARIABLE_NAMES


def builtin_accepts_arity(name: str, arg_count: int) -> bool:
    """Report whether one builtin accepts the supplied argument count."""
    allowed = BUILTIN_ARITY_RULES.get(name)
    if allowed is None:
        return False
    return arg_count in allowed
