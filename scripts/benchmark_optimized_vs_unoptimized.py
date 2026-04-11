"""Benchmark optimized vs unoptimized execution across a small workload suite.

This benchmark compares the same AWK workloads in two modes:

- unoptimized: plain generated IR executed as-is
- optimized: IR passed through LLVM `opt` before execution

The suite intentionally mixes two workload categories:

- optimizer kernels: scalar-heavy loops with redundant temporaries and branches
- runtime workloads: record-processing programs that exercise fields and
  multi-file bookkeeping

For each workload the benchmark reports:

- end-to-end execution through `python -m quawk`
- `lli`-only execution of prebuilt optimized and unoptimized modules
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from quawk import jit, runtime_support
from quawk.lexer import lex
from quawk.parser import parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent

SCALAR_FOLD_TEMPLATE = (
    "{ n = ITER; s = 0; bias = 17; scale = 3; "
    "for (i = 0; i < n; i++) { "
    "base = bias * scale; x = base + i; y = x + 4; z = y - 4; dead = z * 2; "
    "s += z "
    "} "
    "; print s }"
)

BRANCH_REWRITE_TEMPLATE = (
    "{ n = ITER; total = 0; limit = 100; "
    "for (i = 0; i < n; i++) { "
    "left = i * 2; right = left + 10; "
    "if (right > limit) { total += right - limit } else { total += limit - right }; "
    "always = (i - i) + 1; total += always "
    "} "
    "; print total }"
)

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


@dataclass(frozen=True)
class ScaleConfig:
    name: str
    kernel_iterations: int
    record_count: int
    file_count: int


@dataclass(frozen=True)
class TimingSummary:
    mode: str
    repetitions: int
    warmups: int
    median_seconds: float
    p95_seconds: float
    min_seconds: float
    max_seconds: float


@dataclass(frozen=True)
class PreparedWorkload:
    name: str
    category: str
    description: str
    program_text: str
    stdin_text: str | None
    input_files: tuple[str, ...]
    kernel_iterations: int
    record_count: int


SCALE_CONFIGS = {
    "smoke": ScaleConfig(name="smoke", kernel_iterations=1_000, record_count=120, file_count=2),
    "medium": ScaleConfig(name="medium", kernel_iterations=40_000, record_count=8_000, file_count=3),
    "large": ScaleConfig(name="large", kernel_iterations=200_000, record_count=60_000, file_count=4),
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


def geometric_mean(values: list[float]) -> float:
    """Return the geometric mean for positive floating-point values."""
    if not values:
        raise ValueError("geometric_mean requires at least one value")
    if any(value <= 0.0 for value in values):
        raise ValueError("geometric_mean requires all values to be positive")
    return math.exp(sum(math.log(value) for value in values) / len(values))


def format_seconds(seconds: float) -> str:
    """Render one timing value in milliseconds with fixed precision."""
    return f"{seconds * 1000.0:.3f} ms"


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


def prepare_workloads(scale: ScaleConfig, workdir: Path) -> list[PreparedWorkload]:
    """Return the benchmark workloads for the selected dataset scale."""
    record_stream = generate_record_stream(scale.record_count)
    multi_file_inputs = write_multi_file_dataset(workdir, record_count=scale.record_count, file_count=scale.file_count)
    return [
        PreparedWorkload(
            name="scalar_fold_loop",
            category="optimizer_kernel",
            description="Scalar loop with invariant arithmetic and dead temporaries.",
            program_text=SCALAR_FOLD_TEMPLATE.replace("ITER", str(scale.kernel_iterations)),
            stdin_text="record\n",
            input_files=(),
            kernel_iterations=scale.kernel_iterations,
            record_count=1,
        ),
        PreparedWorkload(
            name="branch_rewrite_loop",
            category="optimizer_kernel",
            description="Scalar loop with redundant branch arithmetic and trivially reducible values.",
            program_text=BRANCH_REWRITE_TEMPLATE.replace("ITER", str(scale.kernel_iterations)),
            stdin_text="record\n",
            input_files=(),
            kernel_iterations=scale.kernel_iterations,
            record_count=1,
        ),
        PreparedWorkload(
            name="field_aggregate",
            category="runtime_workload",
            description="Record traversal with numeric field extraction and accumulation.",
            program_text=FIELD_AGGREGATE_PROGRAM,
            stdin_text=record_stream,
            input_files=(),
            kernel_iterations=0,
            record_count=scale.record_count,
        ),
        PreparedWorkload(
            name="filter_transform",
            category="runtime_workload",
            description="Predicate-heavy record filtering with derived numeric output.",
            program_text=FILTER_TRANSFORM_PROGRAM,
            stdin_text=record_stream,
            input_files=(),
            kernel_iterations=0,
            record_count=scale.record_count,
        ),
        PreparedWorkload(
            name="multi_file_reduce",
            category="runtime_workload",
            description="Multi-file traversal that exercises NR/FNR bookkeeping.",
            program_text=MULTI_FILE_REDUCTION_PROGRAM,
            stdin_text=None,
            input_files=multi_file_inputs,
            kernel_iterations=0,
            record_count=scale.record_count,
        ),
    ]


def select_workloads(all_workloads: list[PreparedWorkload], requested_names: list[str]) -> list[PreparedWorkload]:
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


def compile_modules(workload: PreparedWorkload, workdir: Path) -> tuple[Path, Path]:
    """Build optimized and unoptimized IR modules once and return their paths."""
    program = parse(lex(ProgramSource.from_inline(workload.program_text)))
    unoptimized_ir = jit.build_public_execution_llvm_ir(program, list(workload.input_files), None, None, optimize=False)
    optimized_ir = jit.optimize_ir(unoptimized_ir, level=2)

    safe_name = workload.name.replace("-", "_")
    unoptimized_path = workdir / f"{safe_name}_unoptimized.ll"
    optimized_path = workdir / f"{safe_name}_optimized.ll"
    unoptimized_path.write_text(unoptimized_ir, encoding="utf-8")
    optimized_path.write_text(optimized_ir, encoding="utf-8")
    return unoptimized_path, optimized_path


def run_lli_module(lli_path: str, module_path: Path, *, stdin_text: str | None) -> tuple[float, str]:
    """Run one LLVM module with `lli` and return elapsed time plus stdout."""
    start = time.perf_counter()
    completed = subprocess.run(
        [lli_path, "--entry-function=quawk_main", str(module_path)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "lli failed to execute benchmark module")
    return elapsed, completed.stdout


def run_end_to_end(
    workload: PreparedWorkload,
    *,
    optimize: bool,
) -> tuple[float, str]:
    """Run one benchmark sample through the full CLI execution path."""
    command = [sys.executable, "-m", "quawk"]
    if optimize:
        command.append("-O")
    command.append(workload.program_text)
    command.extend(workload.input_files)

    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        input=workload.stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - start
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "quawk failed to execute benchmark workload")
    return elapsed, completed.stdout


def benchmark_pair(
    run_unoptimized,
    run_optimized,
    *,
    repetitions: int,
    warmups: int,
) -> dict[str, object]:
    """Run warmups and measured samples for one unoptimized/optimized pair."""
    reference_output = ""
    for _ in range(warmups):
        _, unoptimized_output = run_unoptimized()
        _, optimized_output = run_optimized()
        if unoptimized_output != optimized_output:
            raise RuntimeError("warmup output mismatch; optimized and unoptimized runs are not comparable")

    unoptimized_samples: list[float] = []
    optimized_samples: list[float] = []
    for _ in range(repetitions):
        unoptimized_time, unoptimized_output = run_unoptimized()
        optimized_time, optimized_output = run_optimized()
        if unoptimized_output != optimized_output:
            raise RuntimeError("benchmark output mismatch; optimized and unoptimized runs are not comparable")
        unoptimized_samples.append(unoptimized_time)
        optimized_samples.append(optimized_time)
        reference_output = unoptimized_output

    unoptimized_summary = summarize("unoptimized", unoptimized_samples, repetitions, warmups)
    optimized_summary = summarize("optimized", optimized_samples, repetitions, warmups)
    speedup = unoptimized_summary.median_seconds / optimized_summary.median_seconds
    return {
        "unoptimized": asdict(unoptimized_summary),
        "optimized": asdict(optimized_summary),
        "reference_output": reference_output,
        "median_speedup_optimized_vs_unoptimized": speedup,
    }


def print_family_summary(name: str, family_payload: dict[str, object]) -> None:
    """Render one timing family summary block."""
    unoptimized = family_payload["unoptimized"]
    optimized = family_payload["optimized"]
    speedup = family_payload["median_speedup_optimized_vs_unoptimized"]
    assert isinstance(unoptimized, dict)
    assert isinstance(optimized, dict)
    assert isinstance(speedup, float)

    print(f"  {name}")
    print("    mode          median       p95          min          max")
    print(
        f"    unoptimized   {format_seconds(float(unoptimized['median_seconds'])):<12}"
        f"{format_seconds(float(unoptimized['p95_seconds'])):<13}"
        f"{format_seconds(float(unoptimized['min_seconds'])):<13}"
        f"{format_seconds(float(unoptimized['max_seconds']))}"
    )
    print(
        f"    optimized     {format_seconds(float(optimized['median_seconds'])):<12}"
        f"{format_seconds(float(optimized['p95_seconds'])):<13}"
        f"{format_seconds(float(optimized['min_seconds'])):<13}"
        f"{format_seconds(float(optimized['max_seconds']))}"
    )
    print(f"    median speedup (optimized vs unoptimized): {speedup:.2f}x")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark optimized vs unoptimized execution across a quawk workload suite.")
    parser.add_argument("--dataset-scale", choices=sorted(SCALE_CONFIGS), default="medium")
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--workload", action="append", default=[], help="Run only the named workload. Repeatable.")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if args.repetitions <= 0:
        raise SystemExit("--repetitions must be positive")
    if args.warmups < 0:
        raise SystemExit("--warmups must be non-negative")

    scale = SCALE_CONFIGS[args.dataset_scale]
    lli_path = runtime_support.find_tool("lli", "LLVM JIT tool")

    with TemporaryDirectory(prefix="quawk-optimized-bench-") as temp_dir_name:
        workdir = Path(temp_dir_name)
        workloads = select_workloads(prepare_workloads(scale, workdir), args.workload)
        results: list[dict[str, object]] = []
        end_to_end_speedups: list[float] = []
        lli_only_speedups: list[float] = []

        for workload in workloads:
            unoptimized_path, optimized_path = compile_modules(workload, workdir)
            lli_only = benchmark_pair(
                lambda: run_lli_module(lli_path, unoptimized_path, stdin_text=workload.stdin_text),
                lambda: run_lli_module(lli_path, optimized_path, stdin_text=workload.stdin_text),
                repetitions=args.repetitions,
                warmups=args.warmups,
            )
            end_to_end = benchmark_pair(
                lambda: run_end_to_end(workload, optimize=False),
                lambda: run_end_to_end(workload, optimize=True),
                repetitions=args.repetitions,
                warmups=args.warmups,
            )

            lli_speedup = lli_only["median_speedup_optimized_vs_unoptimized"]
            end_speedup = end_to_end["median_speedup_optimized_vs_unoptimized"]
            assert isinstance(lli_speedup, float)
            assert isinstance(end_speedup, float)
            lli_only_speedups.append(lli_speedup)
            end_to_end_speedups.append(end_speedup)
            results.append(
                {
                    "name": workload.name,
                    "category": workload.category,
                    "description": workload.description,
                    "kernel_iterations": workload.kernel_iterations,
                    "record_count": workload.record_count,
                    "input_file_count": len(workload.input_files),
                    "end_to_end": end_to_end,
                    "lli_only": lli_only,
                }
            )

    payload = {
        "dataset_scale": scale.name,
        "repetitions": args.repetitions,
        "warmups": args.warmups,
        "workloads": results,
        "geometric_mean_speedup_end_to_end": geometric_mean(end_to_end_speedups),
        "geometric_mean_speedup_lli_only": geometric_mean(lli_only_speedups),
    }

    print("optimized-vs-unoptimized benchmark suite")
    print(f"dataset_scale={scale.name} repetitions={args.repetitions} warmups={args.warmups}")
    print("")
    for workload in results:
        print(f"workload: {workload['name']} [{workload['category']}]")
        print(f"  {workload['description']}")
        print_family_summary("end_to_end", workload["end_to_end"])
        print_family_summary("lli_only", workload["lli_only"])
        print("")
    print(f"geometric mean speedup (optimized vs unoptimized, end_to_end): {payload['geometric_mean_speedup_end_to_end']:.2f}x")
    print(f"geometric mean speedup (optimized vs unoptimized, lli_only): {payload['geometric_mean_speedup_lli_only']:.2f}x")

    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
