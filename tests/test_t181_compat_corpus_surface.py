from __future__ import annotations

from pathlib import Path

from quawk.compat.corpus import compatibility_baseline_cases, differential_corpus_cases

ROOT = Path(__file__).resolve().parent.parent


def test_t181_local_differential_corpus_runs_through_one_shared_entrypoint() -> None:
    compat_corpus_text = (ROOT / "tests" / "test_compat_corpus.py").read_text(encoding="utf-8")

    assert (ROOT / "tests" / "test_compat_corpus.py").is_file()
    assert not (ROOT / "tests" / "test_p10_compat_baselines.py").exists()
    assert not (ROOT / "tests" / "test_p11_supported_compatibility_corpus.py").exists()
    assert "differential_corpus_cases" in compat_corpus_text
    assert "@pytest.mark.compat_corpus" in compat_corpus_text


def test_t181_compatibility_baseline_cases_are_still_covered_by_compat_corpus() -> None:
    baseline_ids = {case.id for case in compatibility_baseline_cases()}
    differential_ids = {case.id for case in differential_corpus_cases()}

    assert baseline_ids
    assert baseline_ids <= differential_ids
