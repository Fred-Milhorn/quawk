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

CONFORMANCE_ROOT = Path(__file__).resolve().parent / "conformance"

DOCUMENTED_GRAMMAR_SECTIONS = {
    "program",
    "item.function_def",
    "function_def",
    "function_def.param_list",
    "item.pattern_action",
    "pattern.BEGIN",
    "pattern.END",
    "pattern.expr",
    "pattern.expr_regex",
    "pattern.range",
    "action",
    "stmt_list",
    "sep.statement",
    "stmt.block",
    "stmt.if",
    "stmt.while",
    "stmt.do_while",
    "stmt.for",
    "stmt.for_in",
    "stmt.break",
    "stmt.continue",
    "stmt.next",
    "stmt.nextfile",
    "stmt.exit",
    "stmt.return",
    "stmt.delete",
    "stmt.assignment",
    "stmt.print",
    "stmt.printf",
    "stmt.expr",
    "expr_list",
    "output_redirect",
    "subscript_list",
    "lvalue.name",
    "lvalue.array",
    "lvalue.field",
    "expr.number",
    "expr.string",
    "expr.regex",
    "expr.name",
    "expr.field",
    "expr.call",
    "expr.grouped",
    "expr.assign",
    "expr.conditional",
    "expr.logical_or",
    "expr.logical_and",
    "expr.less",
    "expr.compare_other",
    "expr.equal",
    "expr.match",
    "expr.in",
    "expr.concat",
    "expr.add",
    "expr.mul",
    "expr.pow",
    "expr.unary",
    "expr.postfix",
    "disambiguation.concat",
    "disambiguation.regex_vs_division",
}

REQUIRED_GRAMMAR_SECTIONS = set(DOCUMENTED_GRAMMAR_SECTIONS)


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


def test_parser_conformance_sections_use_documented_inventory_names() -> None:
    assert REQUIRED_GRAMMAR_SECTIONS.issubset(DOCUMENTED_GRAMMAR_SECTIONS)

    used_sections = {section for case in load_conformance_cases() for section in case.grammar_sections}
    unknown_sections = sorted(used_sections.difference(DOCUMENTED_GRAMMAR_SECTIONS))
    assert not unknown_sections, f"unknown grammar section labels: {', '.join(unknown_sections)}"


def test_parser_conformance_coverage_matrix() -> None:
    coverage: dict[str, set[str]] = {}
    for case in load_conformance_cases():
        for section in case.grammar_sections:
            coverage.setdefault(section, set()).add(case.id)

    missing_sections = sorted(REQUIRED_GRAMMAR_SECTIONS.difference(coverage))
    assert not missing_sections, f"missing grammar coverage for: {', '.join(missing_sections)}"
