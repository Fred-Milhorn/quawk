"""Compile-time type lattice and join operation for AWK value inference."""

from __future__ import annotations

from enum import Enum


class LatticeType(Enum):
    """Type lattice elements for AWK value inference.

    Lattice ordering (join semilattice)::

            MIXED
           /      \\
      NUMERIC    STRING
           \\      /
            UNKNOWN (bottom, no observed value yet)
    """

    UNKNOWN = "unknown"
    NUMERIC = "numeric"
    STRING = "string"
    MIXED = "mixed"

    def __str__(self) -> str:  # pragma: no cover
        return self.value


def join(left: LatticeType, right: LatticeType) -> LatticeType:
    """Return the least upper bound of two lattice types.

    Rules:
    - identical types: that type
    - either is UNKNOWN: the other type (identity element)
    - NUMERIC joined with STRING: MIXED
    - any involving MIXED: MIXED
    """
    if left is right:
        return left
    if left is LatticeType.UNKNOWN:
        return right
    if right is LatticeType.UNKNOWN:
        return left
    return LatticeType.MIXED


def can_be_numeric(t: LatticeType) -> bool:
    """Return whether a value of type *t* may hold a numeric value."""
    return t is LatticeType.UNKNOWN or t is LatticeType.NUMERIC or t is LatticeType.MIXED


def can_be_string(t: LatticeType) -> bool:
    """Return whether a value of type *t* may hold a string value."""
    return t is LatticeType.UNKNOWN or t is LatticeType.STRING or t is LatticeType.MIXED


def join_all(types: list[LatticeType] | tuple[LatticeType, ...]) -> LatticeType:
    """Fold *join* over a sequence of lattice types, returning UNKNOWN for an empty sequence."""
    result = LatticeType.UNKNOWN
    for t in types:
        result = join(result, t)
    return result
