from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t234_slot_hash_benchmark_script_runs_and_emits_json(tmp_path) -> None:
    json_path = tmp_path / "slot_hash_benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_slot_vs_hash.py"),
            "--iterations",
            "20000",
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
    assert "slot-vs-hash microbenchmark" in result.stdout
    assert "median speedup (slot vs hash):" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "slot" in payload
    assert "hash" in payload
    assert payload["slot"]["mode"] == "slot"
    assert payload["hash"]["mode"] == "hash"
    assert payload["slot"]["iterations"] == 20000
    assert payload["hash"]["iterations"] == 20000
    assert payload["median_speedup_slot_vs_hash"] > 0.0
