# AWK Parsing Strategy (High-Level)

This document outlines a practical parsing strategy for a POSIX-oriented AWK compiler written in SML (MLton) with an LLVM backend.

## Goals

- Match POSIX AWK behavior closely, including context-sensitive syntax.
- Keep the parser implementation understandable and testable in Standard ML.
- Produce a clean AST suitable for semantic analysis and LLVM lowering.

## Recommended Approach

- Use a two-layer design:
  - Context-sensitive lexer for tokenization decisions.
  - Hand-written parser for syntax (recursive descent for statements, precedence-driven parsing for expressions).
- Represent implicit concatenation as a synthetic operator in expression parsing.
- Treat regex literals as lexer-level context decisions (`REGEX` vs `/`).

## Front-End Pipeline

1. Source normalization: line tracking, newline tokens, comment handling.
2. Lexing: emit tokens with source spans and minimal semantic payloads.
3. Parsing: build AST from tokens using grammar in `GRAMMAR.md`.
4. AST validation: enforce grammar-adjacent constraints and better diagnostics.
5. Lowering prep: normalize AST shapes expected by semantic/codegen phases.

## Error Handling and Diagnostics

- Keep token spans on all AST nodes.
- Recover at statement boundaries (`;`, newline, `}`) to continue reporting errors.
- Prefer deterministic error messages over aggressive recovery heuristics.

## Conformance Strategy

- Start with core POSIX forms, then add corner cases behind tests.
- Validate behavior against known AWK implementations on focused examples.
- Maintain a compatibility list for intentionally unsupported extensions.

## Milestone Order

1. Lexer with context-sensitive `/` handling.
2. Expression parser with precedence and implicit concatenation.
3. Statement and top-level (`pattern { action }`, `function`) parsing.
4. Error recovery and diagnostics polish.
5. Conformance testing against POSIX-oriented cases.
