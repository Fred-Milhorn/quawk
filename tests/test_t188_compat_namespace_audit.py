from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t188_docs_and_workflow_use_the_final_namespace_and_entrypoint_commands() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing_text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    getting_started_text = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")
    compatibility_text = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github" / "workflows" / "compat-reference.yml").read_text(encoding="utf-8")

    for text in (readme_text, contributing_text, getting_started_text, compatibility_text, workflow_text):
        assert "uv run quawk-upstream bootstrap" in text
        assert "scripts/upstream_compat.py" not in text

    assert "Current layout after `P17`:" in testing_text
    assert "`quawk.compat.upstream_suite`" in testing_text
    assert "`uv run quawk-upstream bootstrap`" in testing_text
    assert "`uv run python -m quawk.compat.upstream_compat bootstrap`" in testing_text
    assert "compatibility wrapper modules still exist" not in testing_text
    assert "Current transition state after `T-186`:" not in testing_text


def test_t188_repo_layout_has_only_the_compat_namespace_for_compatibility_tooling() -> None:
    assert not (ROOT / "scripts" / "upstream_compat.py").exists()

    for relative_path in (
        "src/quawk/compat/__init__.py",
        "src/quawk/compat/corpus.py",
        "src/quawk/compat/upstream_compat.py",
        "src/quawk/compat/upstream_inventory.py",
        "src/quawk/compat/upstream_suite.py",
        "src/quawk/compat/upstream_divergence.py",
        "src/quawk/compat/upstream_audit.py",
    ):
        assert (ROOT / relative_path).is_file(), relative_path

    for relative_path in (
        "src/quawk/corpus.py",
        "src/quawk/upstream_compat.py",
        "src/quawk/upstream_inventory.py",
        "src/quawk/upstream_suite.py",
        "src/quawk/upstream_divergence.py",
        "src/quawk/upstream_audit.py",
    ):
        assert not (ROOT / relative_path).exists(), relative_path


def test_t188_repo_refactor_doc_records_the_final_layout() -> None:
    refactor_text = (ROOT / "docs" / "history" / "repo-refactor.md").read_text(encoding="utf-8")

    assert "# Repository Refactor" in refactor_text
    assert "completed repository-layout refactor" in refactor_text
    assert "`scripts/upstream_compat.py` wrapper is gone" in refactor_text
    assert "`quawk-upstream`" in refactor_text
    assert "`quawk.compat.corpus:main`" in refactor_text
    assert "the temporary top-level compatibility wrappers used during the transition are" in refactor_text


def test_t188_module_entrypoint_runs_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "quawk.compat.upstream_compat", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Bootstrap pinned One True Awk and gawk builds" in result.stdout


def test_t188_roadmap_records_p17_complete() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-187 | P17 | P1 | Update imports, tests, docs, and CI references to the new namespace and commands | T-185, T-186 | Internal imports, pytest modules, contributor docs, and CI bootstrap commands all use `quawk.compat` and the package-owned entrypoints consistently | done |" in roadmap_text
    assert "| T-188 | P17 | P1 | Rebaseline repo layout docs and final namespace audit after the refactor lands | T-187 | `docs/history/repo-refactor.md`, roadmap/docs, and focused compatibility-tooling regressions agree on the final layout, and no stale flat-module or wrapper-script references remain | done |" in roadmap_text
    assert "`P17` closeout is complete. No further compatibility-tooling namespace" in roadmap_text
    assert "Next deliverable: P17 compatibility tooling namespace cleanup" not in roadmap_text
    assert "Immediate next tasks:" not in roadmap_text
