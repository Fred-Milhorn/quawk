from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t182_testing_doc_reclassifies_corpus_as_a_manual_harness() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "Manual harness commands:" in testing_text
    assert "uv run corpus --list" in testing_text
    assert "uv run corpus demo_case" in testing_text
    assert "uv run corpus --differential demo_case" in testing_text
    assert "`corpus` remains available as a manual harness command for case discovery and targeted differential debugging" in testing_text


def test_t182_release_smoke_is_documented_via_the_smoke_marker() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
    checklist_text = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "uv run pytest -q -m smoke" in testing_text
    assert "uv run pytest -q -m smoke" in checklist_text
    assert "tests/test_p12_release_smoke.py" not in checklist_text
