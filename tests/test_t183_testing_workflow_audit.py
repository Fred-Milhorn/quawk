from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t183_testing_doc_rebaselines_to_the_final_p16_state() -> None:
    testing_text = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")

    assert "Current testing workflow after the `P16` cleanup:" in testing_text
    assert "Current remaining entrypoint debt before the rest of the planned `P16` cleanup:" not in testing_text
    assert "`.github/workflows/compat-reference.yml` runs `uv run pytest -m compat_reference`" in testing_text


def test_t183_release_checklist_uses_the_final_smoke_command() -> None:
    checklist_text = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "uv run pytest -q -m smoke" in checklist_text
    assert "tests/test_p12_release_smoke.py" not in checklist_text


def test_t183_workflows_use_the_final_testing_surface_names() -> None:
    ci_fast_text = (ROOT / ".github" / "workflows" / "ci-fast.yml").read_text(encoding="utf-8")
    compat_reference_text = (ROOT / ".github" / "workflows" / "compat-reference.yml").read_text(encoding="utf-8")

    assert "Run core pytest suite" in ci_fast_text
    assert 'uv run pytest -q -m core' in ci_fast_text
    assert "name: compat-reference" in compat_reference_text
    assert "Run reference compatibility subset" in compat_reference_text
    assert 'uv run pytest -m compat_reference' in compat_reference_text
    assert not (ROOT / ".github" / "workflows" / "compat-upstream.yml").exists()


def test_t183_roadmap_records_p16_complete() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "`P16` closeout is complete. No further testing-surface cleanup tasks are" in roadmap_text
    assert "| T-183 | P16 | P1 | Rebaseline testing docs and final workflow audit after the cleanup lands | T-180, T-181, T-182 | `docs/testing.md`, `docs/release-checklist.md`, and any remaining workflow references agree on the final testing surfaces with no stale old-marker wording | done |" in roadmap_text
