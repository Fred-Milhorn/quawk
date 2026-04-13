from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t218_spec_names_the_exact_p23_target_rows() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P23 ternary | implemented |" in spec_text
    assert "ternary expressions over the current claimed numeric/string subset" in spec_text
    assert "| P24 match operators and membership | implemented |" in spec_text


def test_t218_plan_and_posix_docs_record_the_backend_only_p23_baseline() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## T-218 P23 Baseline Result" in analysis_text
    assert "pure ternary expressions over the current claimed numeric/string subset" in analysis_text
    assert "## T-219 Backend Implementation Result" in analysis_text
    assert "## T-220 Inspection And Corroboration Result" in analysis_text
    assert "## T-221 Public-Contract Rebaseline Result" in analysis_text
    assert "### T-218 P23 Baseline Result" in posix_text
    assert "### T-219 P23 Backend Result" in posix_text
    assert "### T-220 P23 Inspection And Corroboration Result" in posix_text
    assert "### T-221 P23 Public-Contract Rebaseline Result" in posix_text


def test_t218_roadmap_marks_the_p23_baseline_done_and_advances_to_p24() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-218 | P23 | P0 | Author the backend-only baseline, target claims, and direct tests for ternary expressions | T-217 | Failing direct tests and explicit `SPEC.md` target rows define the ternary forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
