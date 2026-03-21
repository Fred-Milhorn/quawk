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
    location = error.span.start()
    caret_indent = " " * (location.column - 1)
    return (f"{error.span.format_start()}: error: {error.message}\n"
            f"{location.line_text}\n"
            f"{caret_indent}^\n")
