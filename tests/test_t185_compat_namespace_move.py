from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t185_testing_doc_records_the_transition_state_after_the_namespace_move() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "Current transition state after `T-185`:" in testing_text
    assert "the real compatibility and corpus implementations now live under" in testing_text
    assert "the selected runnable upstream subset now executes through" in testing_text
    assert "compatibility wrapper modules still exist at the old top-level import paths" in testing_text
    assert "`uv run python scripts/upstream_compat.py bootstrap`" in testing_text
    assert "package-owned entrypoints still need to replace the wrapper" in testing_text


def test_t185_repo_layout_moves_compatibility_modules_under_the_new_namespace() -> None:
    assert (ROOT / "src" / "quawk" / "compat").is_dir()
    assert (ROOT / "src" / "quawk" / "compat" / "__init__.py").is_file()
    assert (ROOT / "scripts" / "upstream_compat.py").is_file()

    for relative_path in (
        "src/quawk/compat/corpus.py",
        "src/quawk/compat/upstream_compat.py",
        "src/quawk/compat/upstream_inventory.py",
        "src/quawk/compat/upstream_suite.py",
        "src/quawk/compat/upstream_divergence.py",
        "src/quawk/compat/upstream_audit.py",
        "src/quawk/corpus.py",
        "src/quawk/upstream_compat.py",
        "src/quawk/upstream_inventory.py",
        "src/quawk/upstream_suite.py",
        "src/quawk/upstream_divergence.py",
        "src/quawk/upstream_audit.py",
    ):
        assert (ROOT / relative_path).is_file(), relative_path


def test_t185_new_namespace_imports_and_compat_wrappers_both_resolve() -> None:
    compat_inventory = importlib.import_module("quawk.compat.upstream_inventory")
    wrapper_inventory = importlib.import_module("quawk.upstream_inventory")
    compat_corpus = importlib.import_module("quawk.compat.corpus")
    wrapper_corpus = importlib.import_module("quawk.corpus")

    assert compat_inventory.load_upstream_selection_manifest is wrapper_inventory.load_upstream_selection_manifest
    assert compat_corpus.differential_corpus_cases is wrapper_corpus.differential_corpus_cases


def test_t185_roadmap_marks_the_namespace_move_done_and_advances_to_t186() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P17 compatibility tooling namespace cleanup" in roadmap_text
    assert "`T-185` is complete. The next implementation step is the entrypoint cleanup in" in roadmap_text
    assert "- `T-186` replace `scripts/upstream_compat.py` with package-owned entrypoints" in roadmap_text
    assert "- `T-185` create `quawk.compat` and move the corpus/upstream modules into the" not in roadmap_text
    assert "| T-185 | P17 | P0 | Create `quawk.compat` and move corpus/upstream modules into the dedicated namespace | T-184 | `corpus`, `upstream_compat`, `upstream_inventory`, `upstream_suite`, `upstream_divergence`, and `upstream_audit` live under `src/quawk/compat/` with no functional behavior change | done |" in roadmap_text
