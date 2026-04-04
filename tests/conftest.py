from __future__ import annotations

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark the default fast suite positively as `core`.

    Any test that is not part of the compatibility surfaces is part of the core
    suite. Applying the marker during collection keeps the test modules free of
    repetitive per-file `pytestmark` boilerplate.
    """
    for item in items:
        if "compat" not in item.keywords:
            item.add_marker(pytest.mark.core)
