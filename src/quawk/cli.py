# User-facing command-line entrypoint.
# This module turns CLI options into compiler pipeline stages and owns the
# top-level source-loading and error-reporting flow.

from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path
from typing import Sequence

from . import __version__
from .diagnostics import LexError, ParseError, format_error
from .jit import emit_assembly, execute_with_inputs, lower_to_llvm_ir
from .lexer import format_tokens, lex
from .parser import format_program, parse
from .source import ProgramSource


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the user-facing `quawk` CLI."""
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
    """Run the CLI entrypoint and return a process-style exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"quawk {get_version()}")
        return 0

    if args.program_files and args.program is not None:
        # With `-f`, the remaining positional arguments are input files, not an
        # inline program. Reclassify the first positional token instead of
        # forcing users to work around argparse's fixed positional ordering.
        args.files = [args.program, *args.files]
        args.program = None

    try:
        source = load_program_source(args.program_files, args.program)
        if source is None:
            parser.error("missing AWK program text or -f progfile")

        tokens = lex(source)
        if args.lex:
            sys.stdout.write(format_tokens(tokens))
            return 0

        program = parse(tokens)
        if args.parse:
            sys.stdout.write(format_program(program))
            return 0

        if args.ir:
            # Lower once for the stop-after inspection modes so IR and assembly
            # are derived from the same pipeline.
            llvm_ir = lower_to_llvm_ir(program)
            sys.stdout.write(llvm_ir)
            return 0
        if args.asm:
            llvm_ir = lower_to_llvm_ir(program)
            sys.stdout.write(emit_assembly(llvm_ir))
            return 0

        return execute_with_inputs(program, args.files, args.field_separator)
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
    """Return the installed package version, or the local fallback during development."""
    try:
        return metadata.version("quawk")
    except metadata.PackageNotFoundError:
        return __version__


def load_program_source(
    program_files: list[str],
    inline_program: str | None,
) -> ProgramSource | None:
    """Return the logical AWK program source for `-f` inputs or inline text.

    The result is a `ProgramSource` that the frontend can lex and diagnose
    against. If no program was supplied, return `None` so the caller can emit
    the normal CLI usage error.
    """
    if program_files:
        # AWK allows multiple `-f` flags. Preserve each file as a distinct
        # physical source so diagnostics can still point at the correct origin,
        # while treating the sequence as one logical program.
        files: list[tuple[str, str]] = []
        for program_file in program_files:
            try:
                file_text = Path(program_file).read_text(encoding="utf-8")
            except OSError as exc:
                # Keep file-open failures as normal CLI diagnostics instead of
                # letting Python render a traceback from deep inside `pathlib`.
                message = exc.strerror or str(exc)
                raise OSError(f"{program_file}: {message}") from exc
            files.append((program_file, file_text))
        return ProgramSource.from_files(files)

    # Without `-f`, the first positional argument is the whole AWK program.
    # Returning `None` lets the caller report the standard "missing program"
    # usage error instead of inventing an empty program here.
    if inline_program is None:
        return None

    return ProgramSource.from_inline(inline_program)
