from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t188_repo_layout_has_only_the_compat_namespace_for_compatibility_tooling() -> None:
    assert not (ROOT / "scripts" / "upstream_compat.py").exists()

    for relative_path in (
        "src/quawk/compat/__init__.py",
        "src/quawk/compat/corpus.py",
        "src/quawk/compat/upstream_compat.py",
        "src/quawk/compat/upstream_inventory.py",
        "src/quawk/compat/upstream_suite.py",
        "src/quawk/compat/upstream_divergence.py",
        "src/quawk/compat/upstream_audit.py",
    ):
        assert (ROOT / relative_path).is_file(), relative_path

    for relative_path in (
        "src/quawk/corpus.py",
        "src/quawk/upstream_compat.py",
        "src/quawk/upstream_inventory.py",
        "src/quawk/upstream_suite.py",
        "src/quawk/upstream_divergence.py",
        "src/quawk/upstream_audit.py",
    ):
        assert not (ROOT / relative_path).exists(), relative_path


def test_t188_module_entrypoint_runs_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "quawk.compat.upstream_compat", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Bootstrap pinned One True Awk and gawk builds" in result.stdout
