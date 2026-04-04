"""Selected upstream compatibility subset executed through the upstream harness."""

from __future__ import annotations

import pytest

from quawk.corpus import missing_engines
from quawk.upstream_divergence import load_upstream_divergence_manifest
from quawk.upstream_suite import selected_upstream_cases, run_upstream_case_differential, upstream_validation_errors


@pytest.mark.compat
@pytest.mark.compat_reference
@pytest.mark.parametrize("case", selected_upstream_cases(), ids=lambda case: case.id)
def test_upstream_compatibility_subset(case) -> None:
    missing = missing_engines()
    if missing:
        pytest.fail(f"missing differential engines: {', '.join(missing)}")

    divergences = load_upstream_divergence_manifest()
    result = run_upstream_case_differential(case)
    errors = upstream_validation_errors(result, divergences)
    assert not errors, "\n".join(errors)
