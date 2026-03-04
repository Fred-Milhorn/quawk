# Coding Standards

This document defines coding standards for `quawk`.

## Core Rules

- Prefer explicit, typed data flow over implicit side effects.
- Keep parser/sema/backend/runtime boundaries explicit.
- Use descriptive names that communicate intent quickly.
- Prefer short functions with single focused responsibilities.
- Add comments for invariants, disambiguation rules, and non-obvious behavior.
- Do not add comment fluff or restate obvious syntax.

## Error Handling

- Do not use exception-driven control flow for expected parser/sema/runtime paths.
- Represent recoverable failures with structured result/error objects.
- Attach source spans to frontend and semantic errors when available.
- Keep error classes stable for testability.

## Naming

- Use `snake_case` for functions/variables/modules.
- Use `PascalCase` for classes/dataclasses/enums.
- Avoid one-letter names except short-lived local indices.
- Keep phase-oriented naming consistent (`lexer`, `parser`, `sema`, `backend`, `runtime`).

## Types and Data Models

- Public module boundaries should be type-annotated.
- Prefer `dataclass` or `TypedDict` for structured records over ad hoc dicts.
- Keep AST/IR models immutable by default where practical.

## Control Flow and Data Traversal

- Prefer straightforward loops/comprehensions over overly abstract pipelines.
- Use helper functions to avoid deeply nested branches.
- Keep recursion explicit and bounded where used for tree traversal.

## Comments

- Explain parser disambiguation decisions and semantic invariants.
- Document backend lowering assumptions at module boundaries.
- Keep comments precise, technical, and maintainer-oriented.

## Scope and Consistency

- Apply these rules to all Python source, tests, and support scripts unless a documented exception is approved.
- When rules conflict, prioritize correctness first, then readability, then brevity.
