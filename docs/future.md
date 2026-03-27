# Future Work: Native Executable Emission

## Summary

`quawk` should gain a direct native executable output mode so users can compile
an AWK program into a runnable binary instead of only executing it immediately
or inspecting LLVM artifacts.

Chosen product contract:
- add `--exe PATH` as the executable-emission CLI flag
- produce a reusable native executable, not a baked one-shot invocation
- generated executables accept runtime `-F`, numeric `-v`, `--`, and positional
  input files
- executable emission supports only the current backend-lowered surface

## CLI Contract

Compiler usage:

```sh
quawk --exe PATH -f prog.awk
quawk --exe PATH 'BEGIN { print "hello" }'
```

Generated executable usage:

```sh
PATH [-F fs] [-v name=value ...] [--] [file ...]
```

Rules:
- `--exe` is mutually exclusive with `--lex`, `--parse`, `--ir`, and `--asm`
- compile-time `-F`, `-v`, and input-file operands are rejected in `--exe` mode
- generated executables do not re-expose inspection flags
- runtime `-v` remains numeric-only in the current subset

## Backend And Runtime Design

Implementation direction:
- reuse the existing LLVM lowering and reusable execution-module pipeline
- add a native-link path that assembles IR and invokes `clang`
- keep the current `quawk_main()`-based flow for JIT execution and inspection
- add a separate native executable entrypoint with
  `main(int argc, char **argv)`

Runtime argument handling:
- parse generated-executable arguments in the C runtime support layer, not in
  generated LLVM IR
- extract runtime file operands, optional `-F`, and numeric `-v` assignments
- let generated code map runtime `-v` assignments into compiled program-state
  slots using the known variable-index map

## Support Boundary

Executable emission intentionally matches the backend-lowered subset rather than
all public `quawk` execution.

That means:
- programs supported by the LLVM-backed execution/inspection path are eligible
  for `--exe`
- host-runtime-only programs fail with a clear user-facing error
- normal `quawk` execution behavior remains unchanged

## Test Plan

Required coverage:
- CLI help includes `--exe`
- `--exe` is mutually exclusive with `--lex`, `--parse`, `--ir`, and `--asm`
- compile and run a simple `BEGIN` executable
- compile and run a record-driven executable with runtime file operands
- generated executable honors runtime `-F`
- generated executable honors runtime numeric `-v`
- generated executable honors `--` and `-` stdin operand behavior
- `quawk --exe` rejects compile-time `-F`, `-v`, and input-file operands
- `quawk --exe` rejects host-runtime-only programs with a clear error
- missing `clang`, `llvm-as`, or `llvm-link` failures are surfaced cleanly

## Defaults And Assumptions

- `--exe PATH` is the only new compiler flag in this change
- generated executables expose only `-F`, `-v`, `--`, and positional file
  operands
- runtime `-v` stays numeric-only
- executable emission does not support the host-runtime fallback families in
  this version
