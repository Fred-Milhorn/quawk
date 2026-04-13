from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t281_spec_records_gsub_as_promoted_corroboration() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "upstream corroboration includes runnable `sprintf` and record-target `gsub` coverage" in spec_text
    assert "record-target `gsub` skip" not in spec_text


def test_t281_compatibility_doc_records_the_promoted_record_target_gsub_anchor() -> None:
    compatibility_text = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")

    assert "## P32 Corroboration Baseline" in compatibility_text
    assert "record-target `gsub` is now promoted in the selected upstream subset" in compatibility_text


def test_t281_posix_and_roadmap_record_the_gsub_promotion() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "### T-281 Record-Target gsub Corroboration Result" in posix_text
    assert "the selected upstream `p.29` anchor is runnable" in posix_text
    assert "### T-281" in roadmap_text
    assert "| T-281 | P32 | P1 | Re-audit and resolve the record-target `gsub` reviewed skip | T-279 | The selected upstream `p.29` anchor is promoted, reclassified, or documented with a precise reviewed reason | done |" in roadmap_text
