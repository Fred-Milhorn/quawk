# Structured compiler diagnostics.
# This module defines frontend error types and the shared formatting used for
# human-readable file:line:column error output.

from __future__ import annotations

from enum import StrEnum

from .source import SourceSpan


class SemanticErrorCode(StrEnum):
    DUPLICATE_FUNCTION_DEFINITION = "SEM001"
    FUNCTION_PARAMETER_CONFLICT = "SEM002"
    DUPLICATE_PARAMETER_NAME = "SEM003"
    BREAK_OUTSIDE_LOOP = "SEM004"
    CONTINUE_OUTSIDE_LOOP = "SEM005"
    NEXT_OUTSIDE_RECORD_ACTION = "SEM006"
    NEXTFILE_OUTSIDE_RECORD_ACTION = "SEM007"
    ASSIGN_TO_FUNCTION_NAME = "SEM008"
    RETURN_OUTSIDE_FUNCTION = "SEM009"
    UNDEFINED_FUNCTION_CALL = "SEM010"
    INVALID_BUILTIN_CALL = "SEM011"
    INVALID_INCREMENT_TARGET = "SEM012"
    INVALID_FOR_IN_ITERABLE = "SEM013"


class QuawkError(ValueError):
    def __init__(self, message: str, span: SourceSpan, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.span = span
        self.code = code


class LexError(QuawkError):
    pass


class ParseError(QuawkError):
    pass


class SemanticError(QuawkError):
    def __init__(self, message: str, span: SourceSpan, code: SemanticErrorCode | str):
        super().__init__(message, span, str(code))


def format_error(error: QuawkError) -> str:
    """Render a compiler error with source context and a caret indicator."""
    location = error.span.start_location()
    caret_indent = " " * (location.column - 1)
    code_text = f"[{error.code}]" if error.code is not None else ""
    return f"{error.span.format_start()}: error{code_text}: {error.message}\n{location.line_text}\n{caret_indent}^\n"
