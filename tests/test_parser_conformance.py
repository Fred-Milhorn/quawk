# File-backed parser conformance tests.
# These fixtures map supported programs to the grammar sections they exercise,
# so parser coverage stays visible as the supported subset grows.

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from quawk.lexer import lex
from quawk.parser import parse
from quawk.source import ProgramSource

CONFORMANCE_ROOT = Path(__file__).resolve().parent / "parser_conformance"

REQUIRED_GRAMMAR_SECTIONS = {
    "program",
    "item.pattern_action",
    "pattern.BEGIN",
    "pattern.END",
    "pattern.expr_regex",
    "action",
    "stmt.print",
    "stmt.assignment",
    "stmt.if",
    "stmt.while",
    "expr.string",
    "expr.number",
    "expr.name",
    "expr.field",
    "expr.add",
    "expr.less",
    "expr.equal",
    "expr.logical_and",
    "expr.grouped",
}


@dataclass(frozen=True)
class ParserConformanceCase:
    """One file-backed parser conformance case."""

    id: str
    description: str
    grammar_sections: tuple[str, ...]
    program_path: Path


def load_conformance_cases() -> list[ParserConformanceCase]:
    """Load all parser conformance manifests in deterministic order."""
    cases: list[ParserConformanceCase] = []
    for manifest_path in sorted(CONFORMANCE_ROOT.glob("*.toml")):
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        program_name = manifest.get("program")
        grammar_sections = manifest.get("grammar_sections")
        if not isinstance(program_name, str):
            raise ValueError(f"{manifest_path}: missing string field 'program'")
        if not isinstance(grammar_sections, list) or not all(isinstance(item, str) for item in grammar_sections):
            raise ValueError(f"{manifest_path}: invalid 'grammar_sections' list")
        cases.append(
            ParserConformanceCase(
                id=str(manifest["id"]),
                description=str(manifest["description"]),
                grammar_sections=tuple(grammar_sections),
                program_path=manifest_path.with_name(program_name),
            )
        )
    return cases


@pytest.mark.parametrize("case", load_conformance_cases(), ids=lambda case: case.id)
def test_parser_conformance_case(case: ParserConformanceCase) -> None:
    source = ProgramSource.from_inline(case.program_path.read_text(encoding="utf-8"), name=case.program_path.name)
    program = parse(lex(source))

    assert program.items, case.description


def test_parser_conformance_coverage_matrix() -> None:
    coverage: dict[str, set[str]] = {}
    for case in load_conformance_cases():
        for section in case.grammar_sections:
            coverage.setdefault(section, set()).add(case.id)

    missing_sections = sorted(REQUIRED_GRAMMAR_SECTIONS.difference(coverage))
    assert not missing_sections, f"missing grammar coverage for: {', '.join(missing_sections)}"
