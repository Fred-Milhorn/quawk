# Compatibility corpus loader and runner.
# This module treats AWK programs as first-class test artifacts and provides a
# small harness for running them under quawk or a reference implementation.

from __future__ import annotations

import argparse
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

EngineName = Literal["quawk", "gawk-posix", "one-true-awk"]

DEFAULT_CORPUS_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "tests" / "corpus"


@dataclass(frozen=True)
class CorpusCase:
    """One file-backed compatibility case from `tests/corpus`."""

    id: str
    description: str
    case_dir: Path
    program_path: Path
    input_path: Path | None
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


def load_case(manifest_path: Path) -> CorpusCase:
    """Load one corpus case from `manifest_path`."""
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    case_dir = manifest_path.parent

    id_value = require_string(manifest, "id", manifest_path)
    description = require_string(manifest, "description", manifest_path)
    tags = tuple(read_string_list(manifest.get("tags", []), "tags", manifest_path))
    xfail_reason = read_optional_string(manifest.get("xfail_reason"), "xfail_reason", manifest_path)

    program_rel = require_string(manifest, "program", manifest_path)
    program_path = case_dir / program_rel
    input_path = resolve_optional_path(case_dir, manifest.get("input"), "input", manifest_path)

    expect_table = manifest.get("expect")
    if not isinstance(expect_table, dict):
        raise ValueError(f"{manifest_path}: missing [expect] table")

    expected_stdout_path = resolve_optional_path(case_dir, expect_table.get("stdout"), "expect.stdout", manifest_path)
    expected_stderr_path = resolve_optional_path(case_dir, expect_table.get("stderr"), "expect.stderr", manifest_path)
    expected_exit = require_int(expect_table, "exit", manifest_path, prefix="expect.")

    ensure_file_exists(program_path, manifest_path, "program")
    if input_path is not None:
        ensure_file_exists(input_path, manifest_path, "input")
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


def resolve_optional_path(case_dir: Path, value: object, field_name: str, manifest_path: Path) -> Path | None:
    """Resolve an optional relative path from a case manifest."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: invalid path field {field_name!r}")
    return case_dir / value


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


def run_case(case: CorpusCase, engine: EngineName = "quawk") -> CorpusResult:
    """Run one case under the selected engine."""
    command = build_engine_command(engine, case.program_path)
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


def build_engine_command(engine: EngineName, program_path: Path) -> list[str]:
    """Build the command used to execute one corpus case."""
    match engine:
        case "quawk":
            return ["quawk", "-f", str(program_path)]
        case "gawk-posix":
            return ["gawk", "--posix", "-f", str(program_path)]
        case "one-true-awk":
            # This intentionally uses the host `awk` command. A stricter
            # one-true-awk path can be configured later if needed.
            return ["awk", "-f", str(program_path)]
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

    cases = select_cases(args.cases)
    if args.list:
        for case in cases:
            print(f"{case.id}: {case.description}")
        return 0

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
