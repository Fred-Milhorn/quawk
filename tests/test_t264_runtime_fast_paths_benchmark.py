from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t264_runtime_fast_path_benchmark_script_runs_and_emits_json(tmp_path: Path) -> None:
    json_path = tmp_path / "runtime_fast_path_benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_runtime_fast_paths.py"),
            "--dataset-scale",
            "smoke",
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
    assert "runtime-fast-path benchmark suite" in result.stdout
    assert "geometric mean speedup (fast path vs baseline, lli_only):" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset_scale"] == "smoke"
    assert payload["repetitions"] == 1
    assert payload["warmups"] == 0
    assert payload["geometric_mean_speedup_fast_path_vs_baseline"] > 0.0

    workloads = payload["workloads"]
    assert len(workloads) == 4
    names = {workload["name"] for workload in workloads}
    assert names == {
        "string_concat_loop",
        "field_aggregate",
        "filter_transform",
        "multi_file_reduce",
    }

    for workload in workloads:
        assert workload["category"] in {"string_kernel", "runtime_workload"}
        assert workload["reference_output"] != ""
        assert workload["median_speedup_fast_path_vs_baseline"] > 0.0
        for mode_name in ("baseline", "fast_path"):
            mode = workload[mode_name]
            assert mode["mode"] == mode_name
            assert mode["repetitions"] == 1

