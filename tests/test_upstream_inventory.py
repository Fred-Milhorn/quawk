from __future__ import annotations

from pathlib import Path

import pytest

from quawk import upstream_inventory


def test_load_upstream_selection_manifest_reads_checked_in_inventory() -> None:
    selections = upstream_inventory.load_upstream_selection_manifest()

    assert [selection.case_id for selection in selections_with_suite("one-true-awk", selections)] == [
        "t.split1",
        "t.for",
        "T.split",
    ]
    assert [selection.case_id for selection in selections_with_suite("gawk", selections)] == [
        "assignnumfield",
        "posix_compare",
        "cmdlinefsbacknl",
    ]
    assert [selection.case_id for selection in upstream_inventory.selections_with_status("run", selections)] == [
        "t.split1",
        "t.for",
        "assignnumfield",
        "posix_compare",
    ]


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


def selections_with_suite(
    suite: upstream_inventory.UpstreamSuiteName,
    selections: list[upstream_inventory.UpstreamCaseSelection],
) -> list[upstream_inventory.UpstreamCaseSelection]:
    return [selection for selection in selections if selection.suite == suite]
