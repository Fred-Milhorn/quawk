"""Benchmark the NOAA climate-report workload across startup-heavy and steady-state paths.

The harness runs the checked-in `examples/noaa-climate-report/climate_report.awk`
program against deterministic synthetic fixed-width NOAA-like input. It reports
two timing families:

- startup-heavy: `uv run quawk` versus `gawk --posix`
- steady-state: direct `.venv/bin/quawk` versus `gawk --posix` on repeated input
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOAA_PROGRAM = ROOT / "examples" / "noaa-climate-report" / "climate_report.awk"
TARGET_STATE = "AZ"
BENCHMARK_YEAR = 2023
BENCHMARK_FAMILY_CHOICES = ("both", "startup_heavy", "steady_state")


@dataclass(frozen=True)
class ScaleConfig:
    name: str
    selected_station_count: int
    noise_station_count: int
    steady_repeat_factor: int


@dataclass(frozen=True)
class PreparedDataset:
    metadata_path: Path
    startup_stdin_text: str
    steady_stdin_text: str
    selected_station_count: int
    noise_station_count: int
    startup_monthly_record_count: int
    steady_monthly_record_count: int


@dataclass(frozen=True)
class EngineCommand:
    name: str
    label: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class TimingSummary:
    mode: str
    repetitions: int
    warmups: int
    median_seconds: float
    p95_seconds: float
    min_seconds: float
    max_seconds: float


SCALE_CONFIGS = {
    "smoke": ScaleConfig(
        name="smoke",
        selected_station_count=2,
        noise_station_count=1,
        steady_repeat_factor=2,
    ),
    "medium": ScaleConfig(
        name="medium",
        selected_station_count=12,
        noise_station_count=4,
        steady_repeat_factor=20,
    ),
    "large": ScaleConfig(
        name="large",
        selected_station_count=36,
        noise_station_count=12,
        steady_repeat_factor=60,
    ),
}


def percentile(sorted_values: list[float], p: float) -> float:
    """Return percentile `p` for a sorted value list."""
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    if p <= 0.0:
        return sorted_values[0]
    if p >= 1.0:
        return sorted_values[-1]
    index = (len(sorted_values) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def summarize(mode: str, values: list[float], repetitions: int, warmups: int) -> TimingSummary:
    """Build one summary row for measured timings."""
    ordered = sorted(values)
    return TimingSummary(
        mode=mode,
        repetitions=repetitions,
        warmups=warmups,
        median_seconds=statistics.median(ordered),
        p95_seconds=percentile(ordered, 0.95),
        min_seconds=ordered[0],
        max_seconds=ordered[-1],
    )


def format_seconds(seconds: float) -> str:
    """Render one timing value in milliseconds with fixed precision."""
    return f"{seconds * 1000.0:.3f} ms"


def build_station_line(station_id: str, *, state: str, name: str, lat: float, lon: float, elev: float) -> str:
    """Return one fixed-width station metadata line."""
    return f"{station_id:<11} {lat:>8.4f} {lon:>9.4f} {elev:>6.1f} {state:<2} {name:<30}\n"


def build_day_slot(value: int, *, qflag: str = " ") -> str:
    """Return one 8-character NOAA day slot."""
    if qflag == " ":
        return f"{value:05d}   "
    return f"{value:05d} {qflag} "


def synthesize_day_value(
    station_index: int,
    month: int,
    day: int,
    element: str,
) -> tuple[int, str]:
    """Return one deterministic daily value plus quality flag."""
    base = (station_index * 97) + (month * 13) + day
    if (station_index + month + day) % 29 == 0:
        return -9999, " "
    if (station_index + (month * 3) + day) % 37 == 0:
        qflag = "X"
    else:
        qflag = " "

    if element == "TMAX":
        value = 180 + (base % 170)
    elif element == "TMIN":
        value = -40 + (base % 150)
    elif element == "PRCP":
        value = base % 400
    else:
        raise ValueError(f"unsupported element: {element}")
    return value, qflag


def build_dly_record(station_id: str, *, year: int, month: int, element: str, station_index: int) -> str:
    """Return one fixed-width NOAA `.dly` monthly record."""
    day_slots = [
        build_day_slot(value, qflag=qflag)
        for day in range(1, 32)
        for value, qflag in [synthesize_day_value(station_index, month, day, element)]
    ]
    return f"{station_id}{year:04d}{month:02d}{element}{''.join(day_slots)}\n"


def build_dataset(scale: ScaleConfig, workdir: Path) -> PreparedDataset:
    """Create deterministic fixed-width metadata and `.dly` input for one scale."""
    workdir.mkdir(parents=True, exist_ok=True)
    metadata_lines: list[str] = []
    startup_records: list[str] = []

    for index in range(scale.selected_station_count):
        station_id = f"USAZ{index + 1:07d}"
        metadata_lines.append(
            build_station_line(
                station_id,
                state=TARGET_STATE,
                name=f"AZ BENCH {index + 1}",
                lat=33.0 + (index * 0.11),
                lon=-112.0 + (index * 0.09),
                elev=250.0 + (index * 7.0),
            )
        )
        for month in range(1, 13):
            for element in ("TMAX", "TMIN", "PRCP"):
                startup_records.append(
                    build_dly_record(
                        station_id,
                        year=BENCHMARK_YEAR,
                        month=month,
                        element=element,
                        station_index=index,
                    )
                )

    noise_base = scale.selected_station_count
    for offset in range(scale.noise_station_count):
        station_index = noise_base + offset
        station_id = f"USCA{offset + 1:07d}"
        metadata_lines.append(
            build_station_line(
                station_id,
                state="CA",
                name=f"CA NOISE {offset + 1}",
                lat=36.0 + (offset * 0.07),
                lon=-119.0 + (offset * 0.05),
                elev=100.0 + (offset * 3.0),
            )
        )
        for month in range(1, 13):
            for element in ("TMAX", "TMIN", "PRCP"):
                startup_records.append(
                    build_dly_record(
                        station_id,
                        year=BENCHMARK_YEAR,
                        month=month,
                        element=element,
                        station_index=station_index,
                    )
                )

    metadata_path = workdir / "ghcnd-stations.txt"
    metadata_path.write_text("".join(metadata_lines), encoding="utf-8")

    startup_stdin_text = "".join(startup_records)
    steady_stdin_text = startup_stdin_text * scale.steady_repeat_factor
    return PreparedDataset(
        metadata_path=metadata_path,
        startup_stdin_text=startup_stdin_text,
        steady_stdin_text=steady_stdin_text,
        selected_station_count=scale.selected_station_count,
        noise_station_count=scale.noise_station_count,
        startup_monthly_record_count=len(startup_records),
        steady_monthly_record_count=len(startup_records) * scale.steady_repeat_factor,
    )


def require_executable(name: str, description: str) -> str:
    """Return an executable path or fail with a clear message."""
    path = shutil.which(name)
    if path is None:
        raise SystemExit(f"missing required tool: {name} ({description})")
    return path


def build_engine_commands(metadata_path: Path) -> dict[str, EngineCommand]:
    """Return the benchmark engine commands."""
    uv_path = require_executable("uv", "Python environment runner")
    gawk_path = require_executable("gawk", "GNU Awk with --posix support")
    direct_quawk_path = ROOT / ".venv" / "bin" / "quawk"
    if not direct_quawk_path.is_file():
        raise SystemExit(f"missing required tool: {direct_quawk_path} (direct quawk binary)")

    common_tail = (
        "-v",
        f"state={TARGET_STATE}",
        "-v",
        f"year={BENCHMARK_YEAR}",
        "-f",
        str(NOAA_PROGRAM),
        str(metadata_path),
        "-",
    )
    return {
        "gawk_posix": EngineCommand(
            name="gawk_posix",
            label="gawk --posix",
            argv=(gawk_path, "--posix", *common_tail),
        ),
        "quawk_uv": EngineCommand(
            name="quawk_uv",
            label="uv run quawk",
            argv=(uv_path, "run", "quawk", *common_tail),
        ),
        "quawk_direct": EngineCommand(
            name="quawk_direct",
            label=".venv/bin/quawk",
            argv=(str(direct_quawk_path), *common_tail),
        ),
    }


def run_engine(command: EngineCommand, *, stdin_text: str) -> tuple[float, str]:
    """Run one engine command and return elapsed time plus stdout."""
    start = time.perf_counter()
    completed = subprocess.run(
        list(command.argv),
        cwd=ROOT,
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        raise RuntimeError(f"{command.label} failed: {completed.stderr.strip() or completed.stdout.strip()}")
    return elapsed, completed.stdout


def benchmark_family(
    *,
    family_name: str,
    reference_engine: EngineCommand,
    comparison_engine: EngineCommand,
    stdin_text: str,
    repetitions: int,
    warmups: int,
) -> dict[str, object]:
    """Benchmark one `gawk` vs `quawk` timing family."""
    reference_output = ""
    reference_samples: list[float] = []
    comparison_samples: list[float] = []

    for _ in range(warmups):
        _, warmup_reference_output = run_engine(reference_engine, stdin_text=stdin_text)
        _, warmup_comparison_output = run_engine(comparison_engine, stdin_text=stdin_text)
        if warmup_reference_output != warmup_comparison_output:
            raise RuntimeError(
                f"{family_name} warmup output mismatch between {reference_engine.label} and {comparison_engine.label}"
            )

    for _ in range(repetitions):
        reference_time, reference_output = run_engine(reference_engine, stdin_text=stdin_text)
        comparison_time, comparison_output = run_engine(comparison_engine, stdin_text=stdin_text)
        if reference_output != comparison_output:
            raise RuntimeError(
                f"{family_name} output mismatch between {reference_engine.label} and {comparison_engine.label}"
            )
        reference_samples.append(reference_time)
        comparison_samples.append(comparison_time)

    reference_summary = summarize(reference_engine.name, reference_samples, repetitions, warmups)
    comparison_summary = summarize(comparison_engine.name, comparison_samples, repetitions, warmups)
    relative_to_gawk = comparison_summary.median_seconds / reference_summary.median_seconds
    return {
        reference_engine.name: asdict(reference_summary),
        comparison_engine.name: asdict(comparison_summary),
        "reference_output": reference_output,
        "median_quawk_relative_to_gawk": relative_to_gawk,
    }


def print_family_summary(
    family_name: str,
    payload: dict[str, object],
    *,
    reference_engine_name: str,
    comparison_engine_name: str,
) -> None:
    """Render one family summary block."""
    reference = payload[reference_engine_name]
    comparison = payload[comparison_engine_name]
    relative = payload["median_quawk_relative_to_gawk"]
    assert isinstance(reference, dict)
    assert isinstance(comparison, dict)
    assert isinstance(relative, float)

    print(f"{family_name}:")
    print("  mode          median       p95          min          max")
    print(
        f"  {reference_engine_name:<13}"
        f"{format_seconds(float(reference['median_seconds'])):<13}"
        f"{format_seconds(float(reference['p95_seconds'])):<13}"
        f"{format_seconds(float(reference['min_seconds'])):<13}"
        f"{format_seconds(float(reference['max_seconds']))}"
    )
    print(
        f"  {comparison_engine_name:<13}"
        f"{format_seconds(float(comparison['median_seconds'])):<13}"
        f"{format_seconds(float(comparison['p95_seconds'])):<13}"
        f"{format_seconds(float(comparison['min_seconds'])):<13}"
        f"{format_seconds(float(comparison['max_seconds']))}"
    )
    print(f"  median quawk relative to gawk: {relative:.2f}x")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the NOAA climate-report workload across startup-heavy and steady-state execution paths."
    )
    parser.add_argument("--dataset-scale", choices=sorted(SCALE_CONFIGS), default="large")
    parser.add_argument("--family", choices=BENCHMARK_FAMILY_CHOICES, default="both")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args()

    if args.repetitions <= 0:
        raise SystemExit("--repetitions must be positive")
    if args.warmups < 0:
        raise SystemExit("--warmups must be non-negative")

    scale = SCALE_CONFIGS[args.dataset_scale]
    if args.keep_workdir:
        workdir = Path(tempfile.mkdtemp(prefix="quawk-noaa-benchmark-"))
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="quawk-noaa-benchmark-")
        workdir = Path(temp_dir.name)

    try:
        dataset = build_dataset(scale, workdir)
        commands = build_engine_commands(dataset.metadata_path)
        startup_heavy = None
        steady_state = None
        if args.family in {"both", "startup_heavy"}:
            startup_heavy = benchmark_family(
                family_name="startup_heavy",
                reference_engine=commands["gawk_posix"],
                comparison_engine=commands["quawk_uv"],
                stdin_text=dataset.startup_stdin_text,
                repetitions=args.repetitions,
                warmups=args.warmups,
            )
        if args.family in {"both", "steady_state"}:
            steady_state = benchmark_family(
                family_name="steady_state",
                reference_engine=commands["gawk_posix"],
                comparison_engine=commands["quawk_direct"],
                stdin_text=dataset.steady_stdin_text,
                repetitions=args.repetitions,
                warmups=args.warmups,
            )
    finally:
        if not args.keep_workdir:
            temp_dir.cleanup()

    payload = {
        "dataset_scale": scale.name,
        "family": args.family,
        "repetitions": args.repetitions,
        "warmups": args.warmups,
        "dataset": {
            "target_state": TARGET_STATE,
            "benchmark_year": BENCHMARK_YEAR,
            "selected_station_count": dataset.selected_station_count,
            "noise_station_count": dataset.noise_station_count,
            "startup_monthly_record_count": dataset.startup_monthly_record_count,
            "steady_monthly_record_count": dataset.steady_monthly_record_count,
            "startup_input_bytes": len(dataset.startup_stdin_text.encode("utf-8")),
            "steady_input_bytes": len(dataset.steady_stdin_text.encode("utf-8")),
            "steady_repeat_factor": scale.steady_repeat_factor,
        },
    }
    if startup_heavy is not None:
        payload["startup_heavy"] = startup_heavy
    if steady_state is not None:
        payload["steady_state"] = steady_state

    print("noaa-runtime-gap benchmark")
    print(
        f"dataset_scale={scale.name} family={args.family}"
        f" repetitions={args.repetitions} warmups={args.warmups}"
    )
    print(
        "dataset:"
        f" selected_stations={dataset.selected_station_count}"
        f" noise_stations={dataset.noise_station_count}"
        f" startup_records={dataset.startup_monthly_record_count}"
        f" steady_records={dataset.steady_monthly_record_count}"
    )
    if args.keep_workdir:
        print(f"workdir={workdir}")
    if startup_heavy is not None:
        print("")
        print_family_summary(
            "startup_heavy",
            startup_heavy,
            reference_engine_name="gawk_posix",
            comparison_engine_name="quawk_uv",
        )
    if steady_state is not None:
        print("")
        print_family_summary(
            "steady_state",
            steady_state,
            reference_engine_name="gawk_posix",
            comparison_engine_name="quawk_direct",
        )

    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
