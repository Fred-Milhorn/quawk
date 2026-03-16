from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent


def test_quawk_exits_zero() -> None:
    result = subprocess.run(
        ["quawk"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello world\n"
