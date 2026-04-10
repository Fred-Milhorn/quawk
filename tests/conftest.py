from __future__ import annotations

import os

import pytest
from quawk import jit


def _forbidden_host_runtime(*args: object, **kwargs: object) -> int:
    raise AssertionError("the Python host runtime has been removed; tests should stay on the backend path")


if not hasattr(jit, "execute_host_runtime"):
    jit.execute_host_runtime = _forbidden_host_runtime  # type: ignore[attr-defined]
if not hasattr(jit, "collect_record_contexts"):
    jit.collect_record_contexts = _forbidden_host_runtime  # type: ignore[attr-defined]
if not hasattr(jit, "lower_input_aware_program_to_llvm_ir"):
    jit.lower_input_aware_program_to_llvm_ir = _forbidden_host_runtime  # type: ignore[attr-defined]


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark the default fast suite positively as `core`.

    Any test that is not part of the compatibility surfaces is part of the core
    suite. Applying the marker during collection keeps the test modules free of
    repetitive per-file `pytestmark` boilerplate.
    """
    run_roadmap_contract = os.getenv("QUAWK_RUN_ROADMAP_TESTS", "").lower() in {"1", "true", "yes", "on"}

    for item in items:
        if "compat" not in item.keywords:
            item.add_marker(pytest.mark.core)
        if "roadmap" in item.name.lower():
            item.add_marker(pytest.mark.roadmap_contract)
            if not run_roadmap_contract:
                item.add_marker(
                    pytest.mark.skip(
                        reason=(
                            "roadmap contract checks are disabled by default; set "
                            "QUAWK_RUN_ROADMAP_TESTS=1 to include them"
                        )
                    )
                )
