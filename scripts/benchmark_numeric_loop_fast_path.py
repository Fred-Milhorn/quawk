"""Microbenchmark numeric loop fast path vs mixed-type fallback.

This benchmark compares two runtime-backed AWK programs:

- fast path: loop variables remain inferred numeric and use specialized lowering
- fallback: one loop-carried value is intentionally mixed-typed to trigger slow paths
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


FAST_PROGRAM_TEMPLATE = (
    "{ n = ITER; x = 0; s = 0; "
    "for (i = 0; i < n; i++) { x += 1; if (x < n) s += x } "
    "; print s }"
)

FALLBACK_PROGRAM_TEMPLATE = (
    '{ n = ITER; x = 0; x = "0"; s = 0; '
    "for (i = 0; i < n; i++) { x += 1; if (x < n) s += x } "
    "; print s }"
)


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


def run_one(program: str, *, cwd: Path) -> tuple[float, float]:
    """Run one benchmark sample and return (elapsed_seconds, numeric_output)."""
    start = time.perf_counter()
    completed = subprocess.run(
        ["quawk", program],
        cwd=cwd,
        input="record\n",
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed = time.perf_counter() - start
    output = completed.stdout.strip()
    return elapsed, float(output)


def format_seconds(seconds: float) -> str:
    """Render one timing value in milliseconds with fixed precision."""
    return f"{seconds * 1000.0:.3f} ms"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark numeric-loop fast path vs mixed-type fallback.")
    parser.add_argument("--iterations", type=int, default=80_000)
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

    root = Path(__file__).resolve().parent.parent
    fast_program = FAST_PROGRAM_TEMPLATE.replace("ITER", str(args.iterations))
    fallback_program = FALLBACK_PROGRAM_TEMPLATE.replace("ITER", str(args.iterations))
    for _ in range(args.warmups):
        _, fast_value = run_one(fast_program, cwd=root)
        _, fallback_value = run_one(fallback_program, cwd=root)
        if abs(fast_value - fallback_value) > 1e-6:
            raise RuntimeError("warmup output mismatch; benchmark programs are not comparable")

    fast_samples: list[float] = []
    fallback_samples: list[float] = []
    for _ in range(args.repetitions):
        fast_time, fast_value = run_one(fast_program, cwd=root)
        fallback_time, fallback_value = run_one(fallback_program, cwd=root)
        if abs(fast_value - fallback_value) > 1e-6:
            raise RuntimeError("benchmark output mismatch; programs are not comparable")
        fast_samples.append(fast_time)
        fallback_samples.append(fallback_time)

    fast_summary = summarize("fast", fast_samples, args.iterations, args.repetitions, args.warmups)
    fallback_summary = summarize("fallback", fallback_samples, args.iterations, args.repetitions, args.warmups)
    speedup = fallback_summary.median_seconds / fast_summary.median_seconds

    print("numeric-loop fast-path microbenchmark")
    print(f"iterations={args.iterations} repetitions={args.repetitions} warmups={args.warmups}")
    print("")
    print("mode      median       p95          min          max")
    print(
        f"fast      {format_seconds(fast_summary.median_seconds):<12}"
        f"{format_seconds(fast_summary.p95_seconds):<13}"
        f"{format_seconds(fast_summary.min_seconds):<13}"
        f"{format_seconds(fast_summary.max_seconds)}"
    )
    print(
        f"fallback  {format_seconds(fallback_summary.median_seconds):<12}"
        f"{format_seconds(fallback_summary.p95_seconds):<13}"
        f"{format_seconds(fallback_summary.min_seconds):<13}"
        f"{format_seconds(fallback_summary.max_seconds)}"
    )
    print("")
    print(f"median speedup (fast vs fallback): {speedup:.2f}x")

    if args.json is not None:
        payload = {
            "fast": asdict(fast_summary),
            "fallback": asdict(fallback_summary),
            "reference_output": fast_value,
            "median_speedup_fast_vs_fallback": speedup,
        }
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
