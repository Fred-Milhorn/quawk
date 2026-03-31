"""Audit helpers for the upstream compatibility done-line criteria."""

from __future__ import annotations

from quawk.upstream_divergence import load_upstream_divergence_manifest
from quawk.upstream_divergence import UpstreamDivergenceEntry
from quawk.upstream_inventory import (
    UpstreamFeatureFamilyId,
    UpstreamFeatureCoverageEntry,
    UpstreamCaseSelection,
    load_upstream_feature_coverage,
    load_upstream_selection_manifest,
)


def families_missing_runnable_upstream_coverage(
    selections: list[UpstreamCaseSelection] | None = None,
    coverage: dict[UpstreamFeatureFamilyId, UpstreamFeatureCoverageEntry] | None = None,
) -> list[UpstreamFeatureFamilyId]:
    """Return implemented feature families that have no runnable upstream anchor."""
    selection_entries = load_upstream_selection_manifest() if selections is None else selections
    coverage_entries = load_upstream_feature_coverage() if coverage is None else coverage
    statuses_by_selection_key = {
        selection.selection_key: selection.status
        for selection in selection_entries
    }

    missing: list[UpstreamFeatureFamilyId] = []
    for family, entry in coverage_entries.items():
        if any(statuses_by_selection_key[selection_key] == "run" for selection_key in entry.selection_keys):
            continue
        missing.append(family)
    return missing


def blocking_posix_required_fix_case_ids(
    divergences: dict[str, UpstreamDivergenceEntry] | None = None,
) -> list[str]:
    """Return runnable upstream cases that still carry blocking `posix-required-fix` classifications."""
    divergence_entries = load_upstream_divergence_manifest() if divergences is None else divergences
    blocking = [
        result_key
        for result_key, entry in divergence_entries.items()
        if entry.classification == "posix-required-fix"
    ]
    return sorted(blocking)
