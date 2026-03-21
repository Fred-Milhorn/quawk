from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path
from typing import Sequence

from . import __version__
from .diagnostics import LexError, ParseError, format_error
from .jit import emit_assembly, execute, lower_to_llvm_ir
from .lexer import format_tokens, lex
from .parser import format_program, parse
from .source import SourceText


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quawk",
        description="POSIX-oriented AWK compiler and JIT runtime.",
    )
    parser.add_argument(
        "-F",
        dest="field_separator",
        metavar="fs",
        help="Set input field separator FS.",
    )
    parser.add_argument(
        "-f",
        dest="program_files",
        metavar="progfile",
        action="append",
        default=[],
        help="Read AWK program source from file. Repeatable, in order.",
    )
    parser.add_argument(
        "-v",
        dest="assignments",
        metavar="var=value",
        action="append",
        default=[],
        help="Assign a variable before program execution. Repeatable.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the user-facing version and exit.",
    )
    stop_stage = parser.add_mutually_exclusive_group()
    stop_stage.add_argument(
        "--lex",
        action="store_true",
        help="Print tokens for the input program and exit.",
    )
    stop_stage.add_argument(
        "--parse",
        action="store_true",
        help="Print the parsed AST for the input program and exit.",
    )
    stop_stage.add_argument(
        "--ir",
        action="store_true",
        help="Print the generated LLVM IR and exit.",
    )
    stop_stage.add_argument(
        "--asm",
        action="store_true",
        help="Print the generated assembly and exit.",
    )
    parser.add_argument(
        "program",
        nargs="?",
        help="Inline AWK program text when -f is not used.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Input files processed in order.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"quawk {get_version()}")
        return 0

    if args.program_files and args.program is not None:
        parser.error("cannot mix -f progfile with inline program text")

    source = load_program_source(args.program_files, args.program)
    if source is None:
        parser.error("missing AWK program text or -f progfile")

    try:
        tokens = lex(source)
        if args.lex:
            sys.stdout.write(format_tokens(tokens))
            return 0

        program = parse(tokens)
        if args.parse:
            sys.stdout.write(format_program(program))
            return 0

        llvm_ir = lower_to_llvm_ir(program)
        if args.ir:
            sys.stdout.write(llvm_ir)
            return 0
        if args.asm:
            sys.stdout.write(emit_assembly(llvm_ir))
            return 0

        return execute(program)
    except OSError as exc:
        sys.stderr.write(f"quawk: {exc}\n")
        return 2
    except (LexError, ParseError) as exc:
        sys.stderr.write(format_error(exc))
        return 2
    except RuntimeError as exc:
        sys.stderr.write(f"quawk: {exc}\n")
        return 4


def get_version() -> str:
    try:
        return metadata.version("quawk")
    except metadata.PackageNotFoundError:
        return __version__


def load_program_source(
    program_files: list[str],
    inline_program: str | None,
) -> SourceText | None:
    if program_files:
        files = [(program_file, Path(program_file).read_text(encoding="utf-8")) for program_file in program_files]
        return SourceText.from_files(files)
    if inline_program is None:
        return None
    return SourceText.from_inline(inline_program)
