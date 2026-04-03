"""Builtin-function metadata for the currently supported subset."""

from __future__ import annotations

BUILTIN_FUNCTION_NAMES = frozenset(
    {
        "atan2",
        "close",
        "cos",
        "exp",
        "gsub",
        "index",
        "int",
        "length",
        "log",
        "match",
        "rand",
        "sin",
        "split",
        "sqrt",
        "srand",
        "sprintf",
        "sub",
        "substr",
        "system",
        "tolower",
        "toupper",
    }
)
BUILTIN_VARIABLE_NAMES = frozenset(
    {
        "ARGC",
        "CONVFMT",
        "FILENAME",
        "FNR",
        "NF",
        "NR",
        "OFMT",
        "OFS",
        "ORS",
        "RLENGTH",
        "RSTART",
        "SUBSEP",
    }
)
BUILTIN_ARRAY_NAMES = frozenset({"ARGV", "ENVIRON"})

BUILTIN_ARITY_RULES: dict[str, tuple[int, ...]] = {
    "atan2": (2,),
    "close": (1,),
    "cos": (1,),
    "exp": (1,),
    "gsub": (2, 3),
    "index": (2,),
    "int": (1,),
    "length": (0, 1),
    "log": (1,),
    "match": (2,),
    "rand": (0,),
    "sin": (1,),
    "split": (2, 3),
    "sqrt": (1,),
    "srand": (0, 1),
    "sub": (2, 3),
    "substr": (2, 3),
    "system": (1,),
    "tolower": (1,),
    "toupper": (1,),
}


def is_builtin_function_name(name: str) -> bool:
    """Report whether `name` is a supported builtin in the current subset."""
    return name in BUILTIN_FUNCTION_NAMES


def is_builtin_variable_name(name: str) -> bool:
    """Report whether `name` is a supported builtin variable in the current subset."""
    return name in BUILTIN_VARIABLE_NAMES


def is_builtin_array_name(name: str) -> bool:
    """Report whether `name` is a supported builtin array in the current subset."""
    return name in BUILTIN_ARRAY_NAMES


def builtin_accepts_arity(name: str, arg_count: int) -> bool:
    """Report whether one builtin accepts the supplied argument count."""
    if name == "sprintf":
        return arg_count >= 1
    allowed = BUILTIN_ARITY_RULES.get(name)
    if allowed is None:
        return False
    return arg_count in allowed
