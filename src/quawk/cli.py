# User-facing command-line entrypoint.
# This module turns CLI options into compiler pipeline stages and owns the
# top-level source-loading and error-reporting flow.

from __future__ import annotations

import argparse
import os
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Sequence

from . import __version__
from .ast_format import format_program
from .diagnostics import LexError, ParseError, SemanticError, format_error
from .jit import (
    InitialVariableValue,
    build_public_inspection_llvm_ir,
    emit_assembly,
    execute_with_inputs,
)
from .lexer import format_tokens, lex
from .parser import parse
from .semantics import ProgramAnalysis, analyze
from .source import ProgramSource

IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
CLI_USAGE = """quawk [options] -f progfile ... [--] [file ...]
       quawk [options] program [--] [file ...]
       quawk -h | --help
       quawk --version"""
CLI_EPILOG = """Run-path rules:
  - With one or more -f flags, positional operands are input files.
  - Use -- before a program or file operand that begins with '-'.
  - Operand '-' means standard input at that position."""


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the user-facing `quawk` CLI."""
    parser = argparse.ArgumentParser(
        prog="quawk",
        description="POSIX-oriented AWK compiler and JIT runtime.",
        usage=CLI_USAGE,
        epilog=CLI_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "-O",
        "--optimize",
        action="store_true",
        help="Enable optimization mode for generated IR/execution.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the user-facing version and exit.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Re-raise internal exceptions for contributor debugging.",
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
        help="Print the generated LLVM IR and exit. Use --ir=optimized to request optimized IR.",
    )
    stop_stage.add_argument(
        "--optimized-ir",
        dest="optimized_ir",
        action="store_true",
        help=argparse.SUPPRESS,
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
    args = parser.parse_args(normalize_arguments(argv))

    if args.version:
        print(f"quawk {get_version()}")
        return 0

    if args.program_files and args.program is not None:
        # With `-f`, the remaining positional arguments are input files, not an
        # inline program. Reclassify the first positional token instead of
        # forcing users to work around argparse's fixed positional ordering.
        args.files = [args.program, *args.files]
        args.program = None

    debug_exceptions = args.debug or os.environ.get("QUAWK_DEBUG") == "1"

    try:
        initial_variables = parse_assignments(args.assignments)
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

        analysis = analyze(program)

        if args.ir or args.optimized_ir:
            # Lower once for the stop-after inspection modes so IR and assembly
            # are derived from the same pipeline.
            llvm_ir = build_public_inspection_llvm_ir(
                program,
                args.files,
                args.field_separator,
                initial_variables,
                optimize=args.optimize or args.optimized_ir,
            )
            sys.stdout.write(llvm_ir)
            return 0

        if args.asm:
            llvm_ir = build_public_inspection_llvm_ir(
                program,
                args.files,
                args.field_separator,
                initial_variables,
                optimize=args.optimize,
            )
            sys.stdout.write(emit_assembly(llvm_ir))
            return 0

        validate_assignment_targets(initial_variables, analysis)
        return execute_with_inputs(
            program,
            args.files,
            args.field_separator,
            initial_variables,
            optimize=args.optimize,
        )

    except KeyboardInterrupt:
        if debug_exceptions:
            raise
        sys.stderr.write("quawk: interrupted\n")
        return 130
    except OSError as exc:
        if debug_exceptions:
            raise
        sys.stderr.write(f"quawk: {exc}\n")
        return 2
    except (LexError, ParseError, SemanticError) as exc:
        sys.stderr.write(format_error(exc))
        return 2
    except ValueError as exc:
        if debug_exceptions:
            raise
        sys.stderr.write(f"quawk: {exc}\n")
        return 2
    except RuntimeError as exc:
        if debug_exceptions:
            raise
        sys.stderr.write(f"quawk: {exc}\n")
        return 4


def get_version() -> str:
    """Return the installed package version, or the local fallback during development."""
    try:
        return metadata.version("quawk")
    except metadata.PackageNotFoundError:
        return __version__


def normalize_arguments(argv: Sequence[str] | None) -> list[str]:
    """Rewrite CLI aliases into the shape argparse expects."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    normalized_arguments: list[str] = []
    for token in raw_arguments:
        if token == "--ir=optimized":
            normalized_arguments.append("--optimized-ir")
            continue
        normalized_arguments.append(token)
    return normalized_arguments


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


def parse_assignments(assignments: list[str]) -> list[tuple[str, InitialVariableValue]]:
    """Parse ordered `-v name=value` assignments for execution."""
    parsed: list[tuple[str, InitialVariableValue]] = []
    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(f"invalid -v assignment {assignment!r}: expected name=value")

        name, raw_value = assignment.split("=", 1)
        if not IDENTIFIER_PATTERN.fullmatch(name):
            raise ValueError(f"invalid -v variable name {name!r}")
        try:
            value = float(raw_value)
        except ValueError:
            value = raw_value
        parsed.append((name, value))
    return parsed


def validate_assignment_targets(assignments: list[tuple[str, InitialVariableValue]], analysis: ProgramAnalysis) -> None:
    """Reject `-v` assignments that collide with top-level function names."""
    for name, _ in assignments:
        if name in analysis.functions:
            raise ValueError(f"cannot assign to function name via -v: {name}")
