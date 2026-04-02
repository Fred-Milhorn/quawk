"""Audit helpers for the claimed-backend execution baseline."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from . import jit
from .lexer import lex
from .parser import parse
from .semantics import analyze
from .source import ProgramSource

ArchitectureAuditFamilyId = Literal[
    "control-flow-do-while",
    "control-flow-loop-break-continue",
    "default-print-expression-patterns",
    "expression-pattern-actions",
    "record-control-exit",
    "record-control-next",
    "record-control-nextfile",
    "scalar-string-coercions",
    "user-defined-functions",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_ARCHITECTURE_AUDIT_PATH: Final[Path] = REPO_ROOT / "tests" / "architecture" / "audit.toml"
VALID_AUDIT_FAMILIES: Final[tuple[ArchitectureAuditFamilyId, ...]] = (
    "control-flow-do-while",
    "control-flow-loop-break-continue",
    "default-print-expression-patterns",
    "expression-pattern-actions",
    "record-control-exit",
    "record-control-next",
    "record-control-nextfile",
    "scalar-string-coercions",
    "user-defined-functions",
)


@dataclass(frozen=True)
class ArchitectureAuditEntry:
    """One checked-in claimed-backend audit entry."""

    family: ArchitectureAuditFamilyId
    spec_area: str
    program: str
    expected_uses_host_runtime: bool
    expected_supports_public_backend_execution: bool
    expected_supports_ir_asm: bool
    notes: str | None


@dataclass(frozen=True)
class ArchitectureAuditObservation:
    """Observed backend-support shape for one representative claimed family."""

    uses_host_runtime: bool
    supports_public_backend_execution: bool
    supports_ir_asm: bool


def architecture_audit_path(path: Path | None = None) -> Path:
    """Return the default checked-in architecture audit manifest path."""
    return DEFAULT_ARCHITECTURE_AUDIT_PATH if path is None else path


def load_architecture_audit_manifest(path: Path | None = None) -> list[ArchitectureAuditEntry]:
    """Load and validate the checked-in architecture-audit baseline."""
    manifest_path = architecture_audit_path(path)
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    raw_entries = manifest.get("case", [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"{manifest_path}: invalid architecture audit manifest")

    entries: list[ArchitectureAuditEntry] = []
    seen_families: set[ArchitectureAuditFamilyId] = set()

    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError(f"{manifest_path}: invalid architecture audit entry")

        family = read_family(raw_entry.get("family"), manifest_path)
        if family in seen_families:
            raise ValueError(f"{manifest_path}: duplicate architecture audit entry for {family!r}")
        seen_families.add(family)

        entries.append(
            ArchitectureAuditEntry(
                family=family,
                spec_area=require_string(raw_entry, "spec_area", manifest_path),
                program=require_string(raw_entry, "program", manifest_path),
                expected_uses_host_runtime=require_bool(raw_entry, "expected_uses_host_runtime", manifest_path),
                expected_supports_public_backend_execution=require_bool(
                    raw_entry,
                    "expected_supports_public_backend_execution",
                    manifest_path,
                ),
                expected_supports_ir_asm=require_bool(raw_entry, "expected_supports_ir_asm", manifest_path),
                notes=read_optional_string(raw_entry.get("notes"), "notes", manifest_path),
            )
        )

    missing_families = sorted(family for family in VALID_AUDIT_FAMILIES if family not in seen_families)
    if missing_families:
        raise ValueError(
            f"{manifest_path}: missing architecture audit entry for: {', '.join(missing_families)}"
        )
    return entries


def observe_backend_support(program_text: str) -> ArchitectureAuditObservation:
    """Classify one representative program against the current backend contract."""
    program = parse(lex(ProgramSource.from_inline(program_text)))
    analyze(program)

    uses_host_runtime = jit.requires_host_runtime_execution(program) or jit.requires_host_runtime_value_execution(program)
    try:
        jit.lower_to_llvm_ir(program)
    except RuntimeError:
        supports_ir_asm = False
    else:
        supports_ir_asm = True

    return ArchitectureAuditObservation(
        uses_host_runtime=uses_host_runtime,
        supports_public_backend_execution=(not uses_host_runtime) and supports_ir_asm,
        supports_ir_asm=supports_ir_asm,
    )


def manifest_mismatches(entries: list[ArchitectureAuditEntry] | None = None) -> list[str]:
    """Return descriptive mismatches between the manifest and the current implementation."""
    audit_entries = load_architecture_audit_manifest() if entries is None else entries
    mismatches: list[str] = []
    for entry in audit_entries:
        observed = observe_backend_support(entry.program)
        if observed.uses_host_runtime != entry.expected_uses_host_runtime:
            mismatches.append(
                f"{entry.family}: expected uses_host_runtime={entry.expected_uses_host_runtime}, "
                f"observed {observed.uses_host_runtime}"
            )
        if observed.supports_public_backend_execution != entry.expected_supports_public_backend_execution:
            mismatches.append(
                f"{entry.family}: expected supports_public_backend_execution="
                f"{entry.expected_supports_public_backend_execution}, "
                f"observed {observed.supports_public_backend_execution}"
            )
        if observed.supports_ir_asm != entry.expected_supports_ir_asm:
            mismatches.append(
                f"{entry.family}: expected supports_ir_asm={entry.expected_supports_ir_asm}, "
                f"observed {observed.supports_ir_asm}"
            )
    return mismatches


def families_lacking_full_backend_support(
    entries: list[ArchitectureAuditEntry] | None = None,
) -> list[ArchitectureAuditFamilyId]:
    """Return claimed families that still lack backend execution or inspection parity."""
    audit_entries = load_architecture_audit_manifest() if entries is None else entries
    blocking: list[ArchitectureAuditFamilyId] = []
    for entry in audit_entries:
        observed = observe_backend_support(entry.program)
        if observed.supports_public_backend_execution and observed.supports_ir_asm:
            continue
        blocking.append(entry.family)
    return blocking


def require_string(data: dict[str, object], key: str, manifest_path: Path) -> str:
    """Return one required string field."""
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: missing or invalid string field {key!r}")
    return value


def require_bool(data: dict[str, object], key: str, manifest_path: Path) -> bool:
    """Return one required boolean field."""
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{manifest_path}: missing or invalid boolean field {key!r}")
    return value


def read_optional_string(value: object, field_name: str, manifest_path: Path) -> str | None:
    """Return one optional string field."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{manifest_path}: invalid string field {field_name!r}")
    return value


def read_family(value: object, manifest_path: Path) -> ArchitectureAuditFamilyId:
    """Return one valid architecture-audit family identifier."""
    if value not in VALID_AUDIT_FAMILIES:
        allowed = ", ".join(VALID_AUDIT_FAMILIES)
        raise ValueError(f"{manifest_path}: invalid architecture audit family {value!r}; expected one of: {allowed}")
    return value
