"""Profile runtime hot paths across representative AWK workloads.

The runtime emits call-count summaries when `QUAWK_RUNTIME_PROFILE=1` is set.
This script runs a small workload set under that mode, aggregates the counts,
and prints the top called runtime functions for the current P29 profiling pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent

FIELD_AGGREGATE_PROGRAM = (
    "{ a = $1 + 0; b = $2 + 0; c = $3 + 0; derived = (b * 3) + c; "
    "if (a < 700) { total += derived; count += 1 } } "
    "END { print total + count }"
)

FILTER_TRANSFORM_PROGRAM = (
    "{ a = $1 + 0; b = $2 + 0; c = $3 + 0; value = (a * 5) + (b * 2) - c; "
    "if (a < 500) { if (value > 50) { total += value } } } "
    "END { print total }"
)

MULTI_FILE_REDUCTION_PROGRAM = (
    "FNR == 1 { file_count += 1 } "
    "{ a = $1 + 0; b = $2 + 0; c = $3 + 0; total += (a * 2) + (b * 3) - c + NR - FNR } "
    "END { print total + file_count + NR }"
)

PROFILE_LINE_RE = re.compile(r"^quawk-runtime-profile\s+(\d+)\s+([A-Za-z0-9_]+)\s+(\d+)$")


@dataclass(frozen=True)
class ScaleConfig:
    name: str
    record_count: int
    file_count: int


@dataclass(frozen=True)
class Workload:
    name: str
    description: str
    program_text: str
    stdin_text: str | None
    input_files: tuple[str, ...]


SCALE_CONFIGS = {
    "smoke": ScaleConfig(name="smoke", record_count=120, file_count=2),
    "medium": ScaleConfig(name="medium", record_count=8_000, file_count=3),
    "large": ScaleConfig(name="large", record_count=60_000, file_count=4),
}


def generate_record(index: int) -> str:
    """Return one deterministic numeric record for AWK field workloads."""
    first = (index * 17 + 11) % 997
    second = (index * 13 + 7) % 503
    third = (index * 19 + 5) % 307
    return f"{first} {second} {third}\n"


def generate_record_stream(record_count: int, *, start_index: int = 0) -> str:
    """Return deterministic whitespace-delimited records."""
    return "".join(generate_record(start_index + offset) for offset in range(record_count))


def write_multi_file_dataset(workdir: Path, *, record_count: int, file_count: int) -> tuple[str, ...]:
    """Create deterministic input files and return their absolute paths."""
    records_per_file = max(1, record_count // file_count)
    paths: list[str] = []
    next_index = 0
    for file_index in range(file_count):
        path = workdir / f"input_{file_index + 1}.txt"
        path.write_text(generate_record_stream(records_per_file, start_index=next_index), encoding="utf-8")
        next_index += records_per_file
        paths.append(str(path))
    return tuple(paths)


def prepare_workloads(scale: ScaleConfig, workdir: Path) -> list[Workload]:
    """Return the runtime-heavy workloads for the selected dataset scale."""
    record_stream = generate_record_stream(scale.record_count)
    multi_file_inputs = write_multi_file_dataset(workdir, record_count=scale.record_count, file_count=scale.file_count)
    return [
        Workload(
            name="field_aggregate",
            description="Record traversal with numeric field extraction and accumulation.",
            program_text=FIELD_AGGREGATE_PROGRAM,
            stdin_text=record_stream,
            input_files=(),
        ),
        Workload(
            name="filter_transform",
            description="Predicate-heavy record filtering with derived numeric output.",
            program_text=FILTER_TRANSFORM_PROGRAM,
            stdin_text=record_stream,
            input_files=(),
        ),
        Workload(
            name="multi_file_reduce",
            description="Multi-file traversal that exercises NR/FNR bookkeeping.",
            program_text=MULTI_FILE_REDUCTION_PROGRAM,
            stdin_text=None,
            input_files=multi_file_inputs,
        ),
    ]


def select_workloads(all_workloads: list[Workload], requested_names: list[str]) -> list[Workload]:
    """Return either the full workload list or the requested subset."""
    if not requested_names:
        return all_workloads
    indexed = {workload.name: workload for workload in all_workloads}
    unknown = [name for name in requested_names if name not in indexed]
    if unknown:
        raise SystemExit(
            "unknown workload name(s): "
            + ", ".join(sorted(unknown))
            + "; available workloads: "
            + ", ".join(sorted(indexed))
        )
    return [indexed[name] for name in requested_names]


def parse_profile_lines(stderr_text: str) -> Counter[str]:
    """Parse runtime profile lines from stderr."""
    counts: Counter[str] = Counter()
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "quawk-runtime-profile top=10":
            continue
        match = PROFILE_LINE_RE.fullmatch(line)
        if match is None:
            raise RuntimeError(f"unexpected stderr from profiled run: {line}")
        counts[match.group(2)] += int(match.group(3))
    return counts


def top_functions(counts: Counter[str], top_n: int) -> list[dict[str, object]]:
    """Return the top `top_n` functions by call count."""
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"rank": rank, "name": name, "count": count}
        for rank, (name, count) in enumerate(ranked[:top_n], start=1)
    ]


def format_count(value: int) -> str:
    return f"{value:,}"


def run_profiled_workload(workload: Workload, *, warmups: int, repetitions: int) -> tuple[str, Counter[str]]:
    """Run one workload with runtime profiling enabled and aggregate the counts."""
    command = [sys.executable, "-m", "quawk", workload.program_text, *workload.input_files]
    env = os.environ.copy()
    env["QUAWK_RUNTIME_PROFILE"] = "1"

    reference_output = ""
    aggregated_counts: Counter[str] = Counter()

    for _ in range(warmups):
        completed = subprocess.run(
            command,
            cwd=ROOT,
            input=workload.stdin_text,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "profiled workload failed during warmup")
        if reference_output and completed.stdout != reference_output:
            raise RuntimeError("warmup output mismatch; profiled runs are not comparable")
        reference_output = completed.stdout

    for _ in range(repetitions):
        completed = subprocess.run(
            command,
            cwd=ROOT,
            input=workload.stdin_text,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "profiled workload failed")
        if reference_output and completed.stdout != reference_output:
            raise RuntimeError("benchmark output mismatch; profiled runs are not comparable")
        reference_output = completed.stdout
        aggregated_counts.update(parse_profile_lines(completed.stderr))

    return reference_output, aggregated_counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile current runtime hot paths across representative AWK workloads.")
    parser.add_argument("--dataset-scale", choices=sorted(SCALE_CONFIGS), default="medium")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--workload", action="append", default=[], help="Profile only the named workload. Repeatable.")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if args.repetitions <= 0:
        raise SystemExit("--repetitions must be positive")
    if args.warmups < 0:
        raise SystemExit("--warmups must be non-negative")
    if args.top <= 0:
        raise SystemExit("--top must be positive")

    scale = SCALE_CONFIGS[args.dataset_scale]

    with TemporaryDirectory(prefix="quawk-runtime-profile-") as temp_dir_name:
        workdir = Path(temp_dir_name)
        workloads = select_workloads(prepare_workloads(scale, workdir), args.workload)
        aggregate_counts: Counter[str] = Counter()
        workload_results: list[dict[str, object]] = []

        for workload in workloads:
            reference_output, workload_counts = run_profiled_workload(
                workload,
                warmups=args.warmups,
                repetitions=args.repetitions,
            )
            aggregate_counts.update(workload_counts)
            workload_results.append(
                {
                    "name": workload.name,
                    "description": workload.description,
                    "output": reference_output.strip(),
                    "top_functions": top_functions(workload_counts, args.top),
                }
            )

    aggregate_top = top_functions(aggregate_counts, args.top)
    payload = {
        "dataset_scale": scale.name,
        "repetitions": args.repetitions,
        "warmups": args.warmups,
        "top": args.top,
        "workloads": workload_results,
        "top_functions": aggregate_top,
        "call_counts": dict(sorted(aggregate_counts.items(), key=lambda item: (-item[1], item[0]))),
    }

    print("runtime-hot-path profile")
    print(f"dataset_scale={scale.name} repetitions={args.repetitions} warmups={args.warmups}")
    print("")
    for workload in workload_results:
        print(f"workload: {workload['name']}")
        print(f"  {workload['description']}")
        for entry in workload["top_functions"]:
            print(f"  {entry['rank']}. {entry['name']}: {format_count(int(entry['count']))}")
        print("")
    print(f"aggregate top {args.top}:")
    for entry in aggregate_top:
        print(f"  {entry['rank']}. {entry['name']}: {format_count(int(entry['count']))}")

    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
