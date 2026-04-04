from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t157_spec_splits_cli_variable_rows() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| `-v` numeric scalar preassignment | implemented |" in spec_text
    assert "| `-v` string scalar preassignment | implemented |" in spec_text
    assert "| `-v name=value` | partial |" not in spec_text


def test_t157_spec_splits_output_surface_rows() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Single-argument `print expr` | implemented |" in spec_text
    assert "| Bare `print` / implicit `$0` | implemented |" in spec_text
    assert "| Multi-argument `print` | implemented |" in spec_text
    assert "| `OFS` / `ORS` driven print behavior | implemented |" in spec_text
    assert "| `printf` basic execution | implemented |" in spec_text
    assert "| Full POSIX `printf` parity | implemented |" in spec_text
    assert "| Output redirection and pipe output | implemented |" in spec_text


def test_t157_spec_splits_builtin_and_backend_rows() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Core builtin variables | implemented |" in spec_text
    assert "| Output separator builtin variables | implemented |" in spec_text
    assert "| Formatting builtin variables | implemented |" in spec_text
    assert "| Argument, environment, and match-result builtin variables | implemented |" in spec_text
    assert "| Input separator builtin variables | implemented |" in spec_text
    assert "| Current builtin subset | implemented |" in spec_text
    assert "| POSIX string and regex builtins | implemented |" in spec_text
    assert "| POSIX numeric and system builtins | implemented |" in spec_text
    assert "| `getline` | implemented |" in spec_text
    assert "| Backend parity for broader frontend-admitted POSIX forms | partial |" in spec_text
    assert "| Builtin variables | implemented |" not in spec_text
    assert "| Builtins | partial |" not in spec_text
    assert "| Remaining POSIX builtin variables | implemented |" not in spec_text
