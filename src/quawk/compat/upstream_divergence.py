"""Load and validate evaluated divergences for upstream compatibility cases."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from quawk.compat.upstream_inventory import UpstreamSuiteName, load_upstream_selection_manifest, selections_with_status

UpstreamDivergenceClassification = Literal[
    "posix-required-fix",
    "known-gap",
    "intentional-quawk-extension",
    "gnu-extension-out-of-scope",
    "platform-specific",
    "reference-disagreement",
    "wont-fix",
]
UpstreamDivergenceDecision = Literal["fix-now", "fix-later", "accepted", "out-of-scope", "wont-fix"]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
DEFAULT_UPSTREAM_DIVERGENCE_PATH: Final[Path] = REPO_ROOT / "tests" / "upstream" / "divergences.toml"
DEFAULT_UPSTREAM_NOTES_PATH: Final[Path] = REPO_ROOT / "docs" / "compatibility.md"
VALID_CLASSIFICATIONS: Final[tuple[UpstreamDivergenceClassification, ...]] = (
    "posix-required-fix",
    "known-gap",
    "intentional-quawk-extension",
    "gnu-extension-out-of-scope",
    "platform-specific",
    "reference-disagreement",
    "wont-fix",
)
VALID_DECISIONS: Final[tuple[UpstreamDivergenceDecision, ...]] = (
    "fix-now",
    "fix-later",
    "accepted",
    "out-of-scope",
    "wont-fix",
)
ALLOWED_DECISIONS_BY_CLASSIFICATION: Final[dict[UpstreamDivergenceClassification, tuple[UpstreamDivergenceDecision, ...]]] = {
    "posix-required-fix": ("fix-now", "fix-later"),
    "known-gap": ("fix-later", "accepted", "wont-fix"),
    "intentional-quawk-extension": ("accepted", "wont-fix"),
    "gnu-extension-out-of-scope": ("out-of-scope", "wont-fix"),
    "platform-specific": ("out-of-scope", "wont-fix"),
    "reference-disagreement": ("accepted", "fix-later"),
    "wont-fix": ("wont-fix",),
}
NOTE_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(r"<!-- upstream-divergence: ([a-z0-9-]+) -->")
HEX_COMMIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class UpstreamDivergenceEntry:
    """Checked-in evaluation for one upstream-selected compatibility case."""

    suite: UpstreamSuiteName
    case_id: str
    classification: UpstreamDivergenceClassification
    decision: UpstreamDivergenceDecision
    summary: str
    last_verified_upstream_commit: str
    notes_ref: str

    @property
    def result_key(self) -> str:
        """Return the suite-prefixed result key used by upstream runs."""
        return f"{self.suite}:{self.case_id}"


def upstream_divergence_manifest_path(root: Path | None = None) -> Path:
    """Return the checked-in upstream divergence manifest path."""
    base = REPO_ROOT if root is None else root
    return base / "tests" / "upstream" / "divergences.toml"


def upstream_notes_path(root: Path | None = None) -> Path:
    """Return the checked-in upstream compatibility notes path."""
    base = REPO_ROOT if root is None else root
    return base / "docs" / "compatibility.md"


def load_upstream_note_refs(root: Path | None = None, path: Path | None = None) -> set[str]:
    """Return the note references declared in the companion upstream notes doc."""
    notes_doc_path = upstream_notes_path(root) if path is None else path
    if not notes_doc_path.exists():
        return set()
    return set(NOTE_MARKER_PATTERN.findall(notes_doc_path.read_text(encoding="utf-8")))


def load_upstream_divergence_manifest(
    root: Path | None = None,
    path: Path | None = None,
    notes_path: Path | None = None,
) -> dict[str, UpstreamDivergenceEntry]:
    """Load the checked-in upstream divergence manifest keyed by suite-prefixed case ID."""
    manifest_path = upstream_divergence_manifest_path(root) if path is None else path
    if not manifest_path.exists():
        return {}

    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    raw_entries = manifest.get("divergence", [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"{manifest_path}: invalid upstream divergence manifest")

    note_refs = load_upstream_note_refs(root=root, path=notes_path)
    entries: dict[str, UpstreamDivergenceEntry] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError(f"{manifest_path}: invalid upstream divergence entry")

        suite = read_suite(raw_entry.get("suite"), manifest_path)
        case_id = require_string(raw_entry, "case_id", manifest_path)
        entry = UpstreamDivergenceEntry(
            suite=suite,
            case_id=case_id,
            classification=read_classification(raw_entry.get("classification"), manifest_path),
            decision=read_decision(raw_entry.get("decision"), manifest_path),
            summary=require_string(raw_entry, "summary", manifest_path),
            last_verified_upstream_commit=read_commit(raw_entry.get("last_verified_upstream_commit"), manifest_path),
            notes_ref=read_notes_ref(raw_entry.get("notes_ref"), manifest_path),
        )
        validate_decision(entry, manifest_path)
        if entry.notes_ref not in note_refs:
            raise ValueError(f"{manifest_path}: missing compatibility note marker for {entry.notes_ref!r}")
        if entry.result_key in entries:
            raise ValueError(f"{manifest_path}: duplicate upstream divergence entry for {entry.result_key}")
        entries[entry.result_key] = entry

    known_case_ids = {
        f"{selection.suite}:{selection.case_id}"
        for selection in selections_with_status("run", load_upstream_selection_manifest(root=root))
    }
    unknown_case_ids = sorted(result_key for result_key in entries if result_key not in known_case_ids)
    if unknown_case_ids:
        raise ValueError(
            f"{manifest_path}: upstream divergence entries reference unknown runnable case(s): {', '.join(unknown_case_ids)}"
        )
    return entries


def require_string(data: dict[str, object], key: str, manifest_path: Path) -> str:
    """Return one required string field."""
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: missing or invalid string field {key!r}")
    return value


def read_suite(value: object, manifest_path: Path) -> UpstreamSuiteName:
    """Return one valid upstream suite name."""
    if value not in ("one-true-awk", "gawk"):
        raise ValueError(f"{manifest_path}: invalid upstream suite {value!r}")
    return value


def read_classification(value: object, manifest_path: Path) -> UpstreamDivergenceClassification:
    """Return one valid upstream divergence classification."""
    if value not in VALID_CLASSIFICATIONS:
        allowed = ", ".join(VALID_CLASSIFICATIONS)
        raise ValueError(f"{manifest_path}: invalid upstream divergence classification {value!r}; expected one of: {allowed}")
    return value


def read_decision(value: object, manifest_path: Path) -> UpstreamDivergenceDecision:
    """Return one valid upstream divergence decision."""
    if value not in VALID_DECISIONS:
        allowed = ", ".join(VALID_DECISIONS)
        raise ValueError(f"{manifest_path}: invalid upstream divergence decision {value!r}; expected one of: {allowed}")
    return value


def read_commit(value: object, manifest_path: Path) -> str:
    """Return one hex commit identifier string."""
    if not isinstance(value, str) or not HEX_COMMIT_PATTERN.fullmatch(value):
        raise ValueError(f"{manifest_path}: invalid upstream commit {value!r}")
    return value


def read_notes_ref(value: object, manifest_path: Path) -> str:
    """Return one valid notes reference identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{manifest_path}: invalid notes_ref field")
    return value


def validate_decision(entry: UpstreamDivergenceEntry, manifest_path: Path) -> None:
    """Validate that the decision is coherent for the chosen classification."""
    allowed_decisions = ALLOWED_DECISIONS_BY_CLASSIFICATION[entry.classification]
    if entry.decision not in allowed_decisions:
        allowed = ", ".join(allowed_decisions)
        raise ValueError(
            f"{manifest_path}: invalid decision {entry.decision!r} for {entry.classification!r}; expected one of: {allowed}"
        )
