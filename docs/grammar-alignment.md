# Grammar Alignment Plan

This document captures the follow-on plan from the current code-vs-doc review.

## Decision

Adopt these rules:

- [grammar.ebnf](/Users/fred/dev/quawk/docs/grammar.ebnf) is the concrete syntax contract and must be fully implemented.
- [design.md](/Users/fred/dev/quawk/docs/design.md) must describe the current implementation honestly.
- [quawk.asdl](/Users/fred/dev/quawk/docs/quawk.asdl) must either match the implemented AST shape or be split into a current AST and a future normalized AST.

The main issue is not random drift. The main issue is that `grammar.ebnf` is treated as implemented while parts of the parser, semantics layer, runtime, and backend still narrow it.

## Primary Workstreams

### 1. Finish parser support for the full grammar

Close every remaining concrete-syntax gap so accepted programs match [grammar.ebnf](/Users/fred/dev/quawk/docs/grammar.ebnf) exactly.

Known gaps from the review:

- `for (expr_list; expr?; expr_list)`:
  - the parser currently only accepts assignment statements in init and update slots
  - the grammar requires general expression lists
- `for (IDENT in expr)`:
  - the parser currently narrows the iterable to a bare identifier
  - the grammar requires a general expression
- audit all other productions and remove any remaining parser-side narrowing

Implementation tasks:

- generalize `ForStmt` from `AssignStmt | None` init and update fields to expression lists
- generalize `ForInStmt` from `array_name: str` to an expression node
- update parser helpers so loop parsing mirrors the EBNF directly
- add a grammar-coverage checklist mapping every nonterminal to parser code and tests

Acceptance:

- every production in `docs/grammar.ebnf` has a corresponding parser path
- no parser rejection remains for syntactically valid EBNF input unless the failure is semantic

### 2. Bring semantics up to the full grammar surface

Once parsing is complete, semantic validation must handle the full concrete surface.

Work items:

- validate generalized `for` init and update expression lists
- validate generalized `for ... in expr`
- validate all assignment-like expressions consistently
- validate all lvalue forms exactly as admitted by the grammar
- keep legality rules separate from syntax rules

Acceptance:

- parse-valid but semantically invalid programs fail in semantic analysis, not in parsing
- semantic diagnostics remain deterministic and coded

### 3. Bring runtime execution up to the full grammar surface

If the grammar admits it, public execution must either run it or the docs must explicitly scope execution separately from parsing. For this plan, the target is full grammar implementation, so public execution should cover the full grammar surface.

Likely follow-up from the parser gaps:

- execute `for` loops with general expr-list init and update forms
- execute `for (k in expr)` when the iterable expression resolves to an array-valued target
- remove current runtime assumptions that loop init and update nodes are assignment statements only

Broader runtime audit:

- verify every expression and operator family from the grammar executes
- verify every statement family from the grammar executes
- verify default-action and pattern behavior match the admitted grammar surface

Acceptance:

- every grammar feature is executable through public `quawk` execution
- unsupported-runtime errors no longer occur for grammar-admitted forms

### 4. Align the backend contract with the implemented grammar

Do not let the frontend claim a complete language while the backend silently narrows it.

Work items:

- audit backend subset checks in [jit.py](/Users/fred/dev/quawk/src/quawk/jit.py)
- remove stale host-runtime-only assumptions that exist only because the parser or runtime was previously narrower
- keep explicit docs for any remaining execution-path split:
  - public execution support
  - LLVM and reusable backend support
  - inspection support (`--ir`, `--asm`)

Acceptance:

- [design.md](/Users/fred/dev/quawk/docs/design.md) accurately distinguishes:
  - full language accepted by the parser
  - full language executable publicly
  - backend and inspection support, if still narrower

## Documentation Alignment

### 5. Rewrite current-state sections in `design.md`

Update the sections that describe current behavior so they describe what is true now, not what was true around earlier milestones.

Specific edits:

- refresh the “Currently supported execution path” section
- refresh the “Current architectural caveat” section
- remove statements that are now false, especially:
  - overly narrow feature lists
  - claims that Python is not implementing public record iteration or regex filtering when the host runtime still does
- add a short “Current implementation model” section covering:
  - parser surface
  - public execution surface
  - backend and inspection surface

### 6. Reconcile `quawk.asdl` with reality

Choose one of these approaches explicitly.

Option A, recommended:

- split the AST docs into:
  - `docs/current-ast.asdl`
  - `docs/quawk.asdl` as the future normalized AST
- update [design.md](/Users/fred/dev/quawk/docs/design.md) to explain the distinction

Option B:

- rewrite [quawk.asdl](/Users/fred/dev/quawk/docs/quawk.asdl) to match the current implemented AST exactly

Recommendation:

- prefer Option A because the implementation already has a concrete parser AST and a backend normalization layer
- keeping a single ASDL file for both current and future shapes will keep causing drift

### 7. Add an explicit conformance note to `grammar.ebnf`

Keep the grammar as the source of truth, but add a short header note saying:

- the grammar is intended to be fully implemented
- parser conformance is tested directly
- semantic and runtime restrictions are tracked separately

That makes the role of the grammar explicit.

## Test Plan

### 8. Add grammar conformance coverage as a first-class gate

Create or expand parser conformance tests so every grammar family is covered intentionally.

Required layers:

- parser conformance cases for every grammar production family
- focused loop cases for:
  - `for` with multiple init and update expressions
  - `for` with non-assignment expressions in init and update
  - `for (k in expr)` with legal and illegal iterable expressions
- semantic tests for parse-valid but illegal constructs
- end-to-end execution tests for every previously narrowed grammar form

### 9. Add doc and implementation sync checks

Not a custom validator for roadmap state, but lightweight regression checks are worth it here.

Recommended:

- keep a maintained checklist in tests or docs mapping grammar sections to tests
- add golden AST coverage for representative samples of every major grammar family
- adopt a review rule: parser changes touching grammar must update conformance coverage

## Suggested Rollout Order

1. Finish the parser conformance audit against `grammar.ebnf`.
2. Implement the missing loop and general-expression grammar forms.
3. Update semantic validation for the widened AST.
4. Update runtime execution for those widened forms.
5. Refresh `design.md`.
6. Split or rewrite the ASDL docs.
7. Add final conformance and execution coverage.
8. Mark the grammar and doc alignment milestone complete.

## Concrete Success Criteria

This effort is done when:

- every `grammar.ebnf` production is parseable
- no parser-only narrowing remains for valid grammar constructs
- public execution covers the full grammar surface
- [design.md](/Users/fred/dev/quawk/docs/design.md) accurately describes the current implementation
- [quawk.asdl](/Users/fred/dev/quawk/docs/quawk.asdl) is explicitly either:
  - the current AST
  - or the future AST, with a separate current-AST doc
- tests make grammar conformance and execution coverage visible

## Other Improvements Worth Making

- add a short “Implementation Status” table in [design.md](/Users/fred/dev/quawk/docs/design.md):
  - concrete syntax
  - semantic coverage
  - public execution
  - backend parity
- add one source-of-truth section explaining the three layers:
  - concrete syntax: `grammar.ebnf`
  - current parser AST
  - backend normalization or future AST
- reduce “current subset” phrasing in code comments where it no longer describes reality
- add a compatibility-phase prerequisite note:
  - compatibility work should not be used to discover grammar non-implementation gaps

## Recommendation

Do not try to fix docs first in isolation.

The best sequence is:

- finish the remaining `grammar.ebnf` implementation gaps
- then rewrite [design.md](/Users/fred/dev/quawk/docs/design.md)
- then split or rewrite the ASDL docs

That keeps the docs from going stale again one commit later.
