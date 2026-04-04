from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t179_pyproject_declares_the_renamed_testing_markers() -> None:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"core: default fast repo test surface excluding compatibility suites"' in pyproject_text
    assert '"compat_reference: reference-engine differential compatibility coverage"' in pyproject_text
    assert '"compat_corpus: repo-owned supplemental compatibility corpus coverage"' in pyproject_text
    assert '"compat: full compatibility suite coverage, including corpus and differential checks"' in pyproject_text
    assert '"compat_upstream:' not in pyproject_text
    assert '"compat_local:' not in pyproject_text


def test_t179_testing_doc_uses_the_renamed_command_vocabulary() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "- `core` is the default fast repo suite" in testing_text
    assert "- `compat_reference` is the primary compatibility authority" in testing_text
    assert "- `compat_corpus` is the repo-owned supplemental corpus" in testing_text
    assert "- `uv run pytest -q -m core`" in testing_text
    assert "- `uv run pytest -m compat_reference`" in testing_text
    assert "- `uv run pytest -m compat_corpus`" in testing_text
    assert "`compat_upstream`" not in testing_text
    assert "`compat_local`" not in testing_text
    assert '`uv run pytest -q -m "not compat"`' not in testing_text


def test_t179_workflows_run_the_renamed_pytest_surfaces() -> None:
    ci_fast_text = (ROOT / ".github" / "workflows" / "ci-fast.yml").read_text(encoding="utf-8")
    compat_text = (ROOT / ".github" / "workflows" / "compat-upstream.yml").read_text(encoding="utf-8")

    assert 'uv run pytest -q -m core' in ci_fast_text
    assert 'uv run pytest -m compat_reference' in compat_text
    assert '"not compat"' not in ci_fast_text
    assert "compat_upstream" not in compat_text


def test_t179_compatibility_tests_use_the_renamed_markers() -> None:
    corpus_text = (ROOT / "tests" / "test_corpus.py").read_text(encoding="utf-8")
    baseline_text = (ROOT / "tests" / "test_p10_compat_baselines.py").read_text(encoding="utf-8")
    supported_text = (ROOT / "tests" / "test_p11_supported_compatibility_corpus.py").read_text(encoding="utf-8")
    upstream_text = (ROOT / "tests" / "test_p11_upstream_compatibility_subset.py").read_text(encoding="utf-8")
    conftest_text = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")

    assert "pytest.mark.compat_corpus" in corpus_text
    assert "@pytest.mark.compat_corpus" in baseline_text
    assert "@pytest.mark.compat_corpus" in supported_text
    assert "@pytest.mark.compat_reference" in upstream_text
    assert "compat_local" not in corpus_text + baseline_text + supported_text
    assert "compat_upstream" not in upstream_text
    assert 'pytest.mark.core' in conftest_text
    assert '"compat" not in item.keywords' in conftest_text
