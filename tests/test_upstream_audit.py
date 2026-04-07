from __future__ import annotations

from pathlib import Path

from quawk.compat import upstream_audit, upstream_divergence, upstream_inventory


def test_families_missing_runnable_upstream_coverage_is_empty_for_checked_in_state() -> None:
    selections = upstream_inventory.load_upstream_selection_manifest()
    coverage = upstream_inventory.load_upstream_feature_coverage()

    assert upstream_audit.families_missing_runnable_upstream_coverage(selections, coverage) == []


def test_blocking_posix_required_fix_case_ids_is_empty_for_checked_in_state() -> None:
    assert upstream_audit.blocking_posix_required_fix_case_ids() == []


def test_families_missing_runnable_upstream_coverage_reports_skip_only_family() -> None:
    selection = upstream_inventory.UpstreamCaseSelection(
        suite="one-true-awk",
        case_id="demo-skip",
        path=Path("/tmp/demo.awk"),
        status="skip",
        adapter="onetrueawk-program-file",
        tags=(),
        reason="demo",
    )
    coverage = {
        "cli-basics": upstream_inventory.UpstreamFeatureCoverageEntry(
            family="cli-basics",
            selection_keys=("one-true-awk:demo-skip",),
            notes=None,
        )
    }

    assert upstream_audit.families_missing_runnable_upstream_coverage([selection], coverage) == ["cli-basics"]


def test_blocking_posix_required_fix_case_ids_reports_classified_fix(tmp_path: Path) -> None:
    root = tmp_path
    selection_dir = root / "tests" / "upstream"
    selection_dir.mkdir(parents=True)
    (root / "docs").mkdir()
    case_path = root / "third_party" / "gawk" / "test" / "demo.awk"
    case_path.parent.mkdir(parents=True)
    case_path.write_text('BEGIN { print 1 }\n', encoding="utf-8")
    (case_path.with_suffix(".ok")).write_text("1\n", encoding="utf-8")
    selection_lines = [
        "[[case]]",
        'suite = "gawk"',
        'case_id = "demo"',
        'path = "third_party/gawk/test/demo.awk"',
        'status = "run"',
        'adapter = "gawk-awk-ok"',
        "",
    ]
    for family in upstream_inventory.VALID_FEATURE_FAMILIES:
        selection_lines.extend(
            [
                "[[coverage]]",
                f'family = "{family}"',
                'selection_keys = ["gawk:demo"]',
                "",
            ]
        )
    (selection_dir / "selection.toml").write_text('\n'.join(selection_lines), encoding="utf-8")
    notes_path = root / "docs" / "compatibility.md"
    notes_path.write_text(
        '\n'.join(
            [
                "# Compatibility Plan",
                "",
                "<!-- upstream-divergence: demo-fix -->",
                "## Demo fix",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = selection_dir / "divergences.toml"
    manifest_path.write_text(
        '\n'.join(
            [
                "[[divergence]]",
                'suite = "gawk"',
                'case_id = "demo"',
                'classification = "posix-required-fix"',
                'decision = "fix-now"',
                'summary = "demo"',
                'last_verified_upstream_commit = "abcdef1"',
                'notes_ref = "demo-fix"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    divergences = upstream_divergence.load_upstream_divergence_manifest(
        root=root,
        path=manifest_path,
        notes_path=notes_path,
    )

    assert upstream_audit.blocking_posix_required_fix_case_ids(divergences) == ["gawk:demo"]
