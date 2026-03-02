# Coding Standards

This document defines coding standards for `quawk`.

## Core Rules

- Do not throw exceptions in normal compiler/runtime control flow.
- Prefer explicit error values and typed result paths.
- Use descriptive names, but keep names reasonably short.
- Prefer shorter names when clarity is not reduced.
- Use Standard ML Basis routines for folds and traversals where appropriate.
- Prefer Basis-style folds over complex custom recursive looping constructs when behavior is equivalent.
- Comment code liberally to explain implementation intent and mechanics.
- Do not add comment fluff or restate obvious syntax.

## Error Handling

- Do not use exception-driven flow control for parser, semantic, backend, or runtime logic.
- Represent recoverable failures with structured error types.
- Attach source spans/locations to frontend and semantic errors when available.
- Ensure error messages describe what failed and why.

## Naming

- Use names that communicate role and meaning quickly.
- Avoid unnecessarily long identifiers.
- Avoid one-letter names except for local, conventional short-lived values.
- Keep module/function names consistent with their phase (`lexer`, `parser`, `sema`, `backend`, `runtime`).

## Control Flow and Data Traversal

- Prefer `List.foldl`, `List.foldr`, `List.map`, `List.app`, and related Basis routines for collection processing.
- Use explicit recursion when it is simpler or necessary for correctness.
- Avoid deeply nested recursive loops when a fold/map pipeline is clearer.

## Comments

- Add comments where implementation choices, invariants, or tricky behavior are not obvious.
- Explain parsing disambiguation decisions, semantic invariants, and backend lowering assumptions.
- Keep comments precise, technical, and relevant to maintainers.
- Do not add motivational, decorative, or redundant comments.

## Scope and Consistency

- Apply these rules to all SML, test, and support code unless a documented exception is approved.
- When rules conflict, prioritize correctness first, then readability, then brevity.
