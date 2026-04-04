# Corpus-runner tests.
# This repo-owned corpus is a supplemental local regression surface,
# including strict xfail coverage for known unsupported behaviors.

from __future__ import annotations

import pytest

from quawk.corpus import CorpusCase, compare_case, load_cases, run_case

pytestmark = [pytest.mark.compat, pytest.mark.compat_corpus]


def build_case_params() -> list[pytest.ParameterSet]:
    """Create pytest parameters for all known corpus cases."""
    params: list[pytest.ParameterSet] = []
    for case in load_cases():
        marks: list[object] = []
        if case.xfail_reason is not None:
            marks.append(pytest.mark.xfail(strict=True, reason=case.xfail_reason))
        params.append(pytest.param(case, id=case.id, marks=marks))
    return params


@pytest.mark.corpus
@pytest.mark.parametrize("case", build_case_params())
def test_corpus_case(case: CorpusCase) -> None:
    result = run_case(case)
    mismatches = compare_case(case, result)
    assert not mismatches, "\n".join(mismatches)
