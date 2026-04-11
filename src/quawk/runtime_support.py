# Runtime support layer helpers.
# This module locates and compiles the package-owned C runtime used by the
# planned reusable record-driven execution backend.

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def find_tool(name: str, purpose: str) -> str:
    """Return one required tool from PATH or raise a user-facing runtime error."""
    tool_path = shutil.which(name)
    if tool_path is None:
        raise RuntimeError(f"{purpose} '{name}' is not available on PATH")
    return tool_path


def runtime_directory() -> Path:
    """Return the package directory that owns the C runtime support sources."""
    return Path(__file__).with_name("runtime")


def runtime_header_path() -> Path:
    """Return the public header for the C runtime support ABI."""
    return runtime_directory() / "qk_runtime.h"


def runtime_source_path() -> Path:
    """Return the C implementation file for the runtime support layer."""
    return runtime_directory() / "qk_runtime.c"


def find_clang() -> str:
    """Return the `clang` executable used to compile runtime support artifacts."""
    return find_tool("clang", "C compiler")


def find_llvm_as() -> str:
    """Return the `llvm-as` executable used to assemble generated IR modules."""
    return find_tool("llvm-as", "LLVM assembler")


def find_llvm_link() -> str:
    """Return the `llvm-link` executable used to link generated IR modules."""
    return find_tool("llvm-link", "LLVM linker")


def find_llvm_opt() -> str:
    """Return the `opt` executable used to optimize generated IR modules."""
    return find_tool("opt", "LLVM optimization tool")


def compile_runtime_object(output_dir: Path) -> Path:
    """Compile the C runtime support layer into one object file and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    object_path = output_dir / "qk_runtime.o"
    runtime_dir = runtime_directory()

    subprocess.run(
        [
            find_clang(),
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-c",
            str(runtime_source_path()),
            "-I",
            str(runtime_dir),
            "-o",
            str(object_path),
        ],
        check=True,
    )
    return object_path


def compile_runtime_bitcode(output_dir: Path) -> Path:
    """Compile the C runtime support layer into one LLVM bitcode file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    bitcode_path = output_dir / "qk_runtime.bc"
    runtime_dir = runtime_directory()

    subprocess.run(
        [
            find_clang(),
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-emit-llvm",
            "-c",
            str(runtime_source_path()),
            "-I",
            str(runtime_dir),
            "-o",
            str(bitcode_path),
        ],
        check=True,
    )
    return bitcode_path
