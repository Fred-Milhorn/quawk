from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t222_spec_names_the_exact_p24_target_rows() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P24 match operators and membership | implemented |" in spec_text
    assert "| P24 inspection and routing parity | implemented |" in spec_text
    assert "`~`, `!~`, pure ternary expressions" in spec_text
    assert "`in`, concatenation" in spec_text


def test_t222_plan_and_posix_docs_record_the_backend_only_p24_baseline() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## T-222 P24 Baseline Result" in analysis_text
    assert "- match operators: `~`, `!~`" in analysis_text
    assert "- membership: `expr in array`" in analysis_text
    assert "public Python host execution is not an acceptable dependency for a widened" in analysis_text
    assert "## T-223 And T-224 Backend Implementation Result" in analysis_text
    assert "## T-225 Inspection And Corroboration Result" in analysis_text
    assert "### T-222 P24 Baseline Result" in posix_text
    assert "- `~`, `!~`" in posix_text
    assert "- `expr in array`" in posix_text
    assert "### T-223 And T-224 P24 Backend Result" in posix_text
    assert "### T-225 P24 Inspection And Corroboration Result" in posix_text


def test_t222_roadmap_marks_the_p24_baseline_done_and_closes_the_phase() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "No active widening phase is currently scheduled." in roadmap_text
    assert "`T-222` through `T-226` now close the full `P24` wave" in roadmap_text
    assert "| T-222 | P24 | P0 | Author the backend-only baseline, target claims, and direct tests for match operators and membership | T-221 | Failing direct tests and explicit `SPEC.md` target rows define the `~`, `!~`, and `in` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
