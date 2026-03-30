"""Load and validate the checked-in upstream suite selection manifest."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

UpstreamSuiteName = Literal["one-true-awk", "gawk"]
UpstreamCaseStatus = Literal["run", "skip"]
UpstreamAdapterName = Literal[
    "onetrueawk-program-file",
    "onetrueawk-shell-driver",
    "gawk-awk-ok",
    "gawk-awk-in-ok",
    "gawk-shell-driver",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_UPSTREAM_SELECTION_PATH: Final[Path] = REPO_ROOT / "tests" / "upstream" / "selection.toml"
VALID_SUITES: Final[tuple[UpstreamSuiteName, ...]] = ("one-true-awk", "gawk")
VALID_STATUSES: Final[tuple[UpstreamCaseStatus, ...]] = ("run", "skip")
VALID_ADAPTERS: Final[tuple[UpstreamAdapterName, ...]] = (
    "onetrueawk-program-file",
    "onetrueawk-shell-driver",
    "gawk-awk-ok",
    "gawk-awk-in-ok",
    "gawk-shell-driver",
)


@dataclass(frozen=True)
class UpstreamCaseSelection:
    """One checked-in upstream case selection entry."""

    suite: UpstreamSuiteName
    case_id: str
    path: Path
    status: UpstreamCaseStatus
    adapter: UpstreamAdapterName
    tags: tuple[str, ...]
    reason: str | None


def upstream_selection_path(root: Path | None = None) -> Path:
    """Return the default checked-in upstream selection manifest path."""
    base = REPO_ROOT if root is None else root
    return base / "tests" / "upstream" / "selection.toml"


def load_upstream_selection_manifest(
    root: Path | None = None,
    path: Path | None = None,
) -> list[UpstreamCaseSelection]:
    """Load and validate the checked-in upstream suite selection manifest."""
    manifest_path = upstream_selection_path(root) if path is None else path
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    raw_cases = manifest.get("case", [])
    if not isinstance(raw_cases, list):
        raise ValueError(f"{manifest_path}: invalid upstream selection manifest")

    entries: list[UpstreamCaseSelection] = []
    seen: set[tuple[UpstreamSuiteName, str]] = set()
    manifest_root = REPO_ROOT if root is None else root

    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError(f"{manifest_path}: invalid upstream case entry")

        suite = read_suite(raw_case.get("suite"), manifest_path)
        case_id = require_string(raw_case, "case_id", manifest_path)
        seen_key = (suite, case_id)
        if seen_key in seen:
            raise ValueError(f"{manifest_path}: duplicate upstream case entry for {suite}:{case_id}")
        seen.add(seen_key)

        relative_path = require_string(raw_case, "path", manifest_path)
        resolved_path = manifest_root / relative_path
        if not resolved_path.is_file():
            raise ValueError(f"{manifest_path}: upstream case path does not exist: {resolved_path}")

        status = read_status(raw_case.get("status"), manifest_path)
        adapter = read_adapter(raw_case.get("adapter"), manifest_path)
        tags = tuple(read_string_list(raw_case.get("tags", []), "tags", manifest_path))
        reason = read_optional_string(raw_case.get("reason"), "reason", manifest_path)

        if status == "skip" and reason is None:
            raise ValueError(f"{manifest_path}: skipped upstream case {suite}:{case_id} requires a reason")
        if status == "run" and reason is not None:
            raise ValueError(f"{manifest_path}: runnable upstream case {suite}:{case_id} must not carry a reason")

        entries.append(
            UpstreamCaseSelection(
                suite=suite,
                case_id=case_id,
                path=resolved_path,
                status=status,
                adapter=adapter,
                tags=tags,
                reason=reason,
            )
        )

    return entries


def selections_with_status(
    status: UpstreamCaseStatus,
    selections: list[UpstreamCaseSelection],
) -> list[UpstreamCaseSelection]:
    """Return all selections with the requested manifest status."""
    return [selection for selection in selections if selection.status == status]


def require_string(data: dict[str, object], key: str, manifest_path: Path) -> str:
    """Return one required string field."""
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: missing or invalid string field {key!r}")
    return value


def read_optional_string(value: object, field_name: str, manifest_path: Path) -> str | None:
    """Return one optional string field."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: invalid string field {field_name!r}")
    return value


def read_string_list(value: object, field_name: str, manifest_path: Path) -> list[str]:
    """Return a list of strings."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{manifest_path}: invalid string list field {field_name!r}")
    return list(value)


def read_suite(value: object, manifest_path: Path) -> UpstreamSuiteName:
    """Return one valid upstream suite name."""
    if value not in VALID_SUITES:
        allowed = ", ".join(VALID_SUITES)
        raise ValueError(f"{manifest_path}: invalid upstream suite {value!r}; expected one of: {allowed}")
    return value


def read_status(value: object, manifest_path: Path) -> UpstreamCaseStatus:
    """Return one valid upstream selection status."""
    if value not in VALID_STATUSES:
        allowed = ", ".join(VALID_STATUSES)
        raise ValueError(f"{manifest_path}: invalid upstream case status {value!r}; expected one of: {allowed}")
    return value


def read_adapter(value: object, manifest_path: Path) -> UpstreamAdapterName:
    """Return one valid upstream adapter name."""
    if value not in VALID_ADAPTERS:
        allowed = ", ".join(VALID_ADAPTERS)
        raise ValueError(f"{manifest_path}: invalid upstream adapter {value!r}; expected one of: {allowed}")
    return value
