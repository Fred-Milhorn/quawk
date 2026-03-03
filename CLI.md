# Command Line Interface

This document defines the `quawk` command line interface.

## Canonical Usage Message

```text
Usage:
  quawk [options] -f progfile ... [--] [file ...]
  quawk [options] 'program' [--] [file ...]
  quawk -h | --help
  quawk --version
  quawk --qk-version

POSIX-style options:
  -F fs                 Set input field separator FS.
  -f progfile           Read AWK program source from file (repeatable, in order).
  -v var=value          Assign variable before program execution (repeatable).

quawk options:
  --qk-cache=MODE       Cache mode: auto | off | read-only | refresh.
  --qk-cache-dir PATH   Cache directory.
  --qk-jit=MODE         JIT mode: on | off.
  --qk-dump-ast         Print parsed AST, then continue.
  --qk-dump-ir          Print generated IR, then continue.
  --qk-metrics          Print execution/cache metrics.
  --qk-posix-strict     Enable strict POSIX behavior checks.
  --qk-version          Print detailed build/runtime/toolchain info.

Program selection:
  - If one or more -f options are given, program text comes only from those files.
  - Otherwise, the first non-option argument is the AWK program text.
  - Mixing -f with inline program text is an error.

Input files:
  - Remaining operands are input files processed in order.
  - If no input files are provided, read standard input.
  - Operand "-" means standard input.

Exit status:
  0  Success
  2  Usage, parse, semantic, or configuration error
  3  Runtime execution error
  4  Internal compiler/runtime failure
```

## Goals

- Preserve familiar AWK invocation patterns.
- Keep POSIX-style options front and center.
- Reserve `--qk-` for `quawk`-specific controls.

## Base Invocation

Supported base forms:

```sh
quawk 'program' [file ...]
quawk -f program.awk [file ...]
quawk -f a.awk -f b.awk [file ...]
```

POSIX-style options (target behavior):

- `-F fs` set input field separator
- `-f file` load AWK source from file (repeatable)
- `-v name=value` set variable before program execution (repeatable)

Program source rule:

- If one or more `-f` options are present, concatenate those program files in order.
- Otherwise, the first non-option argument is the AWK program text.
- Remaining arguments are input files (or stdin if none).

## quawk-Specific Options (`--qk-`)

These flags are implementation controls and are not part of POSIX AWK:

- `--qk-cache=auto|off|read-only|refresh`
- `--qk-cache-dir <path>`
- `--qk-jit=on|off`
- `--qk-dump-ast`
- `--qk-dump-ir`
- `--qk-metrics`
- `--qk-posix-strict`
- `--qk-version`

Guidelines:

- `--qk-` options must never shadow POSIX option names.
- `--qk-` options should be stable and additive.
- Experimental options should be explicitly marked in help text.

## Option Precedence

- If both `-f` and inline program text are provided, this is an error.
- Repeated `-v` assignments are applied in argument order; later assignments override earlier ones.
- Repeated `--qk-cache` uses last-value-wins.
- `--qk-cache=off` disables all cache read/write behavior regardless of cache-dir setting.

## Exit Codes

Use the exit code mapping defined in the canonical usage message above.

## Help and Version

Use the help/version behavior defined in the canonical usage message above.

## Examples

```sh
# Inline program
quawk 'BEGIN { print "hello" }'

# Program file + input
quawk -f script.awk input.txt

# POSIX options with quawk cache controls
quawk -F: -v limit=10 -f script.awk --qk-cache=auto --qk-metrics data.txt

# Debug parser output
quawk -f script.awk --qk-dump-ast

# Disable JIT cache usage
quawk -f script.awk --qk-cache=off
```
