from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_PHASES = {f"P{index}" for index in range(7)}
VALID_STATUSES = {"pass", "xfail"}
VALID_XFAIL_REASONS = {"phase_bootstrap", "known_gap"}
VALID_TAGS = {"posix-required", "unspecified", "extension", "known-gap"}
ROADMAP_ROW_RE = re.compile(
    r"^\|\s*(T-\d+)\s*\|\s*(P\d)\s*\|\s*P\d\s*\|.*\|\s*(todo|in_progress|blocked|done)\s*\|$"
)


@dataclass(frozen=True)
class ValidationError:
    path: Path
    message: str

    def render(self, repo_root: Path) -> str:
        try:
            path_text = self.path.relative_to(repo_root).as_posix()
        except ValueError:
            path_text = self.path.as_posix()
        return f"{path_text}: {self.message}"


def main(argv: list[str] | None = None) -> int:
    repo_root = Path.cwd()
    errors = validate_repo(repo_root)
    if errors:
        for error in errors:
            print(f"phase-gate: ERROR {error.render(repo_root)}", file=sys.stderr)
        return 1

    manifest_count = count_manifests(repo_root)
    print(f"phase-gate: validated {manifest_count} manifest(s)")
    return 0


def validate_repo(repo_root: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    completed_phases, roadmap_errors = load_completed_phases(
        repo_root / "docs" / "roadmap.md"
    )
    errors.extend(roadmap_errors)

    for manifest_path in iter_manifest_paths(repo_root):
        try:
            data = parse_toml(manifest_path)
        except ValueError as exc:
            errors.append(ValidationError(manifest_path, str(exc)))
            continue
        errors.extend(
            validate_manifest(manifest_path, data, repo_root, completed_phases)
        )

    return errors


def count_manifests(repo_root: Path) -> int:
    return len(list(iter_manifest_paths(repo_root)))


def iter_manifest_paths(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "tests").glob("**/case.toml"))


def load_completed_phases(roadmap_path: Path) -> tuple[set[str], list[ValidationError]]:
    if not roadmap_path.is_file():
        return set(), [ValidationError(roadmap_path, "missing roadmap.md")]

    phase_statuses: dict[str, list[str]] = {}
    for line in roadmap_path.read_text(encoding="utf-8").splitlines():
        match = ROADMAP_ROW_RE.match(line)
        if match is None:
            continue
        phase = match.group(2)
        status = match.group(3)
        phase_statuses.setdefault(phase, []).append(status)

    completed = {
        phase
        for phase, statuses in phase_statuses.items()
        if statuses and all(status == "done" for status in statuses)
    }
    return completed, []


def parse_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file_obj:
            value = tomllib.load(file_obj)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML: {exc}") from exc

    if not value:
        raise ValueError("manifest is empty")
    if not isinstance(value, dict):
        raise ValueError("manifest root must be a mapping")
    return value


def validate_manifest(
    manifest_path: Path,
    data: dict[str, Any],
    repo_root: Path,
    completed_phases: set[str],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    required_keys = {"id", "phase", "suite", "status", "program", "expect", "tags"}
    missing_keys = sorted(required_keys - data.keys())
    for key in missing_keys:
        errors.append(ValidationError(manifest_path, f"missing required field {key!r}"))

    phase = data.get("phase")
    if phase not in VALID_PHASES:
        errors.append(ValidationError(manifest_path, f"invalid phase {phase!r}"))

    status = data.get("status")
    if status not in VALID_STATUSES:
        errors.append(ValidationError(manifest_path, f"invalid status {status!r}"))

    xfail_reason = data.get("xfail_reason")
    if status == "xfail":
        if xfail_reason not in VALID_XFAIL_REASONS:
            errors.append(
                ValidationError(
                    manifest_path, "xfail manifests require a valid xfail_reason"
                )
            )
        tracking = data.get("tracking")
        if xfail_reason == "known_gap" and (
            not isinstance(tracking, str) or not tracking
        ):
            errors.append(
                ValidationError(manifest_path, "known_gap manifests require tracking")
            )
        if xfail_reason == "phase_bootstrap" and phase in completed_phases:
            errors.append(
                ValidationError(
                    manifest_path,
                    "phase "
                    f"{phase} is complete in docs/roadmap.md and cannot keep "
                    "phase_bootstrap manifests",
                )
            )

    expect = data.get("expect")
    if not isinstance(expect, dict):
        errors.append(ValidationError(manifest_path, "expect must be a mapping"))
    else:
        if not isinstance(expect.get("stdout"), str):
            errors.append(
                ValidationError(manifest_path, "expect.stdout must be a string")
            )
        if not isinstance(expect.get("stderr_class"), str):
            errors.append(
                ValidationError(manifest_path, "expect.stderr_class must be a string")
            )
        if not isinstance(expect.get("exit"), int):
            errors.append(
                ValidationError(manifest_path, "expect.exit must be an integer")
            )

    tags = data.get("tags")
    if (
        not isinstance(tags, list)
        or not tags
        or not all(isinstance(tag, str) for tag in tags)
    ):
        errors.append(
            ValidationError(manifest_path, "tags must be a non-empty list of strings")
        )
    elif VALID_TAGS.isdisjoint(tags):
        errors.append(
            ValidationError(
                manifest_path, "tags must include a supported classification tag"
            )
        )

    validate_repo_path(
        errors,
        manifest_path,
        repo_root,
        "program",
        data.get("program"),
        allow_missing=False,
    )
    validate_repo_path(
        errors, manifest_path, repo_root, "stdin", data.get("stdin"), allow_missing=True
    )

    return errors


def validate_repo_path(
    errors: list[ValidationError],
    manifest_path: Path,
    repo_root: Path,
    field_name: str,
    value: Any,
    *,
    allow_missing: bool,
) -> None:
    if value is None:
        if not allow_missing:
            errors.append(
                ValidationError(manifest_path, f"{field_name} field is required")
            )
        return

    if not isinstance(value, str):
        errors.append(
            ValidationError(
                manifest_path, f"{field_name} must be a repository-relative path"
            )
        )
        return

    candidate = repo_root / value
    if not candidate.is_file():
        errors.append(
            ValidationError(manifest_path, f"{field_name} path does not exist: {value}")
        )
