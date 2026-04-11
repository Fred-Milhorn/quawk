"""Microbenchmark optimized IR execution vs unoptimized IR execution.

This benchmark compares the same AWK program lowered twice:

- unoptimized: plain generated IR executed by `lli`
- optimized: IR passed through LLVM `opt` before `lli`

The benchmark isolates the effect of optimization passes on `lli` runtime by
building both modules once up front and timing only module execution.
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

from quawk import jit, runtime_support
from quawk.lexer import lex
from quawk.parser import parse
from quawk.source import ProgramSource

PROGRAM_TEMPLATE = (
    "{ n = ITER; x = 0; s = 0; "
    "for (i = 0; i < n; i++) { "
    "a = i + 1; b = a + 2; c = b + 3; d = c + 4; e = d + 5; f = e + 6; g = f + 7; h = g + 8; "
    "s += i "
    "} "
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


def compile_modules(program_text: str, workdir: Path) -> tuple[Path, Path]:
    """Build optimized and unoptimized IR modules once and return their paths."""
    program = parse(lex(ProgramSource.from_inline(program_text)))
    unoptimized_ir = jit.build_public_execution_llvm_ir(program, [], None, None, optimize=False)
    optimized_ir = jit.optimize_ir(unoptimized_ir, level=2)

    unoptimized_path = workdir / "unoptimized.ll"
    optimized_path = workdir / "optimized.ll"
    unoptimized_path.write_text(unoptimized_ir, encoding="utf-8")
    optimized_path.write_text(optimized_ir, encoding="utf-8")
    return unoptimized_path, optimized_path


def run_lli_module(lli_path: str, module_path: Path) -> tuple[float, str]:
    """Run one LLVM module with `lli` and return elapsed time plus stdout."""
    start = time.perf_counter()
    completed = subprocess.run(
        [lli_path, "--entry-function=quawk_main", str(module_path)],
        input="record\n",
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "lli failed to execute benchmark module")
    return elapsed, completed.stdout


def format_seconds(seconds: float) -> str:
    """Render one timing value in milliseconds with fixed precision."""
    return f"{seconds * 1000.0:.3f} ms"


def build_program_text(iterations: int) -> str:
    """Return the benchmark program with the selected iteration count."""
    return PROGRAM_TEMPLATE.replace("ITER", str(iterations))


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark optimized vs unoptimized LLVM IR execution in quawk.")
    parser.add_argument("--iterations", type=int, default=250_000)
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

    lli_path = runtime_support.find_tool("lli", "LLVM JIT tool")
    program_text = build_program_text(args.iterations)

    with TemporaryDirectory(prefix="quawk-optimized-bench-") as temp_dir_name:
        workdir = Path(temp_dir_name)
        unoptimized_path, optimized_path = compile_modules(program_text, workdir)
        reference_output = ""

        for _ in range(args.warmups):
            _, unoptimized_output = run_lli_module(lli_path, unoptimized_path)
            _, optimized_output = run_lli_module(lli_path, optimized_path)
            if unoptimized_output != optimized_output:
                raise RuntimeError("warmup output mismatch; optimized and unoptimized modules are not comparable")

        unoptimized_samples: list[float] = []
        optimized_samples: list[float] = []
        for _ in range(args.repetitions):
            unoptimized_time, unoptimized_output = run_lli_module(lli_path, unoptimized_path)
            optimized_time, optimized_output = run_lli_module(lli_path, optimized_path)
            if unoptimized_output != optimized_output:
                raise RuntimeError("benchmark output mismatch; optimized and unoptimized modules are not comparable")
            unoptimized_samples.append(unoptimized_time)
            optimized_samples.append(optimized_time)
            reference_output = unoptimized_output

    unoptimized_summary = summarize("unoptimized", unoptimized_samples, args.iterations, args.repetitions, args.warmups)
    optimized_summary = summarize("optimized", optimized_samples, args.iterations, args.repetitions, args.warmups)
    speedup = unoptimized_summary.median_seconds / optimized_summary.median_seconds

    print("optimized-vs-unoptimized microbenchmark")
    print(f"iterations={args.iterations} repetitions={args.repetitions} warmups={args.warmups}")
    print("")
    print("mode          median       p95          min          max")
    print(
        f"unoptimized   {format_seconds(unoptimized_summary.median_seconds):<12}"
        f"{format_seconds(unoptimized_summary.p95_seconds):<13}"
        f"{format_seconds(unoptimized_summary.min_seconds):<13}"
        f"{format_seconds(unoptimized_summary.max_seconds)}"
    )
    print(
        f"optimized     {format_seconds(optimized_summary.median_seconds):<12}"
        f"{format_seconds(optimized_summary.p95_seconds):<13}"
        f"{format_seconds(optimized_summary.min_seconds):<13}"
        f"{format_seconds(optimized_summary.max_seconds)}"
    )
    print("")
    print(f"median speedup (optimized vs unoptimized): {speedup:.2f}x")

    if args.json is not None:
        payload = {
            "unoptimized": asdict(unoptimized_summary),
            "optimized": asdict(optimized_summary),
            "reference_output": reference_output,
            "median_speedup_optimized_vs_unoptimized": speedup,
        }
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
