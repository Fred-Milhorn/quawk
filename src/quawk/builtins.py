"""Builtin-function metadata for the currently supported subset."""

from __future__ import annotations

BUILTIN_FUNCTION_NAMES = frozenset({"length"})


def is_builtin_function_name(name: str) -> bool:
    """Report whether `name` is a supported builtin in the current subset."""
    return name in BUILTIN_FUNCTION_NAMES
