# Lowering and execution backend facade for the currently supported subset.

from __future__ import annotations

import shutil
import subprocess
import warnings
from pathlib import Path

from . import runtime_support
from .ast import Program
from .backend import driver as backend_driver
from .backend import tools as backend_tools
from .backend.driver import runtime_numeric_slot_indexes, runtime_slot_indexes, runtime_string_slot_indexes
from .backend.lower_lvalue import runtime_name_slot_index
from .backend.lower_program import lower_reusable_program_to_llvm_ir
from .backend.state import InitialVariables, InitialVariableValue, LoweringState
from .normalization import normalize_program_for_lowering
from .type_inference import infer_variable_types

__all__ = [
    "InitialVariableValue",
    "InitialVariables",
    "LoweringState",
    "runtime_name_slot_index",
    "runtime_numeric_slot_indexes",
    "runtime_slot_indexes",
    "runtime_string_slot_indexes",
]


def emit_assembly(llvm_ir: str) -> str:
    """Run `llc` on LLVM IR and return the emitted assembly text."""
    return backend_tools.emit_assembly(
        llvm_ir,
        which=shutil.which,
        subprocess_module=subprocess,
        prune_ir_for_assembly_func=prune_ir_for_assembly,
    )


def execute(program: Program, initial_variables: InitialVariables | None = None, *, optimize: bool = False) -> int:
    """Lower `program` to IR, run it with `lli`, and return the process status."""
    llvm_ir = build_public_execution_llvm_ir(program, [], None, initial_variables, optimize=optimize)
    return execute_llvm_ir(llvm_ir)


def execute_with_inputs(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    optimize: bool = False,
) -> int:
    """Lower `program`, link the reusable driver, and execute it for the given input configuration."""
    llvm_ir = build_public_execution_llvm_ir(
        program,
        input_files,
        field_separator,
        initial_variables,
        optimize=optimize,
    )
    return execute_llvm_ir(llvm_ir)


def execute_llvm_ir(llvm_ir: str) -> int:
    """Run one LLVM IR module with `lli` and return its exit status."""
    return backend_tools.execute_llvm_ir(llvm_ir, which=shutil.which)


def lower_to_llvm_ir(program: Program, initial_variables: InitialVariables | None = None) -> str:
    """Lower the currently supported AST subset to LLVM IR text."""
    normalized_program = normalize_program_for_lowering(program)
    type_info = infer_variable_types(program)
    _ = initial_variables
    return lower_reusable_program_to_llvm_ir(program, normalized_program, type_info)


def build_public_execution_llvm_ir(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    optimize: bool = False,
) -> str:
    """Build the IR module used by public execution and inspection paths."""
    llvm_ir = lower_to_llvm_ir(program, initial_variables=initial_variables)
    if program_requires_linked_execution_module(program, initial_variables):
        llvm_ir = link_reusable_execution_module(llvm_ir, program, input_files, field_separator, initial_variables)
    if optimize:
        return optimize_ir(llvm_ir)
    return llvm_ir


def build_public_inspection_llvm_ir(
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
    *,
    optimize: bool = False,
) -> str:
    """Build the IR module used by public inspection modes."""
    llvm_ir = lower_to_llvm_ir(program, initial_variables=initial_variables)
    if program_requires_linked_execution_module(program, initial_variables):
        llvm_ir = link_reusable_inspection_module(llvm_ir, program, input_files, field_separator, initial_variables)
    if optimize:
        return optimize_ir(llvm_ir)
    return llvm_ir


def optimization_passes_for_level(level: int) -> list[str]:
    """Return the LLVM `opt` flags for one supported optimization level."""
    return backend_tools.optimization_passes_for_level(level)


def optimize_ir(llvm_ir: str, level: int = 1) -> str:
    """Run LLVM `opt` over one generated IR module and return optimized text."""
    return backend_tools.optimize_ir(
        llvm_ir,
        level=level,
        runtime_support_module=runtime_support,
        subprocess_module=subprocess,
        warnings_module=warnings,
    )


def prune_ir_for_assembly(llvm_ir: str) -> str:
    """Drop unreachable linked helpers before lowering one module to assembly."""
    return backend_tools.prune_ir_for_assembly(
        llvm_ir,
        runtime_support_module=runtime_support,
        subprocess_module=subprocess,
    )


def program_requires_linked_execution_module(
    program: Program,
    initial_variables: InitialVariables | None = None,
) -> bool:
    """Report whether public execution/inspection needs the reusable driver module."""
    _ = program
    _ = initial_variables
    return True


def execute_host_runtime(*args: object, **kwargs: object) -> int:
    """Legacy host-runtime seam retained only for compatibility patch points."""
    raise RuntimeError("host runtime execution is no longer part of the supported backend path")


def lower_input_aware_program_to_llvm_ir(*args: object, **kwargs: object) -> str:
    """Legacy input-aware lowering seam retained only for compatibility patch points."""
    raise RuntimeError("legacy input-aware lowering has been replaced by the reusable backend path")


def link_reusable_execution_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Link the reusable program module, runtime support, and execution driver into one IR module."""
    return backend_tools.link_reusable_execution_module(
        program_llvm_ir,
        program,
        input_files,
        field_separator,
        initial_variables,
        runtime_support_module=runtime_support,
        subprocess_module=subprocess,
        assemble_llvm_ir_func=assemble_llvm_ir,
        build_execution_driver_llvm_ir_func=build_execution_driver_llvm_ir,
    )


def link_reusable_inspection_module(
    program_llvm_ir: str,
    program: Program,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Link the program module and reusable driver without runtime implementations."""
    return backend_tools.link_reusable_inspection_module(
        program_llvm_ir,
        program,
        input_files,
        field_separator,
        initial_variables,
        runtime_support_module=runtime_support,
        subprocess_module=subprocess,
        assemble_llvm_ir_func=assemble_llvm_ir,
        build_execution_driver_llvm_ir_func=build_execution_driver_llvm_ir,
    )


def assemble_llvm_ir(llvm_ir: str, output_path: Path) -> Path:
    """Assemble one LLVM IR module to bitcode and return the output path."""
    return backend_tools.assemble_llvm_ir(
        llvm_ir,
        output_path,
        runtime_support_module=runtime_support,
        subprocess_module=subprocess,
    )


def build_execution_driver_llvm_ir(
    program: Program,
    program_llvm_ir: str,
    input_files: list[str],
    field_separator: str | None,
    initial_variables: InitialVariables | None = None,
) -> str:
    """Build the reusable execution driver that invokes runtime and program phases."""
    return backend_driver.build_execution_driver_llvm_ir(
        program,
        program_llvm_ir,
        input_files,
        field_separator,
        initial_variables,
    )
