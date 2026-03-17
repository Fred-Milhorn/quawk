from __future__ import annotations

from pathlib import Path

from quawk.phase_gate import validate_repo


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_phase_gate_passes_without_manifests(tmp_path: Path) -> None:
    write_file(
        tmp_path / "docs" / "roadmap.md",
        "| T-001 | P0 | P0 | Scaffold | none | done | done |\n",
    )

    assert validate_repo(tmp_path) == []


def test_phase_gate_rejects_missing_known_gap_tracking(tmp_path: Path) -> None:
    write_file(
        tmp_path / "docs" / "roadmap.md",
        "| T-001 | P0 | P0 | Scaffold | none | done | in_progress |\n",
    )
    write_file(tmp_path / "tests" / "fixtures" / "empty.txt", "")
    write_file(tmp_path / "tests" / "parser" / "regex.awk", "BEGIN { print 1 }\n")
    write_file(
        tmp_path / "tests" / "parser" / "case.toml",
        "\n".join(
            [
                'id = "parser.regex.division.001"',
                'phase = "P1"',
                'suite = "parser"',
                'status = "xfail"',
                'xfail_reason = "known_gap"',
                'program = "tests/parser/regex.awk"',
                'stdin = "tests/fixtures/empty.txt"',
                'tags = ["known-gap"]',
                "",
                "[expect]",
                'stdout = ""',
                'stderr_class = "syntax_error"',
                "exit = 2",
                "",
            ]
        ),
    )

    errors = validate_repo(tmp_path)

    assert len(errors) == 1
    assert errors[0].message == "known_gap manifests require tracking"


def test_phase_gate_rejects_phase_bootstrap_in_completed_phase(tmp_path: Path) -> None:
    write_file(
        tmp_path / "docs" / "roadmap.md",
        "| T-001 | P0 | P0 | Scaffold | none | done | done |\n",
    )
    write_file(tmp_path / "tests" / "fixtures" / "empty.txt", "")
    write_file(tmp_path / "tests" / "parser" / "regex.awk", "BEGIN { print 1 }\n")
    write_file(
        tmp_path / "tests" / "parser" / "case.toml",
        "\n".join(
            [
                'id = "parser.regex.division.001"',
                'phase = "P0"',
                'suite = "parser"',
                'status = "xfail"',
                'xfail_reason = "phase_bootstrap"',
                'program = "tests/parser/regex.awk"',
                'stdin = "tests/fixtures/empty.txt"',
                'tags = ["posix-required"]',
                "",
                "[expect]",
                'stdout = ""',
                'stderr_class = "syntax_error"',
                "exit = 2",
                "",
            ]
        ),
    )

    errors = validate_repo(tmp_path)

    assert len(errors) == 1
    assert "cannot keep phase_bootstrap manifests" in errors[0].message
