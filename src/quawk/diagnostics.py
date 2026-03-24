# Structured compiler diagnostics.
# This module defines frontend error types and the shared formatting used for
# human-readable file:line:column error output.

from __future__ import annotations

from .source import SourceSpan


class QuawkError(ValueError):
    def __init__(self, message: str, span: SourceSpan):
        super().__init__(message)
        self.message = message
        self.span = span


class LexError(QuawkError):
    pass


class ParseError(QuawkError):
    pass


def format_error(error: QuawkError) -> str:
    """Render a compiler error with source context and a caret indicator."""
    location = error.span.start_location()
    caret_indent = " " * (location.column - 1)
    return f"{error.span.format_start()}: error: {error.message}\n{location.line_text}\n{caret_indent}^\n"
