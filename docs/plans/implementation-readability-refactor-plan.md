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

## Status Snapshot

The first P36 foundation steps are already landed:

- `src/quawk/README.md` now serves as the source-level implementation map
- AST definitions and formatting now live in `ast.py` and `ast_format.py`
- shared AST traversal helpers now live in `ast_walk.py`, and the first
  analysis passes already use them

The backend ownership extraction from `T-306` is now landed:

- `backend/tools.py` now owns LLVM tool orchestration, optimization, assembly,
  linking, and execution helpers
- `backend/driver.py` now owns execution-driver IR generation plus reusable
  runtime slot/state helper logic
- `backend/runtime_abi.py` now owns reusable declaration text and low-level LLVM
  string/GEP helpers
- `backend/state.py` now owns the lowering-state dataclass and initial-variable
  type aliases
- `jit.py` remains the public backend facade and compatibility wrapper during
  the refactor

The active readability-refactor work now starts at `T-308`:

- split statement, expression, lvalue, and builtin lowering into focused backend
  modules now that representative builder coverage exists
- split backend lowering by ownership boundary without replacing one monolith
  with several tightly coupled files
- decide whether the C runtime split should land now or be deferred explicitly
- improve discoverability for newly touched refactor-related tests

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

This hotspot is now mostly addressed by the extracted AST modules. The
remaining parser readability work is secondary to the backend split and should
stay focused on parser-local helpers rather than reopen already-landed AST
ownership moves.

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

### Landed foundation work

Phases 1 through 3 below are retained as checked-in context for how the current
P36 state was reached. New implementation work should start at Phase 4.

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

This phase is now landed. `jit.py` remains the public backend facade, but the
tool orchestration, driver generation, runtime ABI text, and lowering-state
types now have focused ownership under `backend/`.

Extract backend process/tool orchestration out of `jit.py`.

Recommended first extraction shape:

- `backend/tools.py` for `lli`, `llc`, `llvm-as`, `llvm-link`, `opt`, and
  subprocess orchestration
- `backend/driver.py` for generated driver IR
- `backend/runtime_abi.py` for runtime declaration text and ABI symbol names
- `backend/state.py` for lowering state/context types

Dependency-direction rules for this split:

- `backend/tools.py`, `backend/runtime_abi.py`, and `backend/state.py` must not
  import lowering modules
- `backend/driver.py` may depend on ABI/state helpers, but ABI/state helpers
  must not depend on driver rendering
- lowering modules may depend on ABI/state helpers, but not on LLVM subprocess
  orchestration
- `jit.py` should shrink toward a thin public facade during the transition
  rather than becoming a second ownership center

Acceptance:

- public execution and inspection behavior are unchanged
- `jit.py` no longer owns both LLVM process orchestration and detailed lowering
- runtime ABI declarations are defined in one auditable place
- tests that exercise `--ir`, `--asm`, and execution still pass

### Phase 5: Introduce a small LLVM IR builder

This phase is now landed. `backend/ir_builder.py` owns a lightweight text helper
for recurring LLVM emission, and representative lowering paths in `jit.py` now
use it for control flow, calls, stores, arithmetic, select, phi, and string GEP
construction.

Add a lightweight helper for recurring LLVM text emission.

The helper should be a text-emission convenience, not a second IR abstraction
layer. It should cover common operations without hiding the generated IR:

- fresh temporaries and labels
- `call`
- `load` and `store`
- branches and labels
- numeric binary operations
- simple `select`
- GEP helpers for string globals

It should not:

- introduce a parallel semantic model of LLVM IR
- absorb high-level AWK lowering decisions
- force broad reformatting of emitted IR just because helper calls replaced
  inline string formatting

Acceptance:

- representative statement and expression lowering code uses the helper
- generated IR remains stable or changes only in irrelevant temporary naming
  covered by existing tests
- lowering functions read in terms of AWK behavior and runtime calls rather
  than repeated string formatting

### Phase 6: Split statement and expression lowering

This phase is now landed. Lowering ownership is split across
`backend/lower_program.py`, `backend/lower_stmt.py`, `backend/lower_expr.py`,
`backend/lower_lvalue.py`, and `backend/lower_builtins.py`, while `jit.py`
remains the public facade and compatibility layer.

Move lowering by domain into focused modules.

Recommended initial module shape:

- `backend/lower_program.py`
- `backend/lower_stmt.py`
- `backend/lower_expr.py`
- `backend/lower_lvalue.py`
- `backend/lower_builtins.py`

Do not force an early split between numeric and string expression lowering if
that would create circular imports or spread coercion logic across too many
files. Numeric/string sub-splits can happen later if the first ownership split
proves stable and readable.

Acceptance:

- each module has one clear lowering responsibility
- no module becomes a second monolith
- dependency direction remains simple enough that contributors can follow the
  import graph without hopping through many thin wrappers
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

`T-309` landed as an explicit deferral rather than a source split. The checked-in
review kept the runtime as one translation unit for now because:

- `runtime_support.py` still compiles exactly one C source into one object or
  bitcode artifact, so a split would first need new multi-source compile/link
  plumbing
- `qk_runtime.c` still shares one opaque runtime struct and many private helper
  routines across field, scalar, array, IO, and scratch-buffer behavior, so an
  early split would mostly trade one large file for a new internal-header layer
- recent readability churn has been concentrated in the Python backend; keeping
  the runtime intact for one more phase keeps the public ABI easier to audit

Deferral remains acceptable when the checked-in review concludes that most
current runtime churn is still happening in the Python backend, and that a C
split would add build/link complexity without materially improving near-term
readability. An explicit deferral should record:

- why the current runtime file layout is still acceptable
- what signal would justify revisiting the split
- which runtime domains are the first candidates if the split resumes later

The current deferral records the following revisit signals:

- runtime changes begin landing repeatedly in clearly separate domains in the
  same review
- private runtime declarations need an internal header for another reason
- runtime compilation is already being widened to support multiple C artifacts

If the split resumes later, start with the lowest-coupling files first:

- `profile.c`
- `io.c`
- `fields.c`

Then revisit `arrays.c`, `values.c`, and `builtins.c` once the private helper
surface is smaller.

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
- prefer renaming or regrouping tests only when they are already being touched
  for refactor work
- do not move many unrelated tests in one review
- preserve marker behavior and existing suite selection

Acceptance:

- newly touched tests use behavior-oriented names
- a contributor can find coverage by feature area without knowing roadmap task
  IDs
- suite commands and marker behavior remain unchanged

`T-310` lands this phase by renaming the most relevant refactor-era task-numbered
test modules to behavior-oriented names while keeping the originating task IDs in
short module docstrings for traceability.

## Guardrails

- Keep each refactor behavior-preserving unless a task explicitly adds
  characterization tests first.
- Prefer moving code before rewriting logic.
- Keep public CLI, corpus, upstream compatibility, and generated runtime ABI
  behavior unchanged.
- Do not combine broad formatting churn with semantic moves.
- Keep foundational backend modules (`tools`, `runtime_abi`, `state`) below the
  lowering layer in the dependency graph.
- Keep `jit.py` imports or compatibility wrappers temporarily if that reduces
  review risk during the backend split.
- Avoid broad golden or IR-output rebaselines unless a move forces them and the
  review can explain why the changed output is semantically irrelevant.
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
