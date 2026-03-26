"""P10 compatibility baselines executed through the real differential runner."""

from __future__ import annotations

import pytest

from quawk.corpus import compatibility_baseline_cases, missing_engines, run_case_differential


@pytest.mark.compat
@pytest.mark.parametrize("case", compatibility_baseline_cases(), ids=lambda case: case.id)
def test_compatibility_baseline(case) -> None:
    missing = missing_engines()
    if missing:
        pytest.skip(f"missing differential engines: {', '.join(missing)}")

    result = run_case_differential(case)
    status = result.status()
    if status == "REF-DISAGREE":
        return
    assert status == "PASS", "\n".join(result.detail_lines())
