"""Supplemental local supported corpus executed through the differential runner."""

from __future__ import annotations

import pytest

from quawk.corpus import (
    differential_validation_errors,
    load_divergence_manifest,
    missing_engines,
    run_case_differential,
    supported_corpus_cases,
)


@pytest.mark.compat
@pytest.mark.compat_local
@pytest.mark.parametrize("case", supported_corpus_cases(), ids=lambda case: case.id)
def test_supported_compatibility_corpus(case) -> None:
    missing = missing_engines()
    if missing:
        pytest.fail(f"missing differential engines: {', '.join(missing)}")

    divergences = load_divergence_manifest()
    result = run_case_differential(case)
    errors = differential_validation_errors(result, divergences)
    assert not errors, "\n".join(errors)
