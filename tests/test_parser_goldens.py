# File-backed parser golden tests.
# These cases pin selected `format_program()` outputs where a full AST snapshot
# is more reviewable than a handful of node-shape assertions.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from quawk.lexer import lex
from quawk.parser import format_program, parse
from quawk.source import ProgramSource

GOLDEN_ROOT = Path(__file__).resolve().parent / "parser_goldens"


@dataclass(frozen=True)
class ParserGoldenCase:
    """One parser golden case with program input and expected AST rendering."""

    id: str
    program_path: Path
    expected_path: Path


def load_golden_cases() -> list[ParserGoldenCase]:
    """Load parser golden cases in deterministic filename order."""
    cases: list[ParserGoldenCase] = []
    for program_path in sorted(GOLDEN_ROOT.glob("*.awk")):
        expected_path = program_path.with_suffix(".ast")
        if not expected_path.exists():
            raise ValueError(f"missing golden output for {program_path.name}: {expected_path.name}")
        cases.append(
            ParserGoldenCase(
                id=program_path.stem,
                program_path=program_path,
                expected_path=expected_path,
            )
        )
    return cases


@pytest.mark.parametrize("case", load_golden_cases(), ids=lambda case: case.id)
def test_parser_golden(case: ParserGoldenCase) -> None:
    source_text = case.program_path.read_text(encoding="utf-8")
    source = ProgramSource.from_inline(source_text, name=case.program_path.name)
    program = parse(lex(source))

    assert format_program(program) == case.expected_path.read_text(encoding="utf-8")
