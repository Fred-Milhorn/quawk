from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t279_spec_records_the_remaining_corroboration_gap_baseline() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Remaining POSIX compatibility corroboration gaps | planned |" in spec_text
    assert "field rebuild corroborating anchors" in spec_text
    assert "record-target `gsub` skip" in spec_text
    assert "`rand()` corroboration" in spec_text


def test_t279_compatibility_doc_states_the_remaining_corroboration_scope() -> None:
    compatibility_text = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")

    assert "## P32 Corroboration Baseline" in compatibility_text
    assert "field rebuild is already implemented" in compatibility_text
    assert "record-target `gsub` remains a narrower reviewed backend skip" in compatibility_text
    assert "`rand()` remains direct-test-only" in compatibility_text


def test_t279_posix_record_pins_the_remaining_corroboration_baseline() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-279 P32 Corroboration Baseline Result" in posix_text
    assert "field rebuild is already implemented end to end" in posix_text
    assert "record-target `gsub` remains a narrower reviewed backend skip" in posix_text
    assert "deterministic seeded output" in posix_text


def test_t279_roadmap_marks_the_baseline_done_and_moves_to_t280() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "P30 and P31 are complete. We are currently implementing `P32`" in roadmap_text
    assert "| T-279 | P32 | P0 | Author the remaining POSIX corroboration-gap baseline | T-278 | `docs/compatibility.md`, `SPEC.md`, and focused tests explicitly list the remaining corroboration-only gaps for field rebuild, record-target `gsub`, and `rand()` | done |" in roadmap_text
    assert "| T-280 | P32 | P0 | Re-audit and resolve the field rebuild corroboration anchors | T-279 |" in roadmap_text
