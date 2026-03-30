"""Adapt and execute the selected upstream compatibility slice."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from quawk.corpus import (
    DEFAULT_DIFFERENTIAL_ENGINES,
    CorpusResult,
    DifferentialStatus,
    EngineName,
    NormalizedCorpusResult,
    build_engine_command,
    missing_engines,
    normalize_result,
)
from quawk.upstream_inventory import UpstreamCaseSelection, load_upstream_selection_manifest, selections_with_status

UpstreamOracleKind = Literal["expected-output", "reference-agreement"]


@dataclass(frozen=True)
class UpstreamExpectation:
    """Expected normalized output for one upstream-derived case."""

    returncode: int
    stdout: str
    stderr: str

    def comparable_fields(self) -> tuple[int, str, str]:
        """Return the normalized fields used for deterministic comparison."""
        return (self.returncode, self.stdout, self.stderr)


@dataclass(frozen=True)
class UpstreamCase:
    """One executable upstream-selected compatibility case."""

    selection: UpstreamCaseSelection
    program_path: Path
    cli_args: tuple[str, ...]
    input_operands: tuple[str, ...]
    oracle: UpstreamOracleKind
    expectation: UpstreamExpectation | None

    @property
    def id(self) -> str:
        """Return a stable suite-prefixed case identifier."""
        return f"{self.selection.suite}:{self.selection.case_id}"


@dataclass(frozen=True)
class UpstreamCaseResult:
    """Differential execution result for one upstream-selected case."""

    case: UpstreamCase
    results_by_engine: dict[EngineName, NormalizedCorpusResult]
    missing_engines: tuple[EngineName, ...] = ()

    def reference_results(self) -> tuple[NormalizedCorpusResult, NormalizedCorpusResult]:
        """Return the normalized reference-engine results."""
        return (self.results_by_engine["one-true-awk"], self.results_by_engine["gawk-posix"])

    def references_agree(self) -> bool:
        """Report whether the pinned reference engines agree exactly."""
        if self.missing_engines:
            return False
        left, right = self.reference_results()
        return left.comparable_fields() == right.comparable_fields()

    def engine_matches_expectation(self, engine: EngineName) -> bool:
        """Report whether one engine matches the fixture-backed expectation."""
        expectation = self.case.expectation
        if expectation is None:
            raise ValueError(f"{self.case.id}: expected-output oracle is missing fixture expectations")
        return self.results_by_engine[engine].comparable_fields() == expectation.comparable_fields()

    def quawk_matches_references(self) -> bool:
        """Report whether `quawk` matches the agreeing reference result."""
        if not self.references_agree():
            return False
        reference_result, _ = self.reference_results()
        return self.results_by_engine["quawk"].comparable_fields() == reference_result.comparable_fields()

    def status(self) -> DifferentialStatus:
        """Return the comparison status for this upstream-derived run."""
        if self.missing_engines:
            return "SKIP"
        if self.case.oracle == "reference-agreement":
            if not self.references_agree():
                return "REF-DISAGREE"
            if self.quawk_matches_references():
                return "PASS"
            return "FAIL"

        if all(self.engine_matches_expectation(engine) for engine in DEFAULT_DIFFERENTIAL_ENGINES):
            return "PASS"
        return "FAIL"

    def detail_lines(self) -> list[str]:
        """Return human-readable detail lines for reporting or pytest failures."""
        if self.missing_engines:
            missing = ", ".join(self.missing_engines)
            return [f"missing engines: {missing}"]

        lines: list[str] = []
        expectation = self.case.expectation
        if expectation is not None:
            lines.append(
                "expected: "
                f"exit={expectation.returncode} stdout={expectation.stdout!r} stderr={expectation.stderr!r}"
            )

        for engine in DEFAULT_DIFFERENTIAL_ENGINES:
            result = self.results_by_engine[engine]
            lines.append(f"{engine}: exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")
            lines.append(f"{engine}: command={' '.join(result.command)}")
        return lines


def selected_upstream_cases() -> list[UpstreamCase]:
    """Load the checked-in runnable upstream-selected compatibility slice."""
    selections = load_upstream_selection_manifest()
    return [load_upstream_case(selection) for selection in selections_with_status("run", selections)]


def load_upstream_case(selection: UpstreamCaseSelection) -> UpstreamCase:
    """Adapt one checked-in upstream selection entry into an executable case."""
    match selection.adapter:
        case "onetrueawk-program-file":
            return load_onetrueawk_program_file(selection)
        case "gawk-awk-ok":
            return load_gawk_awk_ok(selection)
        case "gawk-awk-in-ok":
            return load_gawk_awk_in_ok(selection)
        case unsupported:
            raise ValueError(f"{selection.case_id}: unsupported upstream adapter for execution slice: {unsupported}")


def load_onetrueawk_program_file(selection: UpstreamCaseSelection) -> UpstreamCase:
    """Adapt one `Compare.t` or `Compare.p` style One True Awk program file."""
    fixture_dir = selection.path.parent
    case_name = selection.path.name

    if case_name.startswith("p."):
        input_operands = (
            str(fixture_dir / "test.countries"),
            str(fixture_dir / "test.countries"),
        )
    elif case_name.startswith("t."):
        input_operands = (str(fixture_dir / "test.data"),)
    else:
        raise ValueError(f"{selection.case_id}: unsupported one-true-awk program-file naming convention")

    return UpstreamCase(
        selection=selection,
        program_path=selection.path,
        cli_args=(),
        input_operands=input_operands,
        oracle="reference-agreement",
        expectation=None,
    )


def load_gawk_awk_ok(selection: UpstreamCaseSelection) -> UpstreamCase:
    """Adapt one gawk `.awk` + `.ok` fixture pair."""
    return UpstreamCase(
        selection=selection,
        program_path=selection.path,
        cli_args=(),
        input_operands=(),
        oracle="expected-output",
        expectation=gawk_fixture_expectation(selection.path),
    )


def load_gawk_awk_in_ok(selection: UpstreamCaseSelection) -> UpstreamCase:
    """Adapt one gawk `.awk` + `.in` + `.ok` fixture triple."""
    return UpstreamCase(
        selection=selection,
        program_path=selection.path,
        cli_args=(),
        input_operands=(str(require_sibling_file(selection.path, ".in")),),
        oracle="expected-output",
        expectation=gawk_fixture_expectation(selection.path),
    )


def gawk_fixture_expectation(program_path: Path) -> UpstreamExpectation:
    """Load the expected result from the companion gawk fixture files."""
    ok_path = require_sibling_file(program_path, ".ok")
    return UpstreamExpectation(
        returncode=0,
        stdout=ok_path.read_text(encoding="utf-8").replace("\r\n", "\n"),
        stderr="",
    )


def require_sibling_file(program_path: Path, suffix: str) -> Path:
    """Return one required sibling file next to an upstream program fixture."""
    sibling_path = program_path.with_suffix(suffix)
    if not sibling_path.is_file():
        raise ValueError(f"{program_path}: missing companion fixture {sibling_path.name}")
    return sibling_path


def run_upstream_case(case: UpstreamCase, engine: EngineName = "quawk") -> NormalizedCorpusResult:
    """Run one upstream-selected case under the selected engine."""
    command = build_engine_command(
        engine,
        case.program_path,
        cli_args=case.cli_args,
        input_operands=case.input_operands,
    )
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    return normalize_result(
        CorpusResult(
            engine=engine,
            command=tuple(command),
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    )


def run_upstream_case_for_engines(
    case: UpstreamCase,
    engines: tuple[EngineName, ...] = DEFAULT_DIFFERENTIAL_ENGINES,
) -> dict[EngineName, NormalizedCorpusResult]:
    """Run one upstream-selected case under each requested engine exactly once."""
    return {engine: run_upstream_case(case, engine=engine) for engine in engines}


def run_upstream_case_differential(
    case: UpstreamCase,
    engines: tuple[EngineName, ...] = DEFAULT_DIFFERENTIAL_ENGINES,
) -> UpstreamCaseResult:
    """Run one upstream-selected case under all differential engines and compare them."""
    missing = missing_engines(engines)
    if missing:
        return UpstreamCaseResult(case=case, results_by_engine={}, missing_engines=missing)
    return UpstreamCaseResult(case=case, results_by_engine=run_upstream_case_for_engines(case, engines=engines))


def upstream_validation_errors(result: UpstreamCaseResult) -> list[str]:
    """Return validation issues for one upstream-selected differential run."""
    status = result.status()
    if status in ("PASS", "SKIP"):
        return []
    if status == "REF-DISAGREE":
        return ["unclassified reference disagreement", *result.detail_lines()]
    return result.detail_lines()
