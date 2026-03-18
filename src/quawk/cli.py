from __future__ import annotations

import argparse
import sys
from importlib import metadata
from typing import Sequence

from . import __version__


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

    if not args.program_files and args.program is None:
        parser.error("missing AWK program text or -f progfile")

    sys.stderr.write("quawk: execution path not implemented yet\n")
    return 2


def get_version() -> str:
    try:
        return metadata.version("quawk")
    except metadata.PackageNotFoundError:
        return __version__
