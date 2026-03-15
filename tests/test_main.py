from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent


def test_main_script_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello world\n"
