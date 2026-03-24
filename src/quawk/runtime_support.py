# Runtime support layer helpers.
# This module locates and compiles the package-owned C runtime used by the
# planned reusable record-driven execution backend.

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


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
    clang_path = shutil.which("clang")
    if clang_path is None:
        raise RuntimeError("C compiler 'clang' is not available on PATH")
    return clang_path


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
