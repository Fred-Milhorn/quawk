from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t249_numeric_loop_benchmark_script_runs_and_emits_json(tmp_path) -> None:
    json_path = tmp_path / "numeric_loop_benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_numeric_loop_fast_path.py"),
            "--iterations",
            "15000",
            "--repetitions",
            "3",
            "--warmups",
            "1",
            "--json",
            str(json_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "numeric-loop fast-path microbenchmark" in result.stdout
    assert "median speedup (fast vs fallback):" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "fast" in payload
    assert "fallback" in payload
    assert payload["fast"]["mode"] == "fast"
    assert payload["fallback"]["mode"] == "fallback"
    assert payload["fast"]["iterations"] == 15000
    assert payload["fallback"]["iterations"] == 15000
    assert payload["reference_output"] > 0.0
    assert payload["median_speedup_fast_vs_fallback"] > 0.0
