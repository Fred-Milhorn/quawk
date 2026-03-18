from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

from .parser import BeginProgram


def execute(program: BeginProgram) -> int:
    lli_path = shutil.which("lli")
    if lli_path is None:
        raise RuntimeError("LLVM JIT tool 'lli' is not available on PATH")

    llvm_ir = lower_to_llvm_ir(program)
    with NamedTemporaryFile(mode="w", suffix=".ll", encoding="utf-8", delete=False) as file_obj:
        file_obj.write(llvm_ir)
        ir_path = Path(file_obj.name)

    try:
        result = subprocess.run(
            [lli_path, "--entry-function=quawk_main", str(ir_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        ir_path.unlink(missing_ok=True)

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def lower_to_llvm_ir(program: BeginProgram) -> str:
    string_lengths = [len(statement.literal.encode("utf-8")) + 1 for statement in program.statements]
    globals_block = "\n".join(
        declare_string(index, statement.literal) for index, statement in enumerate(program.statements)
    )
    calls_block = "\n".join(emit_puts_call(index, byte_length) for index, byte_length in enumerate(string_lengths))

    return "\n".join(
        [
            "declare i32 @puts(ptr)",
            "",
            globals_block,
            "",
            "define i32 @quawk_main() {",
            "entry:",
            calls_block,
            "  ret i32 0",
            "}",
            "",
        ]
    )


def declare_string(index: int, literal: str) -> str:
    data = literal.encode("utf-8") + b"\x00"
    escaped = "".join(f"\\{byte:02X}" for byte in data)
    return f'@.str.{index} = private unnamed_addr constant [{len(data)} x i8] c"{escaped}"'


def emit_puts_call(index: int, byte_length: int) -> str:
    return (
        f"  %strptr.{index} = getelementptr inbounds "
        f"[{byte_length} x i8], ptr @.str.{index}, i64 0, i64 0\n"
        f"  %call.{index} = call i32 @puts(ptr %strptr.{index})"
    )
