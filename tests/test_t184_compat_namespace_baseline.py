from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t184_testing_doc_records_current_flat_compatibility_layout_and_target_state() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "## Compatibility Tooling Layout" in testing_text
    assert "`src/quawk/corpus.py` lives in the top-level package namespace" in testing_text
    assert "`src/quawk/upstream_compat.py`, `src/quawk/upstream_inventory.py`," in testing_text
    assert "the selected runnable upstream subset is still executed through" in testing_text
    assert "`uv run python scripts/upstream_compat.py bootstrap`" in testing_text
    assert "corpus and upstream-compatibility tooling move under `quawk.compat`" in testing_text
    assert "package-owned entrypoints replace the wrapper while the `corpus` command stays" in testing_text


def test_t184_repo_refactor_plan_records_current_wrapper_and_target_namespace() -> None:
    refactor_text = (ROOT / "repo-refactor.md").read_text(encoding="utf-8")

    assert "`scripts/upstream_compat.py` is the only file in `scripts/`" in refactor_text
    assert "`src/quawk/upstream_compat.py`" in refactor_text
    assert "`src/quawk/compat/`" in refactor_text
    assert "`quawk-upstream = \"quawk.compat.upstream_compat:main\"`" in refactor_text
    assert "`quawk.compat.corpus:main`" in refactor_text
    assert "`uv run pytest -q -m core`" in refactor_text
    assert "`uv run pytest -m compat_reference`" in refactor_text


def test_t184_current_files_match_the_pre_refactor_layout() -> None:
    assert (ROOT / "scripts" / "upstream_compat.py").is_file()
    assert not (ROOT / "src" / "quawk" / "compat").exists()

    for relative_path in (
        "src/quawk/corpus.py",
        "src/quawk/upstream_compat.py",
        "src/quawk/upstream_inventory.py",
        "src/quawk/upstream_suite.py",
        "src/quawk/upstream_divergence.py",
        "src/quawk/upstream_audit.py",
    ):
        assert (ROOT / relative_path).is_file(), relative_path


def test_t184_roadmap_marks_p17_baseline_done_and_moves_to_t185() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P17 compatibility tooling namespace cleanup" in roadmap_text
    assert "- `T-185` create `quawk.compat` and move the corpus/upstream modules into the" in roadmap_text
    assert "- `T-184` author the compatibility-tooling namespace baseline and target" not in roadmap_text
    assert "| T-184 | P17 | P0 | Author the compatibility-tooling namespace baseline and import audit | T-183 | Tests and docs make the current flat compatibility module layout, wrapper script dependency, and target `quawk.compat` namespace explicit before implementation | done |" in roadmap_text
