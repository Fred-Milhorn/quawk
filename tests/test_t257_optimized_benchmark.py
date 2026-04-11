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
            "--dataset-scale",
            "smoke",
            "--repetitions",
            "2",
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
    assert "optimized-vs-unoptimized benchmark suite" in result.stdout
    assert "geometric mean speedup (optimized vs unoptimized, end_to_end):" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset_scale"] == "smoke"
    assert payload["repetitions"] == 2
    assert payload["warmups"] == 1
    assert payload["geometric_mean_speedup_end_to_end"] > 0.0
    assert payload["geometric_mean_speedup_lli_only"] > 0.0

    workloads = payload["workloads"]
    assert len(workloads) == 5
    names = {workload["name"] for workload in workloads}
    assert names == {
        "scalar_fold_loop",
        "branch_rewrite_loop",
        "field_aggregate",
        "filter_transform",
        "multi_file_reduce",
    }

    for workload in workloads:
        assert workload["category"] in {"optimizer_kernel", "runtime_workload"}
        for family_name in ("end_to_end", "lli_only"):
            family = workload[family_name]
            assert family["optimized"]["mode"] == "optimized"
            assert family["unoptimized"]["mode"] == "unoptimized"
            assert family["reference_output"] != ""
            assert family["median_speedup_optimized_vs_unoptimized"] > 0.0
