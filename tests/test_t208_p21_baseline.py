from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t208_spec_names_the_exact_p21_target_rows() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| P21 logical-or and broader comparison target | planned |" in spec_text
    assert "The exact next widening wave is `||`, `<=`, `>`, `>=`, and `!=`." in spec_text
    assert "| P21 inspection and routing target | planned |" in spec_text
    assert "`||`, `<=`, `>`, `>=`, and `!=` must gain ordinary public backend/runtime execution plus `--ir` / `--asm` support" in spec_text


def test_t208_plan_and_posix_docs_record_the_backend_only_p21_baseline() -> None:
    analysis_text = (ROOT / "docs" / "plans" / "expression-surface-widening-analysis.md").read_text(
        encoding="utf-8"
    )
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "## T-208 Baseline Result" in analysis_text
    assert "- logical-or: `||`" in analysis_text
    assert "- broader comparisons: `<=`, `>`, `>=`, `!=`" in analysis_text
    assert "public Python host execution is not an acceptable dependency for a widened" in analysis_text
    assert "representative parenthesized `||`, `<=`, `>`, `>=`, and `!=` programs still" in analysis_text
    assert "### T-208 P21 Baseline Result" in posix_text
    assert "- `||`" in posix_text
    assert "- `<=`, `>`, `>=`, `!=`" in posix_text
    assert "the current starting point is pinned with parenthesized expression programs" in posix_text
    assert "these forms do not become claimed until" in posix_text
    assert "ordinary public execution, `--ir`, and `--asm` all stay on the compiled" in posix_text


def test_t208_roadmap_marks_the_p21_baseline_done_and_advances_to_t209() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "Next deliverable: P21 logical-or and comparison widening" in roadmap_text
    assert "`T-197` through `T-207` are complete, and `T-208` now fixes the exact `P21`" in roadmap_text
    assert "- `T-209`: implement backend/runtime support for `||`" in roadmap_text
    assert "| T-208 | P21 | P0 | Author the backend-only baseline, target claims, and direct tests for logical-or and broader comparisons | T-207 | Failing direct tests and explicit `SPEC.md` target rows define the exact `||`, `<=`, `>`, `>=`, and `!=` forms to widen, and the baseline states that newly claimed forms may not depend on public Python host execution | done |" in roadmap_text
