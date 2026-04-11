from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t258_runtime_hot_paths_profile_script_runs_and_emits_json(tmp_path) -> None:
    json_path = tmp_path / "runtime_hot_paths_profile.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "profile_runtime_hot_paths.py"),
            "--dataset-scale",
            "smoke",
            "--workload",
            "field_aggregate",
            "--repetitions",
            "1",
            "--warmups",
            "0",
            "--json",
            str(json_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "runtime-hot-path profile" in result.stdout
    assert "aggregate top 10:" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset_scale"] == "smoke"
    assert payload["repetitions"] == 1
    assert payload["warmups"] == 0
    assert payload["top"] == 10

    workloads = payload["workloads"]
    assert len(workloads) == 1
    assert workloads[0]["name"] == "field_aggregate"
    assert workloads[0]["output"] != ""
    assert len(workloads[0]["top_functions"]) > 0

    top_functions = payload["top_functions"]
    assert len(top_functions) > 0
    assert top_functions[0]["rank"] == 1
    assert top_functions[0]["name"] != ""
    assert top_functions[0]["count"] > 0
