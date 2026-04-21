# Parser/EBNF Conformance Plan

This plan records a parser-only follow-on wave to prove that `docs/quawk.ebnf`
matches the grammar the checked-in parser actually accepts.

The goal is narrower than "the compiler supports the whole language end to
end." This wave is only about the parser contract:

- what `docs/quawk.ebnf` admits
- what `src/quawk/parser.py` accepts
- what the parser-focused test surface proves

## Why This Follow-On Exists

The current repository state is strong but not exhaustive:

- `docs/quawk.ebnf` describes the intended concrete syntax contract
- `src/quawk/parser.py` has explicit parsing paths for the major documented
  forms
- `tests/test_parser.py`, `tests/test_parser_goldens.py`, and
  `tests/test_parser_conformance.py` all pass

But the current conformance matrix only requires a subset of grammar sections.
That means the repo can honestly say parser coverage is healthy, but not yet
that every meaningful EBNF production and disambiguation rule is explicitly
proven by checked-in tests.

## Goals

- inventory every meaningful parser contract surface in `docs/quawk.ebnf`
- make parser conformance coverage explicit instead of implied
- add direct parser tests for ambiguous or failure-prone boundaries
- keep parser claims separate from semantics and lowering/execution claims
- avoid broadening this wave into a language-support rebaseline

## Non-Goals

This wave does not, by itself, claim that every parsed form:

- passes semantic validation
- lowers through the LLVM backend/runtime path
- is part of the current compiled execution contract

Those are separate surfaces and should remain separate.

## Current Problem Shape

### 1. Conformance coverage is intentionally partial

`tests/test_parser_conformance.py` currently tracks only a subset of grammar
sections. That is useful as an early conformance matrix, but it is not yet an
exhaustive parser/EBNF proof.

### 2. Some grammar risk lives in disambiguation rules, not just productions

The most error-prone parser behavior is not only "can this production parse?"
but also:

- implicit concatenation boundaries
- regex literal vs division operator context
- `for (...)` vs `for (... in ...)`
- `printf` argument parsing
- `getline` target/source variants
- `delete` and lvalue forms
- ternary and assignment associativity

Those need direct parser tests in addition to fixture-backed positive coverage.

### 3. Parsing claims should stay separate from later compiler stages

Even after this wave lands, "the parser accepts the documented grammar" should
not be conflated with "the compiler supports every admitted form end to end."

## Proposed Phases

### Phase 1: Inventory the documented parser contract

Extract a concrete inventory from `docs/quawk.ebnf` that includes:

- top-level productions
- statement forms
- expression-precedence layers
- lvalue and redirect forms
- function-definition and pattern-action forms
- disambiguation rules for concat and regex-vs-division

For each inventory item, classify current evidence as:

- covered
- partially covered
- uncovered

Acceptance:

- every meaningful EBNF production/rule is listed once in the inventory
- the inventory makes current coverage gaps explicit
- inventory terminology matches `docs/quawk.ebnf`

Landed inventory:

- [parser-ebnf-coverage-inventory.md](parser-ebnf-coverage-inventory.md)

### Phase 2: Expand parser conformance fixtures

Grow `tests/conformance/` and `tests/test_parser_conformance.py` so the
fixture-backed coverage matrix spans the documented parser contract rather than a
small starter subset.

Use file-backed cases when a documented syntax form is best represented as a
small AWK program. Keep the grammar-section labels explicit and reviewable.

Acceptance:

- every documented parser contract area has at least one positive conformance
  fixture
- the conformance coverage matrix fails if a documented grammar area loses all
  fixture coverage
- conformance fixture names stay understandable without roadmap-task knowledge

Landed fixture expansion:

- `tests/conformance/`
- `tests/test_parser_conformance.py`

### Phase 3: Add ambiguous and negative parser coverage

Use direct parser tests for boundary cases where fixture coverage alone is not
enough.

Priority areas:

- implicit concat adjacency
- regex literal vs division
- `for` vs `for ... in`
- `printf` forms, including parenthesized arguments
- `getline` target/source variants
- `delete` target forms
- lvalue restrictions for assignment
- ternary and assignment associativity
- representative invalid forms that should fail at parse time

Acceptance:

- high-risk parser ambiguities have direct positive and/or negative tests
- AST-shape assertions remain local and readable
- invalid forms fail with parser errors rather than silently producing the wrong
  tree

### Phase 4: Sync parser-facing docs and close out

After the coverage expansion lands:

- update `docs/quawk.ebnf` only where the documented grammar and tested parser
  contract actually diverge
- keep any wording about semantics or lowering out of this parser plan
- record the final validation used to close the wave

Acceptance:

- `docs/quawk.ebnf` and the parser-focused test surface describe the same parser
  contract
- the roadmap can honestly say whether parser/EBNF coverage is exhaustive
- no parser-facing doc wording overclaims semantics or lowering support

## Suggested Validation

Primary validation:

```sh
uv run pytest -q tests/test_parser.py tests/test_parser_goldens.py tests/test_parser_conformance.py
```

Follow-up validation only if parser changes ripple outward:

```sh
uv run pytest -q -m core
```

## Definition Of Done

This wave is complete when:

- every meaningful production and disambiguation rule in `docs/quawk.ebnf` has
  an explicit coverage classification
- the parser conformance matrix covers the full documented parser contract
- ambiguous and failure-prone parser boundaries have direct tests
- `docs/quawk.ebnf` and checked-in parser tests no longer disagree about the
  parser contract
- the roadmap records the final parser/EBNF conformance status honestly
