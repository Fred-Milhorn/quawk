"""Selected upstream compatibility slice executed through the upstream harness."""

from __future__ import annotations

import pytest

from quawk.corpus import missing_engines
from quawk.upstream_suite import selected_upstream_cases, run_upstream_case_differential, upstream_validation_errors


@pytest.mark.compat
@pytest.mark.compat_upstream
@pytest.mark.parametrize("case", selected_upstream_cases(), ids=lambda case: case.id)
def test_upstream_compatibility_slice(case) -> None:
    missing = missing_engines()
    if missing:
        pytest.fail(f"missing differential engines: {', '.join(missing)}")

    result = run_upstream_case_differential(case)
    errors = upstream_validation_errors(result)
    assert not errors, "\n".join(errors)
