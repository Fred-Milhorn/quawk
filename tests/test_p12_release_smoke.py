"""P12 release-readiness smoke baselines."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UV_CACHE_DIR = ROOT / ".uv-test-cache"
VENV_BIN_DIR = ROOT / ".venv" / "bin"


def run_tool(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["UV_CACHE_DIR"] = str(UV_CACHE_DIR)
    env["PATH"] = f"{VENV_BIN_DIR}:{env.get('PATH', '')}"
    return subprocess.run(
        [tool, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.smoke
def test_uv_run_quawk_help_smoke() -> None:
    result = run_tool("quawk", "--help")

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert result.stderr == ""


@pytest.mark.smoke
def test_uv_run_corpus_list_smoke() -> None:
    result = run_tool("corpus", "--list")

    assert result.returncode == 0, result.stderr
    assert "begin_print_literal" in result.stdout
    assert result.stderr == ""


@pytest.mark.smoke
def test_uv_run_example_program_smoke() -> None:
    example_path = ROOT / "examples" / "hello.awk"
    result = run_tool("quawk", "-f", str(example_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello from quawk\n"
    assert result.stderr == ""


@pytest.mark.smoke
@pytest.mark.xfail(strict=True, reason="T-040: SPEC.md feature matrix is not committed yet")
def test_release_smoke_requires_spec_feature_matrix() -> None:
    spec_path = ROOT / "SPEC.md"

    assert spec_path.is_file(), "missing SPEC.md"


@pytest.mark.smoke
@pytest.mark.xfail(strict=True, reason="T-042: release checklist doc is not committed yet")
def test_release_smoke_requires_versioned_release_checklist() -> None:
    checklist_path = ROOT / "docs" / "release-checklist.md"

    assert checklist_path.is_file(), "missing docs/release-checklist.md"


@pytest.mark.smoke
@pytest.mark.xfail(strict=True, reason="T-042: changelog workflow artifact is not committed yet")
def test_release_smoke_requires_changelog_artifact() -> None:
    changelog_path = ROOT / "CHANGELOG.md"

    assert changelog_path.is_file(), "missing CHANGELOG.md"
