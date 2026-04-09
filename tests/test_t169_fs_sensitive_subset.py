from __future__ import annotations

from quawk.compat.upstream_inventory import load_upstream_selection_manifest


def test_t169_promotes_clean_fs_sensitive_cases_and_promotes_p35_after_rebuild_closure() -> None:
    statuses = {
        (selection.suite, selection.case_id): (selection.status, selection.reason)
        for selection in load_upstream_selection_manifest()
    }

    for case_id in ("p.5", "p.5a", "p.36", "p.48", "p.50", "p.51", "p.52"):
        assert statuses[("one-true-awk", case_id)] == ("run", None)

    assert statuses[("one-true-awk", "p.35")] == ("run", None)
