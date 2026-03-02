# Command Line Interface

This document defines the `quawk` command line interface.

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

Proposed exit code mapping:

- `0`: successful execution
- `2`: command line usage, parse, or semantic/configuration error
- `3`: runtime execution error
- `4`: internal compiler/runtime failure

## Help and Version

Required:

- `-h` / `--help`: print usage and option summary
- `--version`: print user-facing version
- `--qk-version`: print detailed build/toolchain/runtime metadata

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
