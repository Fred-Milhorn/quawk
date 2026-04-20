from __future__ import annotations

from quawk.compat import upstream_inventory


def test_t211_reference_subset_already_contains_clean_p21_corrobating_anchors() -> None:
    runnable_case_ids = {
        f"{selection.suite}:{selection.case_id}"
        for selection in upstream_inventory.load_upstream_selection_manifest()
        if selection.status == "run"
    }

    assert "one-true-awk:p.7" in runnable_case_ids
    assert "one-true-awk:p.8" in runnable_case_ids
    assert "one-true-awk:p.21a" in runnable_case_ids
    assert "one-true-awk:t.next" in runnable_case_ids
