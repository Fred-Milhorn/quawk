"""Supplemental local compatibility baselines executed through the differential runner."""

from __future__ import annotations

import pytest

from quawk.corpus import (
    compatibility_baseline_cases,
    differential_validation_errors,
    load_divergence_manifest,
    missing_engines,
    run_case_differential,
)


@pytest.mark.compat
@pytest.mark.compat_local
@pytest.mark.parametrize("case", compatibility_baseline_cases(), ids=lambda case: case.id)
def test_compatibility_baseline(case) -> None:
    missing = missing_engines()
    if missing:
        pytest.fail(f"missing differential engines: {', '.join(missing)}")

    divergences = load_divergence_manifest()
    result = run_case_differential(case)
    errors = differential_validation_errors(result, divergences)
    assert not errors, "\n".join(errors)
