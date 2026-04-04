from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t178_pyproject_records_current_testing_markers() -> None:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"compat: full compatibility suite coverage, including corpus and differential checks"' in pyproject_text
    assert '"compat_upstream: upstream-suite-derived compatibility coverage"' in pyproject_text
    assert '"compat_local: repo-owned supplemental compatibility corpus coverage"' in pyproject_text
    assert '"corpus: single-engine compatibility corpus coverage"' in pyproject_text
    assert '"smoke: reserved for smoke coverage"' in pyproject_text
    assert '"core:' not in pyproject_text
    assert '"compat_reference:' not in pyproject_text
    assert '"compat_corpus:' not in pyproject_text


def test_t178_testing_doc_makes_current_command_surfaces_and_debt_explicit() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert '- `uv run pytest -q -m "not compat"`' in testing_text
    assert "- `uv run pytest -m compat_upstream`" in testing_text
    assert "- `uv run pytest -m compat_local`" in testing_text
    assert '`uv run pytest -q -m "not compat"` is the current fast default suite' in testing_text
    assert "`compat_upstream` is the current marker for the reference-engine differential gate" in testing_text
    assert "`compat_local` is the current marker for the repo-owned supplemental corpus coverage" in testing_text
    assert "`corpus` remains available as a manual harness command" in testing_text
    assert "`tests/test_p12_release_smoke.py` and as the `smoke` marker" in testing_text


def test_t178_testing_doc_records_current_local_corpus_overlap() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    baseline_text = (ROOT / "tests" / "test_p10_compat_baselines.py").read_text(encoding="utf-8")
    supported_text = (ROOT / "tests" / "test_p11_supported_compatibility_corpus.py").read_text(encoding="utf-8")

    assert "`tests/test_p10_compat_baselines.py` and `tests/test_p11_supported_compatibility_corpus.py`" in testing_text
    assert "@pytest.mark.compat_local" in baseline_text
    assert "@pytest.mark.compat_local" in supported_text
    assert "run_case_differential" in baseline_text
    assert "run_case_differential" in supported_text
    assert "differential_validation_errors" in baseline_text
    assert "differential_validation_errors" in supported_text


def test_t178_testing_refactor_plan_uses_renamed_target_vocabulary() -> None:
    plan_text = (ROOT / "testing-refactor.md").read_text(encoding="utf-8")

    assert "- `compat_upstream` -> `compat_reference`" in plan_text
    assert "- `compat_local` -> `compat_corpus`" in plan_text
    assert "- `core` for the default fast repo test surface" in plan_text
    assert "uv run pytest -q -m core" in plan_text
    assert "uv run pytest -m compat_reference" in plan_text
    assert "uv run pytest -m compat_corpus" in plan_text
