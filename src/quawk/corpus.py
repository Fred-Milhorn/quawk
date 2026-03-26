# Compatibility corpus loader and runner.
# This module treats AWK programs as first-class test artifacts and provides a
# small harness for running them under quawk or a reference implementation.

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

EngineName = Literal["quawk", "gawk-posix", "one-true-awk"]
DifferentialStatus = Literal["PASS", "FAIL", "SKIP", "REF-DISAGREE"]
DivergenceClassification = Literal["POSIX-specified", "implementation-defined", "unspecified/undefined", "extension"]

DEFAULT_CORPUS_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "tests" / "corpus"
DEFAULT_DIFFERENTIAL_ENGINES: Final[tuple[EngineName, ...]] = ("quawk", "one-true-awk", "gawk-posix")
DEFAULT_DIVERGENCE_MANIFEST: Final[str] = "divergences.toml"
DIVERGENCE_CLASSIFICATIONS: Final[tuple[DivergenceClassification, ...]] = (
    "POSIX-specified",
    "implementation-defined",
    "unspecified/undefined",
    "extension",
)


@dataclass(frozen=True)
class CorpusCase:
    """One file-backed compatibility case from `tests/corpus`."""

    id: str
    description: str
    case_dir: Path
    program_path: Path
    input_path: Path | None
    input_paths: tuple[Path, ...]
    cli_args: tuple[str, ...]
    expected_stdout_path: Path | None
    expected_stderr_path: Path | None
    expected_exit: int
    tags: tuple[str, ...]
    xfail_reason: str | None

    def input_text(self) -> str | None:
        """Return the case input text, if the case defines one."""
        if self.input_path is None:
            return None
        return self.input_path.read_text(encoding="utf-8")

    def expected_stdout(self) -> str:
        """Return the expected stdout text, defaulting to empty output."""
        if self.expected_stdout_path is None:
            return ""
        return self.expected_stdout_path.read_text(encoding="utf-8")

    def expected_stderr(self) -> str:
        """Return the expected stderr text, defaulting to empty output."""
        if self.expected_stderr_path is None:
            return ""
        return self.expected_stderr_path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class CorpusResult:
    """Captured process result for one corpus case run."""

    engine: EngineName
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class NormalizedCorpusResult:
    """Captured corpus result after deterministic normalization."""

    engine: EngineName
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def comparable_fields(self) -> tuple[int, str, str]:
        """Return the normalized fields used for deterministic comparison."""
        return (self.returncode, self.stdout, self.stderr)


@dataclass(frozen=True)
class DifferentialCaseResult:
    """Differential execution result for one corpus case."""

    case: CorpusCase
    results_by_engine: dict[EngineName, NormalizedCorpusResult]
    missing_engines: tuple[EngineName, ...] = ()

    def reference_results(self) -> tuple[NormalizedCorpusResult, NormalizedCorpusResult]:
        """Return the normalized reference-engine results."""
        return (self.results_by_engine["one-true-awk"], self.results_by_engine["gawk-posix"])

    def references_agree(self) -> bool:
        """Report whether the reference engines agree exactly."""
        if self.missing_engines:
            return False
        left, right = self.reference_results()
        return left.comparable_fields() == right.comparable_fields()

    def quawk_matches_references(self) -> bool:
        """Report whether `quawk` matches the agreed reference result."""
        if not self.references_agree():
            return False
        quawk_result = self.results_by_engine["quawk"]
        reference_result, _ = self.reference_results()
        return quawk_result.comparable_fields() == reference_result.comparable_fields()

    def status(self) -> DifferentialStatus:
        """Return the comparison status for this differential run."""
        if self.missing_engines:
            return "SKIP"
        if not self.references_agree():
            return "REF-DISAGREE"
        if self.quawk_matches_references():
            return "PASS"
        return "FAIL"

    def detail_lines(self) -> list[str]:
        """Return human-readable detail lines for reporting or pytest failures."""
        if self.missing_engines:
            missing = ", ".join(self.missing_engines)
            return [f"missing engines: {missing}"]

        lines: list[str] = []
        for engine in DEFAULT_DIFFERENTIAL_ENGINES:
            result = self.results_by_engine[engine]
            lines.append(f"{engine}: exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")
            lines.append(f"{engine}: command={' '.join(result.command)}")
        return lines


@dataclass(frozen=True)
class DivergenceEntry:
    """Checked-in classification for one persistent reference disagreement."""

    case_id: str
    classification: DivergenceClassification
    summary: str


def corpus_root() -> Path:
    """Return the repository-local compatibility corpus root."""
    return DEFAULT_CORPUS_ROOT


def load_cases(root: Path | None = None) -> list[CorpusCase]:
    """Load all corpus cases from `root` in deterministic order."""
    base = corpus_root() if root is None else root
    if not base.exists():
        return []

    cases: list[CorpusCase] = []
    for case_dir in sorted(path for path in base.iterdir() if path.is_dir()):
        manifest_path = case_dir / "case.toml"
        if manifest_path.exists():
            cases.append(load_case(manifest_path))
    return cases


def cases_with_tag(tag: str, root: Path | None = None) -> list[CorpusCase]:
    """Return all corpus cases carrying `tag`."""
    return [case for case in load_cases(root) if tag in case.tags]


def compatibility_baseline_cases(root: Path | None = None) -> list[CorpusCase]:
    """Return the corpus cases that seed the P10 compatibility baseline."""
    return cases_with_tag("compat-baseline", root=root)


def supported_corpus_cases(root: Path | None = None) -> list[CorpusCase]:
    """Return the supported compatibility corpus cases."""
    return cases_with_tag("supported", root=root)


def divergence_manifest_path(root: Path | None = None) -> Path:
    """Return the checked-in divergence manifest path."""
    base = corpus_root() if root is None else root
    return base / DEFAULT_DIVERGENCE_MANIFEST


def load_case(manifest_path: Path) -> CorpusCase:
    """Load one corpus case from `manifest_path`."""
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    case_dir = manifest_path.parent

    id_value = require_string(manifest, "id", manifest_path)
    description = require_string(manifest, "description", manifest_path)
    tags = tuple(read_string_list(manifest.get("tags", []), "tags", manifest_path))
    xfail_reason = read_optional_string(manifest.get("xfail_reason"), "xfail_reason", manifest_path)
    cli_args = tuple(read_optional_string_list(manifest.get("args"), "args", manifest_path))

    program_rel = require_string(manifest, "program", manifest_path)
    program_path = case_dir / program_rel
    input_path = resolve_optional_path(case_dir, manifest.get("input"), "input", manifest_path)
    input_paths = tuple(resolve_optional_paths(case_dir, manifest.get("inputs"), "inputs", manifest_path))

    expect_table = manifest.get("expect")
    if not isinstance(expect_table, dict):
        raise ValueError(f"{manifest_path}: missing [expect] table")

    expected_stdout_path = resolve_optional_path(case_dir, expect_table.get("stdout"), "expect.stdout", manifest_path)
    expected_stderr_path = resolve_optional_path(case_dir, expect_table.get("stderr"), "expect.stderr", manifest_path)
    expected_exit = require_int(expect_table, "exit", manifest_path, prefix="expect.")

    ensure_file_exists(program_path, manifest_path, "program")
    if input_path is not None:
        ensure_file_exists(input_path, manifest_path, "input")
    for file_index, extra_input_path in enumerate(input_paths, start=1):
        ensure_file_exists(extra_input_path, manifest_path, f"inputs[{file_index}]")
    if expected_stdout_path is not None:
        ensure_file_exists(expected_stdout_path, manifest_path, "expect.stdout")
    if expected_stderr_path is not None:
        ensure_file_exists(expected_stderr_path, manifest_path, "expect.stderr")

    return CorpusCase(
        id=id_value,
        description=description,
        case_dir=case_dir,
        program_path=program_path,
        input_path=input_path,
        input_paths=input_paths,
        cli_args=cli_args,
        expected_stdout_path=expected_stdout_path,
        expected_stderr_path=expected_stderr_path,
        expected_exit=expected_exit,
        tags=tags,
        xfail_reason=xfail_reason,
    )


def require_string(data: dict[str, object], key: str, manifest_path: Path) -> str:
    """Return a required string key from a manifest table."""
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: missing or invalid string field {key!r}")
    return value


def require_int(data: dict[str, object], key: str, manifest_path: Path, prefix: str = "") -> int:
    """Return a required integer key from a manifest table."""
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{manifest_path}: missing or invalid integer field {prefix}{key!r}")
    return value


def read_optional_string(value: object, field_name: str, manifest_path: Path) -> str | None:
    """Return an optional manifest string field."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: invalid string field {field_name!r}")
    return value


def read_string_list(value: object, field_name: str, manifest_path: Path) -> list[str]:
    """Return a list of manifest strings."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{manifest_path}: invalid string list field {field_name!r}")
    return list(value)


def read_optional_string_list(value: object, field_name: str, manifest_path: Path) -> list[str]:
    """Return an optional list of manifest strings."""
    if value is None:
        return []
    return read_string_list(value, field_name, manifest_path)


def resolve_optional_path(case_dir: Path, value: object, field_name: str, manifest_path: Path) -> Path | None:
    """Resolve an optional relative path from a case manifest."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: invalid path field {field_name!r}")
    return case_dir / value


def resolve_optional_paths(case_dir: Path, value: object, field_name: str, manifest_path: Path) -> list[Path]:
    """Resolve an optional list of relative paths from a case manifest."""
    path_values = read_optional_string_list(value, field_name, manifest_path)
    return [case_dir / path_value for path_value in path_values]


def ensure_file_exists(path: Path, manifest_path: Path, field_name: str) -> None:
    """Raise a manifest error when a declared file is missing."""
    if not path.is_file():
        raise ValueError(f"{manifest_path}: {field_name} file does not exist: {path}")


def select_cases(case_ids: list[str], root: Path | None = None) -> list[CorpusCase]:
    """Load all cases, optionally filtering by explicit case IDs."""
    cases = load_cases(root)
    if not case_ids:
        return cases

    wanted = set(case_ids)
    selected = [case for case in cases if case.id in wanted]
    missing = sorted(wanted.difference(case.id for case in selected))
    if missing:
        raise ValueError(f"unknown corpus case(s): {', '.join(missing)}")
    return selected


def load_divergence_manifest(
    root: Path | None = None,
    path: Path | None = None,
) -> dict[str, DivergenceEntry]:
    """Load the checked-in divergence manifest keyed by case ID."""
    manifest_path = divergence_manifest_path(root) if path is None else path
    if not manifest_path.exists():
        return {}

    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    raw_entries = manifest.get("divergence", [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"{manifest_path}: invalid divergence manifest")

    entries: dict[str, DivergenceEntry] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError(f"{manifest_path}: invalid divergence entry")
        case_id = require_string(raw_entry, "case_id", manifest_path)
        if case_id in entries:
            raise ValueError(f"{manifest_path}: duplicate divergence entry for {case_id!r}")
        entries[case_id] = DivergenceEntry(
            case_id=case_id,
            classification=read_divergence_classification(raw_entry.get("classification"), manifest_path),
            summary=require_string(raw_entry, "summary", manifest_path),
        )

    known_case_ids = {case.id for case in load_cases(root)}
    unknown_case_ids = sorted(case_id for case_id in entries if case_id not in known_case_ids)
    if unknown_case_ids:
        raise ValueError(
            f"{manifest_path}: divergence entries reference unknown corpus case(s): {', '.join(unknown_case_ids)}"
        )
    return entries


def read_divergence_classification(value: object, manifest_path: Path) -> DivergenceClassification:
    """Return one valid divergence classification string."""
    if value not in DIVERGENCE_CLASSIFICATIONS:
        allowed = ", ".join(DIVERGENCE_CLASSIFICATIONS)
        raise ValueError(f"{manifest_path}: invalid divergence classification {value!r}; expected one of: {allowed}")
    return value


def differential_validation_errors(
    result: DifferentialCaseResult,
    divergences: dict[str, DivergenceEntry],
) -> list[str]:
    """Return validation issues for one differential result and divergence manifest."""
    status = result.status()
    divergence_entry = divergences.get(result.case.id)
    if status == "SKIP":
        return []
    if status == "PASS":
        if divergence_entry is None:
            return []
        return [f"stale divergence manifest entry: {divergence_entry.classification} - {divergence_entry.summary}"]
    if status == "REF-DISAGREE":
        if divergence_entry is not None:
            return []
        return ["unclassified reference disagreement", *result.detail_lines()]
    if divergence_entry is not None:
        return [f"stale divergence manifest entry: {divergence_entry.classification} - {divergence_entry.summary}"]
    return result.detail_lines()


def run_case(case: CorpusCase, engine: EngineName = "quawk") -> CorpusResult:
    """Run one case under the selected engine."""
    command = build_engine_command(engine, case.program_path, cli_args=case.cli_args, input_paths=case.input_paths)
    result = subprocess.run(
        command,
        input=case.input_text(),
        capture_output=True,
        text=True,
        check=False,
    )
    return CorpusResult(
        engine=engine,
        command=tuple(command),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def normalize_result(result: CorpusResult) -> NormalizedCorpusResult:
    """Normalize one raw subprocess result conservatively for comparison."""
    return NormalizedCorpusResult(
        engine=result.engine,
        command=result.command,
        returncode=result.returncode,
        stdout=result.stdout.replace("\r\n", "\n"),
        stderr=result.stderr.replace("\r\n", "\n"),
    )


def is_engine_available(engine: EngineName) -> bool:
    """Report whether the requested engine is available in the current environment."""
    executable = build_engine_command(engine, Path("program.awk"))[0]
    return shutil.which(executable) is not None


def missing_engines(engines: tuple[EngineName, ...] = DEFAULT_DIFFERENTIAL_ENGINES) -> tuple[EngineName, ...]:
    """Return the differential engines missing from the current environment."""
    return tuple(engine for engine in engines if not is_engine_available(engine))


def run_case_for_engines(
    case: CorpusCase,
    engines: tuple[EngineName, ...] = DEFAULT_DIFFERENTIAL_ENGINES,
) -> dict[EngineName, NormalizedCorpusResult]:
    """Run one corpus case under each requested engine exactly once."""
    results: dict[EngineName, NormalizedCorpusResult] = {}
    for engine in engines:
        results[engine] = normalize_result(run_case(case, engine=engine))
    return results


def run_case_differential(
    case: CorpusCase,
    engines: tuple[EngineName, ...] = DEFAULT_DIFFERENTIAL_ENGINES,
) -> DifferentialCaseResult:
    """Run one corpus case under all differential engines and compare them."""
    missing = missing_engines(engines)
    if missing:
        return DifferentialCaseResult(case=case, results_by_engine={}, missing_engines=missing)
    return DifferentialCaseResult(case=case, results_by_engine=run_case_for_engines(case, engines=engines))


def build_engine_command(
    engine: EngineName,
    program_path: Path,
    cli_args: tuple[str, ...] = (),
    input_paths: tuple[Path, ...] = (),
) -> list[str]:
    """Build the command used to execute one corpus case."""
    input_args = [str(input_path) for input_path in input_paths]
    match engine:
        case "quawk":
            return ["quawk", *cli_args, "-f", str(program_path), *input_args]
        case "gawk-posix":
            return ["gawk", "--posix", *cli_args, "-f", str(program_path), *input_args]
        case "one-true-awk":
            # This intentionally uses the host `awk` command. A stricter
            # one-true-awk path can be configured later if needed.
            return ["awk", *cli_args, "-f", str(program_path), *input_args]
    raise AssertionError(f"unhandled engine: {engine}")


def compare_case(case: CorpusCase, result: CorpusResult) -> list[str]:
    """Return human-readable mismatch lines for `result` against `case`."""
    mismatches: list[str] = []
    if result.returncode != case.expected_exit:
        mismatches.append(f"exit: expected {case.expected_exit}, got {result.returncode}")
    expected_stdout = case.expected_stdout()
    if result.stdout != expected_stdout:
        mismatches.append(f"stdout: expected {expected_stdout!r}, got {result.stdout!r}")
    expected_stderr = case.expected_stderr()
    if result.stderr != expected_stderr:
        mismatches.append(f"stderr: expected {expected_stderr!r}, got {result.stderr!r}")
    return mismatches


def main(argv: list[str] | None = None) -> int:
    """Run selected corpus cases from the command line."""
    parser = argparse.ArgumentParser(
        prog="corpus",
        description="Run quawk compatibility corpus cases.",
    )
    parser.add_argument(
        "--differential",
        action="store_true",
        help="Run each case under quawk, awk, and gawk --posix.",
    )
    parser.add_argument(
        "--engine",
        choices=("quawk", "gawk-posix", "one-true-awk"),
        default="quawk",
        help="Execution engine used for the corpus run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available case IDs and exit.",
    )
    parser.add_argument(
        "cases",
        nargs="*",
        help="Optional case IDs to run. Default: run all cases.",
    )
    args = parser.parse_args(argv)
    if args.differential and args.engine != "quawk":
        parser.error("--differential cannot be combined with --engine")

    cases = select_cases(args.cases)
    if args.list:
        for case in cases:
            print(f"{case.id}: {case.description}")
        return 0

    if args.differential:
        divergences = load_divergence_manifest()
        failures = 0
        for case in cases:
            differential_result = run_case_differential(case)
            status = differential_result.status()
            divergence_entry = divergences.get(case.id)
            if status == "REF-DISAGREE" and divergence_entry is not None:
                print(f"{status} {case.id} [{divergence_entry.classification}]")
            else:
                print(f"{status} {case.id}")
            if differential_validation_errors(differential_result, divergences):
                failures += 1
            if status == "SKIP":
                failures += 1

        missing = missing_engines()
        if missing:
            missing_text = ", ".join(missing)
            print(f"corpus: missing differential engines: {missing_text}", file=sys.stderr)
        return 0 if failures == 0 else 1

    failures = 0
    for case in cases:
        result = run_case(case, engine=args.engine)
        mismatches = compare_case(case, result)
        status = "PASS" if not mismatches else "FAIL"
        print(f"{status} {case.id}")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        if mismatches:
            failures += 1

    return 0 if failures == 0 else 1
