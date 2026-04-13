from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t282_spec_records_the_explicit_rand_policy() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Remaining POSIX compatibility corroboration gaps | implemented |" in spec_text
    assert "`rand()` remains direct-test-only under the checked-in reference-disagreement policy" in spec_text
    assert "final corroboration decision is now closed out" in spec_text


def test_t282_compatibility_and_posix_record_the_checked_in_policy() -> None:
    compatibility_text = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## P32 Corroboration Baseline" in compatibility_text
    assert "checked-in POSIX corroboration policy is now explicit" in compatibility_text
    assert "`rand()` remains direct-test-only under the checked-in reference-disagreement" in compatibility_text
    assert "### T-282 Rand Corroboration Policy Result" in posix_text
    assert "`rand()` stays direct-test-only under the checked-in reference-disagreement" in posix_text


def test_t282_plan_and_roadmap_record_the_policy_closeout() -> None:
    plan_text = (ROOT / "docs" / "plans" / "remaining-posix-compatibility-plan.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "## T-282 Result" in plan_text
    assert "The `rand()` corroboration strategy is now explicit:" in plan_text
    assert "| `rand()` corroboration strategy | resolved | The references disagree on deterministic seeded output, so the checked-in policy keeps `rand()` direct-test-only. | none |" in plan_text
    assert "| T-282 | P32 | P1 | Resolve the `rand()` compatibility strategy | T-279 | `rand()` has either a stable corroborating anchor or a checked-in classified reference-disagreement policy | done |" in roadmap_text
