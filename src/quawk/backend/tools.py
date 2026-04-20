from __future__ import annotations

import shutil
import subprocess
import sys
import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import TYPE_CHECKING, Any, Callable, TextIO, cast

from .. import runtime_support
from .driver import build_execution_driver_llvm_ir
from .state import InitialVariables

if TYPE_CHECKING:
    from ..ast import Program

OPTIMIZATION_PASS_PIPELINES: dict[int, tuple[str, ...]] = {
    1: ("-passes=mem2reg,instcombine,simplifycfg,gvn",),
    2: ("-O2", "-vectorize-loops"),
}
ASSEMBLY_PRUNE_FLAGS: tuple[str, ...] = (
    "-passes=internalize,globaldce",
    "-internalize-public-api-list=quawk_main",
)


def optimization_passes_for_level(level: int) -> list[str]:
    """Return the LLVM `opt` flags for one supported optimization level."""
    return list(OPTIMIZATION_PASS_PIPELINES.get(level, OPTIMIZATION_PASS_PIPELINES[1]))


def optimize_ir(
    llvm_ir: str,
    level: int = 1,
    *,
    runtime_support_module: Any = runtime_support,
    subprocess_module: Any = subprocess,
    warnings_module: Any = warnings,
) -> str:
    """Run LLVM `opt` over one generated IR module and return optimized text."""
    try:
        opt_path = runtime_support_module.find_llvm_opt()
    except RuntimeError as exc:
        warnings_module.warn(str(exc), RuntimeWarning)
        return llvm_ir
    result = subprocess_module.run(
        [opt_path, *optimization_passes_for_level(level), "-S"],
        input=llvm_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "opt failed to optimize generated IR")
    return cast(str, result.stdout)


def prune_ir_for_assembly(
    llvm_ir: str,
    *,
    runtime_support_module: Any = runtime_support,
    subprocess_module: Any = subprocess,
) -> str:
    """Drop unreachable linked helpers before lowering one module to assembly."""
    try:
        opt_path = runtime_support_module.find_llvm_opt()
    except RuntimeError:
        return llvm_ir
    result = subprocess_module.run(
        [opt_path, *ASSEMBLY_PRUNE_FLAGS, "-S"],
        input=llvm_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "opt failed to prune generated assembly IR")
    return cast(str, result.stdout)


def emit_assembly(
    llvm_ir: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    subprocess_module: Any = subprocess,
    prune_ir_for_assembly_func: Callable[[str], str] = prune_ir_for_assembly,
) -> str:
    """Run `llc` on LLVM IR and return the emitted assembly text."""
    llc_path = which("llc")
    if llc_path is None:
        raise RuntimeError("LLVM code generation tool 'llc' is not available on PATH")
    pruned_ir = prune_ir_for_assembly_func(llvm_ir)

    result = subprocess_module.run(
        [llc_path, "-o", "-", "-"],
        input=pruned_ir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "llc failed to produce assembly output")
    return cast(str, result.stdout)


def execute_llvm_ir(
    llvm_ir: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    run_process_with_current_stdin_func: Callable[[list[str]], subprocess.CompletedProcess[bytes]] | None = None,
) -> int:
    """Run one LLVM IR module with `lli` and return its exit status."""
    lli_path = which("lli")
    if lli_path is None:
        raise RuntimeError("LLVM JIT tool 'lli' is not available on PATH")

    run_with_stdin = run_process_with_current_stdin_func or run_process_with_current_stdin
    with NamedTemporaryFile(mode="w", suffix=".ll", encoding="utf-8", delete=False) as file_obj:
        file_obj.write(llvm_ir)
        ir_path = Path(file_obj.name)

    try:
        result = run_with_stdin([lli_path, "--entry-function=quawk_main", str(ir_path)])
    finally:
        ir_path.unlink(missing_ok=True)

    if result.stdout:
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
    return result.returncode


def assemble_llvm_ir(
    llvm_ir: str,
    output_path: Path,
    *,
    runtime_support_module: Any = runtime_support,
    subprocess_module: Any = subprocess,
) -> Path:
    """Assemble one LLVM IR module to bitcode and return the output path."""
    source_path = output_path.with_suffix(".ll")
    source_path.write_text(llvm_ir, encoding="utf-8")
    result = subprocess_module.run(
        [
            runtime_support_module.find_llvm_as(),
            str(source_path),
            "-o",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "llvm-as failed to assemble generated IR")
    return output_path


def link_reusable_execution_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    runtime_support_module: Any = runtime_support,
    subprocess_module: Any = subprocess,
    assemble_llvm_ir_func: Callable[[str, Path], Path] = assemble_llvm_ir,
    build_execution_driver_llvm_ir_func: Callable[
        [Program, str, list[str], str | None, InitialVariables | None], str
    ] = build_execution_driver_llvm_ir,
) -> str:
    """Link the reusable program module, runtime support, and execution driver into one IR module."""
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        runtime_bitcode = runtime_support_module.compile_runtime_bitcode(temp_dir)
        program_bitcode = assemble_llvm_ir_func(program_llvm_ir, temp_dir / "program.bc")
        driver_ir = build_execution_driver_llvm_ir_func(
            program,
            program_llvm_ir,
            input_files,
            field_separator,
            initial_variables,
        )
        driver_bitcode = assemble_llvm_ir_func(driver_ir, temp_dir / "driver.bc")
        linked_ir_path = temp_dir / "linked.ll"

        result = subprocess_module.run(
            [
                runtime_support_module.find_llvm_link(),
                str(runtime_bitcode),
                str(program_bitcode),
                str(driver_bitcode),
                "-S",
                "-o",
                str(linked_ir_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "llvm-link failed to link the reusable execution module")
        return linked_ir_path.read_text(encoding="utf-8")


def link_reusable_inspection_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    runtime_support_module: Any = runtime_support,
    subprocess_module: Any = subprocess,
    assemble_llvm_ir_func: Callable[[str, Path], Path] = assemble_llvm_ir,
    build_execution_driver_llvm_ir_func: Callable[
        [Program, str, list[str], str | None, InitialVariables | None], str
    ] = build_execution_driver_llvm_ir,
) -> str:
    """Link the program module and reusable driver without runtime implementations."""
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        program_bitcode = assemble_llvm_ir_func(program_llvm_ir, temp_dir / "program.bc")
        driver_ir = build_execution_driver_llvm_ir_func(
            program,
            program_llvm_ir,
            input_files,
            field_separator,
            initial_variables,
        )
        driver_bitcode = assemble_llvm_ir_func(driver_ir, temp_dir / "driver.bc")
        linked_ir_path = temp_dir / "linked.ll"

        result = subprocess_module.run(
            [
                runtime_support_module.find_llvm_link(),
                str(program_bitcode),
                str(driver_bitcode),
                "-S",
                "-o",
                str(linked_ir_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "llvm-link failed to link the reusable inspection module")
        return linked_ir_path.read_text(encoding="utf-8")


def run_process_with_current_stdin(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run one subprocess while forwarding the current stdin source when possible."""
    stdin_handle = current_stdin_handle()
    if stdin_handle is not None:
        return subprocess.run(
            command,
            stdin=stdin_handle,
            capture_output=True,
            check=False,
        )

    try:
        stdin_buffer = sys.stdin.buffer
    except AttributeError:
        try:
            stdin_text = sys.stdin.read()
        except OSError:
            stdin_bytes = b""
        else:
            stdin_bytes = stdin_text.encode("utf-8")
    else:
        try:
            stdin_bytes = stdin_buffer.read()
        except OSError:
            stdin_bytes = b""

    return subprocess.run(command, input=stdin_bytes, capture_output=True, check=False)


def current_stdin_handle() -> TextIO | None:
    """Return the current stdin handle when it can be forwarded directly to a subprocess."""
    try:
        sys.stdin.fileno()
    except (AttributeError, OSError):
        return None
    return sys.stdin
