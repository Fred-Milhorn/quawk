from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t180_readme_uses_the_renamed_test_surface_vocabulary() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "`core` pytest suite" in readme_text
    assert "`compat_reference` subset" in readme_text
    assert "non-compatibility pytest suite" not in readme_text


def test_t180_contributing_commands_use_the_renamed_surfaces() -> None:
    contributing_text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "uv run pytest -q -m core" in contributing_text
    assert "uv run pytest -m compat_reference" in contributing_text
    assert "uv run pytest -m compat_corpus" in contributing_text
    assert "uv run pytest -m compat_upstream" not in contributing_text


def test_t180_getting_started_uses_the_reference_compatibility_command() -> None:
    getting_started_text = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")

    assert "uv run pytest -m compat_reference" in getting_started_text
    assert "fast `core` pytest suite" in getting_started_text
    assert "compat_upstream" not in getting_started_text


def test_t180_compatibility_doc_uses_the_renamed_surface_names() -> None:
    compatibility_text = (ROOT / "docs" / "compatibility.md").read_text(encoding="utf-8")

    assert "`compat_reference` is the primary compatibility authority" in compatibility_text
    assert "`compat_corpus` remains a fast supplemental regression suite" in compatibility_text
    assert "uv run pytest -m compat_reference" in compatibility_text
    assert "uv run pytest -m compat_corpus" in compatibility_text
    assert "`compat_upstream`" not in compatibility_text
    assert "`compat_local`" not in compatibility_text
