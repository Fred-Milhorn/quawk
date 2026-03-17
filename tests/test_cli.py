import subprocess

from quawk.cli import build_info


def run_quawk(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_quawk_help_exits_zero() -> None:
    result = run_quawk("--help")

    assert result.returncode == 0, result.stderr
    assert "usage: quawk" in result.stdout
    assert "--qk-version" in result.stdout


def test_quawk_version_exits_zero() -> None:
    result = run_quawk("--version")

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("quawk 0.1.0")


def test_quawk_qk_version_reports_runtime_details() -> None:
    result = run_quawk("--qk-version")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{build_info()}\n"


def test_quawk_requires_program_source() -> None:
    result = run_quawk()

    assert result.returncode == 2
    assert "missing AWK program text or -f progfile" in result.stderr


def test_quawk_execution_stub_returns_usage_error() -> None:
    result = run_quawk("BEGIN { print 1 }")

    assert result.returncode == 2
    assert result.stderr == "quawk: execution path not implemented yet\n"
