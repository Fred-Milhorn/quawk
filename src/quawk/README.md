# quawk Source Map

This package implements the `quawk` command: a POSIX-oriented AWK compiler and
LLVM-backed runtime. The implementation is organized as a compiler pipeline with
compatibility tooling alongside it.

## Pipeline

1. `cli.py` parses command-line options, loads AWK source, runs stop-after
   inspection modes, and reports user-facing errors.
2. `source.py` tracks source files, offsets, spans, and cursor movement.
3. `lexer.py` converts source text into tokens.
4. `ast.py` defines the syntax tree, `parser.py` builds it, and
   `ast_format.py` renders stable AST output for `--parse`.
5. `semantics.py` validates supported AWK constructs and produces program
   analysis used by the CLI and backend.
6. `ast_walk.py`, `normalization.py`, `type_inference.py`,
   `slot_allocation.py`, and `local_scalar_residency.py` prepare the program
   for lowering.
7. `jit.py` is the public backend facade for lowering and execution.
8. `backend/` owns backend state, LLVM tool orchestration, runtime ABI text,
   and generated driver IR.
9. `runtime_support.py` locates LLVM/C tools and compiles files under
   `runtime/`.
10. `compat/` owns corpus and upstream compatibility selection, execution, and
    divergence metadata.

## Main Modules

| Path | Owns |
|---|---|
| `__main__.py` | `python -m quawk` entrypoint |
| `cli.py` | user-facing CLI flow and stop-after modes |
| `diagnostics.py` | structured lexer, parser, and semantic errors |
| `source.py` | source locations, spans, and cursors |
| `lexer.py` | token definitions, lexing, and token formatting |
| `ast.py` | AST dataclasses, enums, type aliases, and AST-only helpers |
| `parser.py` | recursive-descent parsing and parser-local token helpers |
| `ast_format.py` | stable AST rendering for `--parse` and golden tests |
| `ast_walk.py` | shared AST child-expression traversal helpers |
| `builtins.py` | builtin variable, array, and function metadata |
| `semantics.py` | semantic validation and program analysis |
| `normalization.py` | lowering-oriented program normalization |
| `type_inference.py` | variable and expression type lattice inference |
| `slot_allocation.py` | runtime state slot layout helpers |
| `local_scalar_residency.py` | scalar-locality analysis for backend storage |
| `jit.py` | public backend facade and compatibility wrapper around lowering/execution helpers |
| `backend/state.py` | lowering-state dataclass and initial-variable type aliases |
| `backend/tools.py` | LLVM tool orchestration, IR assembly/linking, optimization, and execution helpers |
| `backend/runtime_abi.py` | reusable runtime declaration text and low-level LLVM text helpers |
| `backend/driver.py` | generated execution-driver IR and runtime slot/state helper logic |
| `backend/lower_program.py` | reusable program-phase and action lowering orchestration |
| `backend/lower_stmt.py` | statement lowering, print/printf emission, and loop/control-flow lowering |
| `backend/lower_expr.py` | numeric/string/condition expression lowering and record-pattern lowering |
| `backend/lower_lvalue.py` | variable-address, runtime name/slot, and string-assignment helper logic |
| `backend/lower_builtins.py` | builtin-call lowering helpers shared by runtime-backed expressions |
| `runtime_support.py` | LLVM/C tool lookup and runtime compilation |
| `runtime/` | C runtime ABI and implementation |
| `compat/` | corpus, upstream suite, and divergence tooling |
| `architecture_audit.py` | architecture-support manifest checks |

## Where To Start

- CLI behavior: start in `cli.py`, then follow into `lexer.py`, `parser.py`,
  `semantics.py`, and `jit.py`.
- New syntax: update tokens in `lexer.py`, AST support in `ast.py`, parser
  support in `parser.py`, validation in `semantics.py`, and lowering support
  in `jit.py`.
- Analysis changes: start in the pass that owns the question, then check
  repeated AST traversal in `normalization.py`, `semantics.py`,
  `type_inference.py`, and `local_scalar_residency.py`.
- Backend execution changes: start in `jit.py` for the public flow, then follow
  into `backend/`; runtime toolchain support lives in `runtime_support.py`, and
  C ABI changes belong under `runtime/`.
- Compatibility changes: start in `compat/corpus.py` for local corpus behavior
  or `compat/upstream_suite.py` for imported upstream cases.

## Current Refactor Direction

`P36` is a readability refactor wave. The goal is to move code along existing
ownership boundaries without changing public behavior.

Current landed moves:

- keep AST definitions and AST formatting out of `parser.py`
- expand shared AST traversal helpers for analysis passes
- split backend tool orchestration, driver IR, ABI declarations, and lowering
  state into `backend/` while keeping `jit.py` as the public facade
- add `backend/ir_builder.py` and use it in representative lowering paths
- split program, statement, expression, lvalue, and builtin lowering into
  focused backend modules while shrinking `jit.py` to the public facade

Remaining planned moves:

- split the C runtime into concise domain files under `runtime/`, such as
  `core.c`, `fields.c`, `values.c`, `arrays.c`, `io.c`, `builtins.c`, and
  `profile.c`
- prefer behavior-oriented test names when touching task-numbered tests

Naming should stay concise when the package or directory already supplies the
context. For example, a future `runtime/fields.c` is clearer than repeating
`runtime` in the filename.

See `../../docs/plans/implementation-readability-refactor-plan.md` for the full
plan.
