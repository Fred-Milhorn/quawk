"""Microbenchmark slot-based vs hash-based numeric variable access.

This benchmark compiles a tiny C harness against `qk_runtime.c` and measures
wall-clock time for repeated numeric read/write loops using:

- slot path: `qk_slot_get_number` / `qk_slot_set_number`
- hash path: `qk_scalar_get_number` / `qk_scalar_set_number`
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from quawk import runtime_support

HARNESS_SOURCE = r"""
#include "qk_runtime.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    const char *mode;
    int64_t iterations;
    qk_runtime *runtime;
    int64_t index;
    volatile double sink = 0.0;

    if (argc != 3) {
        fprintf(stderr, "usage: %s <slot|hash> <iterations>\n", argv[0]);
        return 2;
    }
    mode = argv[1];
    iterations = strtoll(argv[2], (char **)0, 10);
    if (iterations < 0) {
        fprintf(stderr, "iterations must be non-negative\n");
        return 2;
    }

    runtime = qk_runtime_create(0, (char **)0, (const char *)0);
    if (runtime == NULL) {
        fprintf(stderr, "failed to create runtime\n");
        return 3;
    }

    if (strcmp(mode, "slot") == 0) {
        for (index = 0; index < iterations; index += 1) {
            qk_slot_set_number(runtime, 0, (double)index);
            sink += qk_slot_get_number(runtime, 0);
        }
    } else if (strcmp(mode, "hash") == 0) {
        for (index = 0; index < iterations; index += 1) {
            qk_scalar_set_number(runtime, "x", (double)index);
            sink += qk_scalar_get_number(runtime, "x");
        }
    } else {
        fprintf(stderr, "unknown mode: %s\n", mode);
        qk_runtime_destroy(runtime);
        return 2;
    }

    qk_runtime_destroy(runtime);
    printf("%.17g\n", sink);
    return 0;
}
"""


@dataclass(frozen=True)
class TimingSummary:
    mode: str
    iterations: int
    repetitions: int
    warmups: int
    median_seconds: float
    p95_seconds: float
    min_seconds: float
    max_seconds: float


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


def summarize(mode: str, values: list[float], iterations: int, repetitions: int, warmups: int) -> TimingSummary:
    """Build one summary row for measured timings."""
    ordered = sorted(values)
    return TimingSummary(
        mode=mode,
        iterations=iterations,
        repetitions=repetitions,
        warmups=warmups,
        median_seconds=statistics.median(ordered),
        p95_seconds=percentile(ordered, 0.95),
        min_seconds=ordered[0],
        max_seconds=ordered[-1],
    )


def compile_harness(workdir: Path) -> Path:
    """Compile and return the benchmark harness executable path."""
    harness_path = workdir / "slot_hash_benchmark.c"
    executable_path = workdir / "slot_hash_benchmark"
    harness_path.write_text(HARNESS_SOURCE, encoding="utf-8")
    subprocess.run(
        [
            runtime_support.find_clang(),
            "-std=c11",
            "-O3",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(runtime_support.runtime_source_path()),
            str(harness_path),
            "-I",
            str(runtime_support.runtime_directory()),
            "-o",
            str(executable_path),
            "-lm",
        ],
        check=True,
    )
    return executable_path


def run_one(executable: Path, mode: str, iterations: int) -> tuple[float, float]:
    """Run one benchmark sample and return (elapsed_seconds, sink)."""
    start = time.perf_counter()
    completed = subprocess.run(
        [str(executable), mode, str(iterations)],
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed = time.perf_counter() - start
    sink = float(completed.stdout.strip())
    return elapsed, sink


def format_seconds(seconds: float) -> str:
    """Render one timing value in milliseconds with fixed precision."""
    return f"{seconds * 1000.0:.3f} ms"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark slot vs hash numeric variable access in qk_runtime.")
    parser.add_argument("--iterations", type=int, default=5_000_000)
    parser.add_argument("--repetitions", type=int, default=9)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if args.iterations <= 0:
        raise SystemExit("--iterations must be positive")
    if args.repetitions <= 0:
        raise SystemExit("--repetitions must be positive")
    if args.warmups < 0:
        raise SystemExit("--warmups must be non-negative")

    with TemporaryDirectory(prefix="quawk-slot-hash-bench-") as temp_dir:
        workdir = Path(temp_dir)
        executable = compile_harness(workdir)

        for mode in ("slot", "hash"):
            for _ in range(args.warmups):
                run_one(executable, mode, args.iterations)

        slot_samples: list[float] = []
        hash_samples: list[float] = []
        for _ in range(args.repetitions):
            slot_time, slot_sink = run_one(executable, "slot", args.iterations)
            hash_time, hash_sink = run_one(executable, "hash", args.iterations)
            slot_samples.append(slot_time)
            hash_samples.append(hash_time)
            # Keep the loop bodies observable and comparable.
            if abs(slot_sink - hash_sink) > 1e-6:
                raise RuntimeError("slot/hash sinks diverged; benchmark harness is not comparable")

    slot_summary = summarize("slot", slot_samples, args.iterations, args.repetitions, args.warmups)
    hash_summary = summarize("hash", hash_samples, args.iterations, args.repetitions, args.warmups)
    speedup = hash_summary.median_seconds / slot_summary.median_seconds

    print("slot-vs-hash microbenchmark")
    print(f"iterations={args.iterations} repetitions={args.repetitions} warmups={args.warmups}")
    print("")
    print("mode   median       p95          min          max")
    print(
        f"slot   {format_seconds(slot_summary.median_seconds):<12}"
        f"{format_seconds(slot_summary.p95_seconds):<13}"
        f"{format_seconds(slot_summary.min_seconds):<13}"
        f"{format_seconds(slot_summary.max_seconds)}"
    )
    print(
        f"hash   {format_seconds(hash_summary.median_seconds):<12}"
        f"{format_seconds(hash_summary.p95_seconds):<13}"
        f"{format_seconds(hash_summary.min_seconds):<13}"
        f"{format_seconds(hash_summary.max_seconds)}"
    )
    print("")
    print(f"median speedup (slot vs hash): {speedup:.2f}x")

    if args.json is not None:
        payload = {
            "slot": asdict(slot_summary),
            "hash": asdict(hash_summary),
            "median_speedup_slot_vs_hash": speedup,
        }
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
