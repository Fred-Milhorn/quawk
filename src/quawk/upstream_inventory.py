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
UpstreamFeatureFamilyId = Literal[
    "cli-basics",
    "pattern-action-execution",
    "regex-selection",
    "default-print-patterns",
    "scalar-assignment",
    "associative-arrays",
    "fields",
    "control-flow",
    "record-control",
    "expressions-and-coercions",
    "user-defined-functions",
    "builtin-variables",
    "implemented-builtins",
    "multi-file-input-processing",
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
VALID_FEATURE_FAMILIES: Final[tuple[UpstreamFeatureFamilyId, ...]] = (
    "cli-basics",
    "pattern-action-execution",
    "regex-selection",
    "default-print-patterns",
    "scalar-assignment",
    "associative-arrays",
    "fields",
    "control-flow",
    "record-control",
    "expressions-and-coercions",
    "user-defined-functions",
    "builtin-variables",
    "implemented-builtins",
    "multi-file-input-processing",
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

    @property
    def selection_key(self) -> str:
        """Return the suite-prefixed selection key used by coverage metadata."""
        return f"{self.suite}:{self.case_id}"


@dataclass(frozen=True)
class UpstreamFeatureCoverageEntry:
    """One checked-in feature-family mapping into the upstream inventory."""

    family: UpstreamFeatureFamilyId
    selection_keys: tuple[str, ...]
    notes: str | None


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


def load_upstream_feature_coverage(
    root: Path | None = None,
    path: Path | None = None,
) -> dict[UpstreamFeatureFamilyId, UpstreamFeatureCoverageEntry]:
    """Load and validate the checked-in upstream feature-family coverage map."""
    manifest_path = upstream_selection_path(root) if path is None else path
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    raw_entries = manifest.get("coverage", [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"{manifest_path}: invalid upstream feature coverage section")

    selection_entries = load_upstream_selection_manifest(root=root, path=manifest_path)
    known_selection_keys = {entry.selection_key for entry in selection_entries}
    entries: dict[UpstreamFeatureFamilyId, UpstreamFeatureCoverageEntry] = {}

    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError(f"{manifest_path}: invalid upstream feature coverage entry")

        family = read_feature_family(raw_entry.get("family"), manifest_path)
        if family in entries:
            raise ValueError(f"{manifest_path}: duplicate upstream feature coverage entry for {family!r}")

        selection_keys = tuple(read_string_list(raw_entry.get("selection_keys", []), "selection_keys", manifest_path))
        if not selection_keys:
            raise ValueError(f"{manifest_path}: upstream feature coverage entry {family!r} must reference selections")
        unknown_keys = sorted(selection_key for selection_key in selection_keys if selection_key not in known_selection_keys)
        if unknown_keys:
            raise ValueError(
                f"{manifest_path}: upstream feature coverage entry {family!r} references unknown selection key(s): "
                f"{', '.join(unknown_keys)}"
            )

        entries[family] = UpstreamFeatureCoverageEntry(
            family=family,
            selection_keys=selection_keys,
            notes=read_optional_string(raw_entry.get("notes"), "notes", manifest_path),
        )

    missing_families = sorted(family for family in VALID_FEATURE_FAMILIES if family not in entries)
    if missing_families:
        raise ValueError(
            f"{manifest_path}: missing upstream feature coverage entry for: {', '.join(missing_families)}"
        )
    return entries


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


def read_feature_family(value: object, manifest_path: Path) -> UpstreamFeatureFamilyId:
    """Return one valid implemented compatibility feature-family identifier."""
    if value not in VALID_FEATURE_FAMILIES:
        allowed = ", ".join(VALID_FEATURE_FAMILIES)
        raise ValueError(
            f"{manifest_path}: invalid upstream feature family {value!r}; expected one of: {allowed}"
        )
    return value
