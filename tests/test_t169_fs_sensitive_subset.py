from __future__ import annotations

from quawk.compat.upstream_inventory import load_upstream_selection_manifest


def test_t169_promotes_clean_fs_sensitive_cases_and_leaves_p35_reviewed() -> None:
    statuses = {
        (selection.suite, selection.case_id): (selection.status, selection.reason)
        for selection in load_upstream_selection_manifest()
    }

    for case_id in ("p.5", "p.5a", "p.36", "p.48", "p.50", "p.51", "p.52"):
        assert statuses[("one-true-awk", case_id)] == ("run", None)

    status, reason = statuses[("one-true-awk", "p.35")]
    assert status == "skip"
    assert reason is not None
    assert "$0` field-rebuild mismatch" in reason
