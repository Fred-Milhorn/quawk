# Implementation Readability Refactor Plan

This plan records a follow-on refactor wave focused on making the `quawk`
implementation easier to read, navigate, and modify without changing public
behavior.

The current codebase has a clear phase model: CLI, source handling, lexing,
parsing, semantic analysis, normalization, backend lowering, runtime support,
and compatibility tooling. The main readability problem is that several of
those phases have grown dense enough that a contributor has to understand too
much at once before making a small change.

## Goals

- make the compiler pipeline easy to follow from CLI entrypoint to runtime
  execution
- split large modules along real ownership boundaries
- make AST traversal and backend lowering contracts explicit
- reduce ad hoc LLVM string construction in ordinary lowering code
- keep the refactor behavior-preserving and reviewable
- keep compatibility and corpus behavior unchanged unless a task explicitly
  adds characterization coverage before a move

## Current Readability Hotspots

### `src/quawk/jit.py`

`jit.py` is the largest implementation hotspot. It currently combines:

- public execution and inspection helpers
- LLVM tool orchestration and linking
- runtime ABI declarations
- reusable BEGIN/record/END lowering
- statement lowering
- numeric expression lowering
- string expression lowering
- assignment and lvalue storage logic
- driver IR generation
- low-level LLVM string helpers

This makes it hard to answer a local question, such as "how does string
assignment lower?" or "where does runtime linking happen?", without scanning a
large backend file.

### `src/quawk/parser.py`

`parser.py` currently contains:

- AST node dataclasses and enums
- parser implementation
- AST formatting helpers
- token-to-operator helpers
- literal decoding helpers

The parser itself is readable, but its module has too many roles. Moving AST
definitions and formatting helpers out would make grammar parsing easier to
scan.

### Repeated AST Traversal

Several modules manually walk the same AST shapes:

- `normalization.py`
- `semantics.py`
- `type_inference.py`
- `local_scalar_residency.py`

Each manual traversal is understandable in isolation, but adding a new AST form
requires remembering every visitor-shaped module. A shared traversal helper or
visitor protocol would make omissions easier to avoid.

### Runtime Support C File

`src/quawk/runtime/qk_runtime.c` is also large. It combines runtime lifecycle,
record input, field splitting and rebuild, scalar storage, arrays, output
redirection, getline, regex, substitution, formatting, profiling, and builtins.

The C runtime is already organized by function naming, but splitting it by
domain would make the runtime easier to review and test incrementally.

### Test Discoverability

Many tests are behavior-oriented, but a large number are named after roadmap
task IDs. Task IDs are useful for historical traceability; behavior names are
more useful when a contributor is trying to find coverage for a language or
backend feature.

## Proposed Refactor Phases

### Phase 1: Add an implementation map

Create a source-level implementation map, likely `src/quawk/README.md`, that
describes the package layout and the main data/control flow:

1. CLI and source loading
2. lexing and parsing
3. semantic analysis
4. normalization and analysis passes
5. backend lowering and runtime linking
6. C runtime support
7. compatibility tooling

Acceptance:

- a new reader can identify where to start for parser, backend, runtime,
  compatibility, and test changes
- the map names the current large-module hotspots and points to the planned
  refactor path

### Phase 2: Extract AST and formatting modules

Split `parser.py` into focused modules:

- `ast.py` for AST dataclasses, enums, and type aliases
- `ast_format.py` for human-readable AST formatting
- `parser.py` for recursive-descent parsing and parser-local helpers

Acceptance:

- parser behavior is unchanged
- public imports used by tests and other modules are updated coherently
- parser-focused tests and docs-contract tests pass
- `parser.py` reads primarily as grammar parsing logic

### Phase 3: Introduce shared AST traversal helpers

Add a small shared traversal layer for passes that need to visit expressions,
statements, actions, patterns, functions, and whole programs.

The first version should be conservative. It does not need to be a heavy
framework. Useful shapes might include:

- `walk_expression(expr, visitor)`
- `walk_statement(stmt, visitor)`
- a protocol or callback object for pre/post expression and statement hooks
- helpers for visiting lvalue subscripts and pattern endpoints

Acceptance:

- at least two existing analysis passes use the shared traversal
- behavior remains unchanged
- future AST additions have one obvious traversal utility to extend

### Phase 4: Split backend orchestration from lowering

Extract backend process/tool orchestration out of `jit.py`.

Likely modules:

- `backend/tools.py` or `backend/link.py` for `lli`, `llc`, `llvm-as`,
  `llvm-link`, and optimization orchestration
- `backend/driver.py` for generated driver IR
- `backend/runtime_abi.py` for runtime declaration text and ABI symbol names
- `backend/state.py` for lowering state/context types

Acceptance:

- public execution and inspection behavior are unchanged
- `jit.py` no longer owns both LLVM process orchestration and detailed lowering
- runtime ABI declarations are defined in one auditable place
- tests that exercise `--ir`, `--asm`, and execution still pass

### Phase 5: Introduce a small LLVM IR builder

Add a lightweight helper for recurring LLVM text emission.

The helper should cover common operations without hiding the generated IR:

- fresh temporaries and labels
- `call`
- `load` and `store`
- branches and labels
- numeric binary operations
- simple `select`
- GEP helpers for string globals

Acceptance:

- representative statement and expression lowering code uses the helper
- generated IR remains stable or changes only in irrelevant temporary naming
  covered by existing tests
- lowering functions read in terms of AWK behavior and runtime calls rather
  than repeated string formatting

### Phase 6: Split statement and expression lowering

Move lowering by domain into focused modules.

Likely modules:

- `backend/lower_program.py`
- `backend/lower_stmt.py`
- `backend/lower_expr_numeric.py`
- `backend/lower_expr_string.py`
- `backend/lower_lvalue.py`
- `backend/lower_builtins.py`

Acceptance:

- each module has one clear lowering responsibility
- no module becomes a second monolith
- `jit.py` becomes a compatibility facade or thin public API wrapper during the
  transition
- backend parity and core suites pass

### Phase 7: Split C runtime by domain

Split `qk_runtime.c` into multiple C files while preserving the public
`qk_runtime.h` ABI.

Likely files under `src/quawk/runtime/`:

- `core.c`
- `fields.c`
- `values.c`
- `arrays.c`
- `io.c`
- `builtins.c`
- `profile.c`

The build helper should compile and link all runtime sources. This should land
only after the Python backend split is stable enough that runtime ABI
declarations are easier to audit.

Acceptance:

- runtime object/bitcode build handles multiple C sources
- generated programs link and execute unchanged
- runtime-focused tests pass
- public `qk_runtime.h` remains the ABI entrypoint

### Phase 8: Improve test discoverability

Gradually migrate task-numbered tests into behavior-oriented test modules.

Guidelines:

- keep task IDs in comments where historical traceability is useful
- prefer module names that answer "what behavior is covered here?"
- do not move many unrelated tests in one review
- preserve marker behavior and existing suite selection

Acceptance:

- newly touched tests use behavior-oriented names
- a contributor can find coverage by feature area without knowing roadmap task
  IDs
- suite commands and marker behavior remain unchanged

## Guardrails

- Keep each refactor behavior-preserving unless a task explicitly adds
  characterization tests first.
- Prefer moving code before rewriting logic.
- Keep public CLI, corpus, upstream compatibility, and generated runtime ABI
  behavior unchanged.
- Do not combine broad formatting churn with semantic moves.
- Keep `jit.py` imports or compatibility wrappers temporarily if that reduces
  review risk during the backend split.
- Run focused tests after each move, then `uv run pytest -q -m core` at phase
  boundaries.

## Suggested Validation

For parser/AST moves:

```sh
uv run pytest -q tests/test_parser.py tests/test_parser_goldens.py tests/test_parser_conformance.py
uv run pytest -q -m core
```

For backend moves:

```sh
uv run pytest -q tests/test_jit.py tests/test_cli.py tests/test_p9_backend_parity.py
uv run pytest -q -m core
```

For runtime C splits:

```sh
uv run pytest -q tests/test_runtime_support.py tests/test_jit.py tests/test_p8_runtime_baselines.py
uv run pytest -q -m core
```

For compatibility-sensitive moves:

```sh
uv run pytest -m compat_corpus
uv run pytest -m compat_reference
```

## Definition Of Done

The readability refactor wave is complete when:

- `src/quawk/README.md` or equivalent source map exists
- AST definitions and formatting are no longer embedded in `parser.py`
- at least the highest-churn AST analysis passes share traversal helpers
- backend orchestration, runtime ABI declarations, lowering state, statement
  lowering, and expression lowering are no longer all in `jit.py`
- the runtime C source is split or has a checked-in decision explaining why a
  split should wait
- newly touched tests use behavior-oriented organization
- core validation passes after the final refactor task
