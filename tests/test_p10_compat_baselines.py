"""P10 compatibility baselines tracked before the differential runner exists."""

from __future__ import annotations

import pytest

from quawk.corpus import CorpusCase, compatibility_baseline_cases

XF_REASON = "T-035 differential runner not implemented"


def build_case_params() -> list[pytest.ParameterSet]:
    """Create pytest parameters for the current compatibility baseline."""
    params: list[pytest.ParameterSet] = []
    for case in compatibility_baseline_cases():
        params.append(
            pytest.param(
                case,
                id=case.id,
                marks=pytest.mark.xfail(strict=True, reason=XF_REASON),
            )
        )
    return params


def run_differential_baseline(case: CorpusCase) -> None:
    """Placeholder for the P10 differential runner implementation."""
    raise NotImplementedError(
        "T-035 will execute compatibility baseline cases under "
        "quawk, one-true-awk, and gawk --posix"
    )


@pytest.mark.compat
@pytest.mark.parametrize("case", build_case_params())
def test_compatibility_baseline(case: CorpusCase) -> None:
    run_differential_baseline(case)
