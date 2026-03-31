from __future__ import annotations

from pathlib import Path

import pytest

from quawk import upstream_inventory


def test_load_upstream_selection_manifest_reads_checked_in_inventory() -> None:
    selections = upstream_inventory.load_upstream_selection_manifest()
    coverage = upstream_inventory.load_upstream_feature_coverage()

    assert selections
    assert {selection.suite for selection in selections} == {"one-true-awk", "gawk"}
    assert {selection.status for selection in selections} == {"run", "skip"}
    assert set(coverage) == set(upstream_inventory.VALID_FEATURE_FAMILIES)

    for suite in ("one-true-awk", "gawk"):
        suite_entries = selections_with_suite(suite, selections)
        assert any(selection.status == "run" for selection in suite_entries)
        assert any(selection.status == "skip" for selection in suite_entries)

    for selection in selections:
        assert selection.path.is_file()
        if selection.status == "skip":
            assert selection.reason
        else:
            assert selection.reason is None

        if selection.suite == "one-true-awk":
            assert selection.adapter.startswith("onetrueawk-")
        if selection.suite == "gawk":
            assert selection.adapter.startswith("gawk-")

    known_selection_keys = {selection.selection_key for selection in selections}
    for entry in coverage.values():
        assert entry.selection_keys
        assert set(entry.selection_keys).issubset(known_selection_keys)


def test_selection_manifest_classifies_all_onetrueawk_p_files() -> None:
    selections = upstream_inventory.load_upstream_selection_manifest()
    selected_case_ids = {
        selection.case_id
        for selection in selections
        if selection.suite == "one-true-awk" and selection.case_id.startswith("p.")
    }
    upstream_case_ids = {
        path.name
        for path in (upstream_inventory.REPO_ROOT / "third_party" / "onetrueawk" / "testdir").glob("p.*")
        if path.name != "p.table"
    }

    assert selected_case_ids == upstream_case_ids


def test_load_upstream_selection_manifest_requires_reason_for_skips(tmp_path: Path) -> None:
    manifest_path = tmp_path / "selection.toml"
    case_path = tmp_path / "case.awk"
    case_path.write_text("BEGIN { print 1 }\n", encoding="utf-8")
    manifest_path.write_text(
        '\n'.join(
            [
                "[[case]]",
                'suite = "gawk"',
                'case_id = "demo"',
                'path = "case.awk"',
                'status = "skip"',
                'adapter = "gawk-awk-ok"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a reason"):
        upstream_inventory.load_upstream_selection_manifest(root=tmp_path, path=manifest_path)


def test_load_upstream_selection_manifest_rejects_duplicate_suite_case_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "selection.toml"
    case_path = tmp_path / "case.awk"
    case_path.write_text("BEGIN { print 1 }\n", encoding="utf-8")
    manifest_path.write_text(
        '\n'.join(
            [
                "[[case]]",
                'suite = "one-true-awk"',
                'case_id = "demo"',
                'path = "case.awk"',
                'status = "run"',
                'adapter = "onetrueawk-program-file"',
                "",
                "[[case]]",
                'suite = "one-true-awk"',
                'case_id = "demo"',
                'path = "case.awk"',
                'status = "run"',
                'adapter = "onetrueawk-program-file"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate upstream case entry"):
        upstream_inventory.load_upstream_selection_manifest(root=tmp_path, path=manifest_path)


def test_load_upstream_feature_coverage_rejects_unknown_selection_keys(tmp_path: Path) -> None:
    manifest_path = tmp_path / "selection.toml"
    case_path = tmp_path / "case.awk"
    case_path.write_text("BEGIN { print 1 }\n", encoding="utf-8")
    lines = [
        "[[case]]",
        'suite = "gawk"',
        'case_id = "demo"',
        'path = "case.awk"',
        'status = "run"',
        'adapter = "gawk-awk-ok"',
        "",
    ]
    for family in upstream_inventory.VALID_FEATURE_FAMILIES:
        lines.extend(
            [
                "[[coverage]]",
                f'family = "{family}"',
                'selection_keys = ["gawk:missing"]' if family == "cli-basics" else 'selection_keys = ["gawk:demo"]',
                "",
            ]
        )
    manifest_path.write_text(
        '\n'.join(lines),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown selection key"):
        upstream_inventory.load_upstream_feature_coverage(root=tmp_path, path=manifest_path)


def test_load_upstream_feature_coverage_requires_every_family(tmp_path: Path) -> None:
    manifest_path = tmp_path / "selection.toml"
    case_path = tmp_path / "case.awk"
    case_path.write_text("BEGIN { print 1 }\n", encoding="utf-8")
    manifest_path.write_text(
        '\n'.join(
            [
                "[[case]]",
                'suite = "gawk"',
                'case_id = "demo"',
                'path = "case.awk"',
                'status = "run"',
                'adapter = "gawk-awk-ok"',
                "",
                "[[coverage]]",
                'family = "cli-basics"',
                'selection_keys = ["gawk:demo"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing upstream feature coverage entry"):
        upstream_inventory.load_upstream_feature_coverage(root=tmp_path, path=manifest_path)


def selections_with_suite(
    suite: upstream_inventory.UpstreamSuiteName,
    selections: list[upstream_inventory.UpstreamCaseSelection],
) -> list[upstream_inventory.UpstreamCaseSelection]:
    return [selection for selection in selections if selection.suite == suite]
