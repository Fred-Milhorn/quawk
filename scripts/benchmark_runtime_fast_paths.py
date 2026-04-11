"""Benchmark runtime fast-path improvements against a baseline helper-symbol rewrite.

This benchmark compares the same hot-path AWK workloads in two module forms:

- fast-path: generated IR that calls the inline fast-path runtime helpers
- baseline: the same module with fast-path helper symbols rewritten to the
  original helper entry points

The workloads mirror the runtime hot paths identified by the P29 profiling
pass so the benchmark stays focused on the actual helper-call reductions.
"""

from __future__ import annotations

import argparse
import json
import math
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

STRING_CONCAT_LOOP_PROGRAM = (
    "BEGIN { n = ITER; s = \"\"; "
    "for (i = 0; i < n; i++) { s = s \"x\" } "
    "; print length(s) }"
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

INLINE_TO_BASE_SYMBOLS = (
    ("@qk_scalar_get_number_inline", "@qk_scalar_get_number"),
    ("@qk_scalar_set_number_inline", "@qk_scalar_set_number"),
    ("@qk_scalar_get_inline", "@qk_scalar_get"),
    ("@qk_capture_string_arg_inline", "@qk_capture_string_arg"),
    ("@qk_compare_values_inline", "@qk_compare_values"),
    ("@qk_get_field_inline", "@qk_get_field"),
    ("@qk_next_record_inline", "@qk_next_record"),
    ("@qk_get_nr_inline", "@qk_get_nr"),
    ("@qk_get_fnr_inline", "@qk_get_fnr"),
    ("@qk_get_nf_inline", "@qk_get_nf"),
    ("@qk_get_filename_inline", "@qk_get_filename"),
)


@dataclass(frozen=True)
class ScaleConfig:
    name: str
    loop_iterations: int
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
    loop_iterations: int
    record_count: int


SCALE_CONFIGS = {
    "smoke": ScaleConfig(name="smoke", loop_iterations=5_000, record_count=120, file_count=2),
    "medium": ScaleConfig(name="medium", loop_iterations=40_000, record_count=8_000, file_count=3),
    "large": ScaleConfig(name="large", loop_iterations=200_000, record_count=60_000, file_count=4),
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


def geometric_mean(values: list[float]) -> float:
    """Return the geometric mean for positive values."""
    if not values:
        raise ValueError("geometric_mean requires at least one value")
    if any(value <= 0.0 for value in values):
        raise ValueError("geometric_mean requires all values to be positive")
    return math.exp(sum(math.log(value) for value in values) / len(values))


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
            name="string_concat_loop",
            category="string_kernel",
            description="String concatenation loop that exercises string capture and concat hot paths.",
            program_text=STRING_CONCAT_LOOP_PROGRAM.replace("ITER", str(scale.loop_iterations)),
            stdin_text="record\n",
            input_files=(),
            loop_iterations=scale.loop_iterations,
            record_count=1,
        ),
        PreparedWorkload(
            name="field_aggregate",
            category="runtime_workload",
            description="Record traversal with numeric field extraction and accumulation.",
            program_text=FIELD_AGGREGATE_PROGRAM,
            stdin_text=record_stream,
            input_files=(),
            loop_iterations=0,
            record_count=scale.record_count,
        ),
        PreparedWorkload(
            name="filter_transform",
            category="runtime_workload",
            description="Predicate-heavy record filtering with derived numeric output.",
            program_text=FILTER_TRANSFORM_PROGRAM,
            stdin_text=record_stream,
            input_files=(),
            loop_iterations=0,
            record_count=scale.record_count,
        ),
        PreparedWorkload(
            name="multi_file_reduce",
            category="runtime_workload",
            description="Multi-file traversal that exercises NR/FNR bookkeeping.",
            program_text=MULTI_FILE_REDUCTION_PROGRAM,
            stdin_text=None,
            input_files=multi_file_inputs,
            loop_iterations=0,
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


def rewrite_fast_path_symbols(llvm_ir: str) -> str:
    """Rewrite inline helper calls back to their base helper names."""
    rewritten_lines: list[str] = []
    for line in llvm_ir.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("define "):
            rewritten_lines.append(line)
            continue
        rewritten_line = line
        for inline_name, base_name in INLINE_TO_BASE_SYMBOLS:
            rewritten_line = rewritten_line.replace(inline_name, base_name)
        rewritten_lines.append(rewritten_line)
    return "\n".join(rewritten_lines)


def compile_modules(workload: PreparedWorkload) -> tuple[str, str]:
    """Build fast-path and baseline linked IR modules for one workload."""
    program = parse(lex(ProgramSource.from_inline(workload.program_text)))
    fast_ir = jit.build_public_execution_llvm_ir(program, list(workload.input_files), None, None, optimize=False)
    baseline_ir = rewrite_fast_path_symbols(fast_ir)
    return fast_ir, baseline_ir


def run_lli_module(lli_path: str, llvm_ir: str, *, stdin_text: str | None) -> tuple[float, str]:
    """Run one LLVM IR module with `lli` and return elapsed time plus stdout."""
    with TemporaryDirectory(prefix="quawk-fast-path-bench-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        ir_path = temp_dir / "module.ll"
        ir_path.write_text(llvm_ir, encoding="utf-8")

        start = time.perf_counter()
        completed = subprocess.run(
            [lli_path, "--entry-function=quawk_main", str(ir_path)],
            input=stdin_text,
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed = time.perf_counter() - start

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "lli failed to execute benchmark module")
    return elapsed, completed.stdout


def benchmark_pair(
    run_baseline,
    run_fast_path,
    *,
    repetitions: int,
    warmups: int,
) -> dict[str, object]:
    """Run warmups and measured samples for one baseline/fast-path pair."""
    reference_output = ""
    for _ in range(warmups):
        _, baseline_output = run_baseline()
        _, fast_output = run_fast_path()
        if baseline_output != fast_output:
            raise RuntimeError("warmup output mismatch; fast-path and baseline runs are not comparable")
        reference_output = baseline_output

    baseline_samples: list[float] = []
    fast_samples: list[float] = []
    for _ in range(repetitions):
        baseline_time, baseline_output = run_baseline()
        fast_time, fast_output = run_fast_path()
        if baseline_output != fast_output:
            raise RuntimeError("benchmark output mismatch; fast-path and baseline runs are not comparable")
        baseline_samples.append(baseline_time)
        fast_samples.append(fast_time)
        reference_output = baseline_output

    baseline_summary = summarize("baseline", baseline_samples, repetitions, warmups)
    fast_summary = summarize("fast_path", fast_samples, repetitions, warmups)
    speedup = baseline_summary.median_seconds / fast_summary.median_seconds
    return {
        "baseline": asdict(baseline_summary),
        "fast_path": asdict(fast_summary),
        "reference_output": reference_output,
        "median_speedup_fast_path_vs_baseline": speedup,
    }


def print_family_summary(name: str, family_payload: dict[str, object]) -> None:
    """Render one timing family summary block."""
    baseline = family_payload["baseline"]
    fast_path = family_payload["fast_path"]
    speedup = family_payload["median_speedup_fast_path_vs_baseline"]
    assert isinstance(baseline, dict)
    assert isinstance(fast_path, dict)
    assert isinstance(speedup, float)

    print(f"  {name}")
    print("    mode          median       p95          min          max")
    print(
        f"    baseline     {format_seconds(float(baseline['median_seconds'])):<12}"
        f"{format_seconds(float(baseline['p95_seconds'])):<13}"
        f"{format_seconds(float(baseline['min_seconds'])):<13}"
        f"{format_seconds(float(baseline['max_seconds']))}"
    )
    print(
        f"    fast_path    {format_seconds(float(fast_path['median_seconds'])):<12}"
        f"{format_seconds(float(fast_path['p95_seconds'])):<13}"
        f"{format_seconds(float(fast_path['min_seconds'])):<13}"
        f"{format_seconds(float(fast_path['max_seconds']))}"
    )
    print(f"    median speedup (fast path vs baseline): {speedup:.2f}x")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark runtime fast-path improvements across representative hot workloads.")
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

    with TemporaryDirectory(prefix="quawk-fast-path-bench-suite-") as temp_dir_name:
        workdir = Path(temp_dir_name)
        workloads = select_workloads(prepare_workloads(scale, workdir), args.workload)
        results: list[dict[str, object]] = []
        speedups: list[float] = []

        for workload in workloads:
            fast_ir, baseline_ir = compile_modules(workload)
            if fast_ir == baseline_ir:
                raise RuntimeError(f"workload {workload.name} did not produce any fast-path symbol rewrites")

            pair = benchmark_pair(
                lambda: run_lli_module(lli_path, baseline_ir, stdin_text=workload.stdin_text),
                lambda: run_lli_module(lli_path, fast_ir, stdin_text=workload.stdin_text),
                repetitions=args.repetitions,
                warmups=args.warmups,
            )
            speedup = pair["median_speedup_fast_path_vs_baseline"]
            assert isinstance(speedup, float)
            speedups.append(speedup)
            print(f"workload: {workload.name} [{workload.category}]")
            print(f"  {workload.description}")
            print_family_summary("lli_only", pair)
            print("")
            results.append(
                {
                    "name": workload.name,
                    "category": workload.category,
                    "description": workload.description,
                    "loop_iterations": workload.loop_iterations,
                    "record_count": workload.record_count,
                    "input_file_count": len(workload.input_files),
                    "fast_path": pair["fast_path"],
                    "baseline": pair["baseline"],
                    "reference_output": pair["reference_output"],
                    "median_speedup_fast_path_vs_baseline": speedup,
                }
            )

    payload = {
        "dataset_scale": scale.name,
        "repetitions": args.repetitions,
        "warmups": args.warmups,
        "workloads": results,
        "geometric_mean_speedup_fast_path_vs_baseline": geometric_mean(speedups),
    }

    print("runtime-fast-path benchmark suite")
    print(f"dataset_scale={scale.name} repetitions={args.repetitions} warmups={args.warmups}")
    print("baseline = same module with inline helper symbols rewritten to base helpers")
    print("")
    print(
        "geometric mean speedup (fast path vs baseline, lli_only): "
        f"{payload['geometric_mean_speedup_fast_path_vs_baseline']:.2f}x"
    )

    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
