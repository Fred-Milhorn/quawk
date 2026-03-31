from __future__ import annotations

from pathlib import Path

import pytest

from quawk import upstream_divergence, upstream_inventory, upstream_suite
from quawk.corpus import NormalizedCorpusResult


def make_result(
    engine: str,
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> NormalizedCorpusResult:
    return NormalizedCorpusResult(
        engine=engine,
        command=(engine, "-f", "program.awk"),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def make_case_result(
    *,
    status: str,
) -> upstream_suite.UpstreamCaseResult:
    selection = upstream_inventory.UpstreamCaseSelection(
        suite="gawk",
        case_id="demo",
        path=Path("/tmp/demo.awk"),
        status="run",
        adapter="gawk-awk-ok",
        tags=(),
        reason=None,
    )
    case = upstream_suite.UpstreamCase(
        selection=selection,
        program_path=selection.path,
        cli_args=(),
        input_operands=(),
        oracle="reference-agreement",
        expectation=None,
    )
    match status:
        case "PASS":
            results = {
                "quawk": make_result("quawk", stdout="ok\n"),
                "one-true-awk": make_result("one-true-awk", stdout="ok\n"),
                "gawk-posix": make_result("gawk-posix", stdout="ok\n"),
            }
        case "FAIL":
            results = {
                "quawk": make_result("quawk", stdout="bad\n"),
                "one-true-awk": make_result("one-true-awk", stdout="ok\n"),
                "gawk-posix": make_result("gawk-posix", stdout="ok\n"),
            }
        case "REF-DISAGREE":
            results = {
                "quawk": make_result("quawk", stdout="q\n"),
                "one-true-awk": make_result("one-true-awk", stdout="a\n"),
                "gawk-posix": make_result("gawk-posix", stdout="b\n"),
            }
        case _:
            raise AssertionError(f"unhandled status: {status}")
    return upstream_suite.UpstreamCaseResult(case=case, results_by_engine=results)


def make_root_with_selection(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path
    selection_dir = root / "tests" / "upstream"
    selection_dir.mkdir(parents=True)
    (root / "docs").mkdir()
    case_path = root / "third_party" / "gawk" / "test" / "demo.awk"
    case_path.parent.mkdir(parents=True)
    case_path.write_text('BEGIN { print 1 }\n', encoding="utf-8")
    (case_path.with_suffix(".ok")).write_text("1\n", encoding="utf-8")
    (selection_dir / "selection.toml").write_text(
        '\n'.join(
            [
                "[[case]]",
                'suite = "gawk"',
                'case_id = "demo"',
                'path = "third_party/gawk/test/demo.awk"',
                'status = "run"',
                'adapter = "gawk-awk-ok"',
                'tags = ["posix"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    notes_path = root / "docs" / "compatibility.md"
    notes_path.write_text(
        '\n'.join(
            [
                "# Compatibility Plan",
                "",
                "<!-- upstream-divergence: demo-known-gap -->",
                "## Demo known gap",
                "",
            ]
        ),
        encoding="utf-8",
    )
    manifest_path = selection_dir / "divergences.toml"
    return root, manifest_path, notes_path


def test_load_upstream_divergence_manifest_accepts_empty_checked_in_manifest() -> None:
    assert upstream_divergence.load_upstream_divergence_manifest() == {}


def test_load_upstream_divergence_manifest_rejects_unknown_runnable_cases(tmp_path: Path) -> None:
    root, manifest_path, notes_path = make_root_with_selection(tmp_path)
    manifest_path.write_text(
        '\n'.join(
            [
                "[[divergence]]",
                'suite = "gawk"',
                'case_id = "unknown"',
                'classification = "known-gap"',
                'decision = "fix-later"',
                'summary = "demo"',
                'last_verified_upstream_commit = "abcdef1"',
                'notes_ref = "demo-known-gap"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown runnable case"):
        upstream_divergence.load_upstream_divergence_manifest(root=root, path=manifest_path, notes_path=notes_path)


def test_load_upstream_divergence_manifest_requires_matching_note_marker(tmp_path: Path) -> None:
    root, manifest_path, notes_path = make_root_with_selection(tmp_path)
    notes_path.write_text("# Compatibility Plan\n", encoding="utf-8")
    manifest_path.write_text(
        '\n'.join(
            [
                "[[divergence]]",
                'suite = "gawk"',
                'case_id = "demo"',
                'classification = "known-gap"',
                'decision = "fix-later"',
                'summary = "demo"',
                'last_verified_upstream_commit = "abcdef1"',
                'notes_ref = "demo-known-gap"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing compatibility note marker"):
        upstream_divergence.load_upstream_divergence_manifest(root=root, path=manifest_path, notes_path=notes_path)


def test_upstream_validation_errors_allow_classified_known_gap_failures() -> None:
    result = make_case_result(status="FAIL")
    divergences = {
        "gawk:demo": upstream_divergence.UpstreamDivergenceEntry(
            suite="gawk",
            case_id="demo",
            classification="known-gap",
            decision="fix-later",
            summary="demo",
            last_verified_upstream_commit="abcdef1",
            notes_ref="demo-known-gap",
        )
    }

    assert upstream_suite.upstream_validation_errors(result, divergences) == []


def test_upstream_validation_errors_reject_stale_divergence_entries() -> None:
    result = make_case_result(status="PASS")
    divergences = {
        "gawk:demo": upstream_divergence.UpstreamDivergenceEntry(
            suite="gawk",
            case_id="demo",
            classification="known-gap",
            decision="fix-later",
            summary="demo",
            last_verified_upstream_commit="abcdef1",
            notes_ref="demo-known-gap",
        )
    }

    assert upstream_suite.upstream_validation_errors(result, divergences) == [
        "stale divergence manifest entry: known-gap - demo"
    ]


def test_upstream_validation_errors_keep_posix_required_fix_failures_blocking() -> None:
    result = make_case_result(status="FAIL")
    divergences = {
        "gawk:demo": upstream_divergence.UpstreamDivergenceEntry(
            suite="gawk",
            case_id="demo",
            classification="posix-required-fix",
            decision="fix-now",
            summary="demo",
            last_verified_upstream_commit="abcdef1",
            notes_ref="demo-known-gap",
        )
    }

    errors = upstream_suite.upstream_validation_errors(result, divergences)
    assert errors[0] == "classified required upstream failure: posix-required-fix [fix-now] - demo"


def test_upstream_validation_errors_allow_only_reference_disagreement_entries_for_ref_disagree() -> None:
    result = make_case_result(status="REF-DISAGREE")
    divergences = {
        "gawk:demo": upstream_divergence.UpstreamDivergenceEntry(
            suite="gawk",
            case_id="demo",
            classification="known-gap",
            decision="fix-later",
            summary="demo",
            last_verified_upstream_commit="abcdef1",
            notes_ref="demo-known-gap",
        )
    }

    assert upstream_suite.upstream_validation_errors(result, divergences) == [
        "stale divergence manifest entry: known-gap - demo"
    ]
