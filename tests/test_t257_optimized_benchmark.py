from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t257_optimized_vs_unoptimized_benchmark_script_runs_and_emits_json(tmp_path) -> None:
    json_path = tmp_path / "optimized_vs_unoptimized_benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_optimized_vs_unoptimized.py"),
            "--iterations",
            "10000",
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
    assert "optimized-vs-unoptimized microbenchmark" in result.stdout
    assert "median speedup (optimized vs unoptimized):" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "optimized" in payload
    assert "unoptimized" in payload
    assert payload["optimized"]["mode"] == "optimized"
    assert payload["unoptimized"]["mode"] == "unoptimized"
    assert payload["optimized"]["iterations"] == 10000
    assert payload["unoptimized"]["iterations"] == 10000
    assert payload["reference_output"] != ""
    assert payload["median_speedup_optimized_vs_unoptimized"] > 0.0
