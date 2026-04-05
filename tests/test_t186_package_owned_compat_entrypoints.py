from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t186_testing_doc_records_package_owned_entrypoints_and_remaining_cleanup() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "Current transition state after `T-186`:" in testing_text
    assert "`uv run quawk-upstream bootstrap`" in testing_text
    assert "`uv run python -m quawk.compat.upstream_compat bootstrap`" in testing_text
    assert "the stable" in testing_text and "`uv run corpus ...` command" in testing_text
    assert "contributor docs and CI still reference the removed wrapper command" in testing_text
    assert "top-level compatibility wrapper modules still exist for transition" in testing_text


def test_t186_pyproject_uses_package_owned_entrypoints() -> None:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'corpus = "quawk.compat.corpus:main"' in pyproject_text
    assert 'quawk-upstream = "quawk.compat.upstream_compat:main"' in pyproject_text
    assert 'corpus = "quawk.corpus:main"' not in pyproject_text


def test_t186_wrapper_script_is_removed_but_transition_wrappers_remain() -> None:
    assert not (ROOT / "scripts" / "upstream_compat.py").exists()

    for relative_path in (
        "src/quawk/corpus.py",
        "src/quawk/upstream_compat.py",
        "src/quawk/upstream_inventory.py",
        "src/quawk/upstream_suite.py",
        "src/quawk/upstream_divergence.py",
        "src/quawk/upstream_audit.py",
    ):
        assert (ROOT / relative_path).is_file(), relative_path


def test_t186_new_namespace_imports_and_compat_wrappers_both_resolve() -> None:
    compat_inventory = importlib.import_module("quawk.compat.upstream_inventory")
    wrapper_inventory = importlib.import_module("quawk.upstream_inventory")
    compat_corpus = importlib.import_module("quawk.compat.corpus")
    wrapper_corpus = importlib.import_module("quawk.corpus")

    assert compat_inventory.load_upstream_selection_manifest is wrapper_inventory.load_upstream_selection_manifest
    assert compat_corpus.differential_corpus_cases is wrapper_corpus.differential_corpus_cases


def test_t186_module_entrypoint_runs_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "quawk.compat.upstream_compat", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Bootstrap pinned One True Awk and gawk builds" in result.stdout


def test_t186_roadmap_marks_the_entrypoint_cleanup_done_and_advances_to_t187() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P17 compatibility tooling namespace cleanup" in roadmap_text
    assert "`T-186` is complete. The next implementation step is the import, doc, and CI" in roadmap_text
    assert "- `T-187` update imports, tests, docs, and CI references to the new namespace" in roadmap_text
    assert "- `T-186` replace `scripts/upstream_compat.py` with package-owned entrypoints" not in roadmap_text
    assert "| T-186 | P17 | P0 | Replace `scripts/upstream_compat.py` with package-owned entrypoints | T-185 | The singleton wrapper is removed, a package-owned upstream bootstrap entrypoint exists, and the `corpus` command still resolves cleanly through the new namespace | done |" in roadmap_text
