from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "benchmark_noaa_runtime_gap.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("benchmark_noaa_runtime_gap", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_t325_noaa_benchmark_dataset_generation_is_deterministic(tmp_path: Path) -> None:
    module = load_script_module()
    scale = module.SCALE_CONFIGS["smoke"]

    first = module.build_dataset(scale, tmp_path / "first")
    second = module.build_dataset(scale, tmp_path / "second")

    assert first.startup_stdin_text == second.startup_stdin_text
    assert first.steady_stdin_text == second.steady_stdin_text
    assert first.metadata_path.read_text(encoding="utf-8") == second.metadata_path.read_text(encoding="utf-8")


def test_t325_noaa_benchmark_builds_expected_engine_commands(tmp_path: Path) -> None:
    module = load_script_module()
    metadata_path = tmp_path / "ghcnd-stations.txt"
    metadata_path.write_text("", encoding="utf-8")

    commands = module.build_engine_commands(metadata_path)

    assert set(commands) == {"gawk_posix", "quawk_uv", "quawk_direct"}
    assert commands["gawk_posix"].argv[1] == "--posix"
    assert commands["quawk_uv"].argv[:3] == (commands["quawk_uv"].argv[0], "run", "quawk")
    assert commands["quawk_direct"].argv[0].endswith("/.venv/bin/quawk")
    for command in commands.values():
        assert command.argv[-2] == str(metadata_path)
        assert command.argv[-1] == "-"


def test_t325_noaa_benchmark_script_runs_and_emits_json(tmp_path: Path) -> None:
    json_path = tmp_path / "noaa_runtime_gap_benchmark.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
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
    assert "noaa-runtime-gap benchmark" in result.stdout
    assert "startup_heavy:" in result.stdout
    assert "steady_state:" in result.stdout
    assert json_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["dataset_scale"] == "smoke"
    assert payload["repetitions"] == 1
    assert payload["warmups"] == 0
    assert payload["dataset"]["selected_station_count"] == 2
    assert payload["dataset"]["steady_repeat_factor"] == 2
    assert payload["startup_heavy"]["median_quawk_relative_to_gawk"] > 0.0
    assert payload["steady_state"]["median_quawk_relative_to_gawk"] > 0.0
    assert payload["startup_heavy"]["reference_output"] != ""
    assert payload["steady_state"]["reference_output"] != ""


def test_t325_noaa_benchmark_script_can_run_steady_state_only(tmp_path: Path) -> None:
    json_path = tmp_path / "noaa_runtime_gap_benchmark_steady.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dataset-scale",
            "smoke",
            "--family",
            "steady_state",
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
    assert "family=steady_state" in result.stdout
    assert "startup_heavy:" not in result.stdout
    assert "steady_state:" in result.stdout

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["family"] == "steady_state"
    assert "startup_heavy" not in payload
    assert payload["steady_state"]["median_quawk_relative_to_gawk"] > 0.0
