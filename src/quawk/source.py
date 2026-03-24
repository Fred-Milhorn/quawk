# Source tracking primitives for the frontend.
# This module maps logical program positions back to real files, lines, and
# columns, and provides the cursor abstraction shared by the scanner.

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


def build_line_starts(text: str) -> tuple[int, ...]:
    """Return the starting offset of each physical line in `text`."""
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return tuple(starts)


@dataclass(frozen=True)
class ResolvedLocation:
    source_name: str
    line: int
    column: int
    line_text: str


@dataclass(frozen=True)
class SourcePoint:
    file_index: int
    offset: int


@dataclass(frozen=True)
class SourceFile:
    name: str
    text: str
    line_starts: tuple[int, ...]

    @classmethod
    def create(cls, name: str, text: str) -> SourceFile:
        """Create a tracked source file with precomputed line offsets."""
        return cls(name=name, text=text, line_starts=build_line_starts(text))

    def resolve(self, offset: int) -> ResolvedLocation:
        """Resolve a file-local offset into human-readable source coordinates."""
        clamped_offset = min(max(offset, 0), len(self.text))
        effective_offset = clamped_offset

        if clamped_offset == len(self.text):
            # Diagnostics anchored at EOF should point at the last real token
            # line, not at a phantom line after a trailing newline.
            while effective_offset > 0 and self.text[effective_offset - 1] == "\n":
                effective_offset -= 1

        line_index = bisect_right(self.line_starts, effective_offset) - 1
        line_start = self.line_starts[line_index]
        next_line_start = self.line_starts[line_index + 1] if line_index + 1 < len(self.line_starts) else len(self.text)
        line_text = self.text[line_start:next_line_start].rstrip("\n")
        return ResolvedLocation(
            source_name=self.name,
            line=line_index + 1,
            column=(effective_offset - line_start) + 1,
            line_text=line_text,
        )


@dataclass(frozen=True)
class ProgramSource:
    files: tuple[SourceFile, ...]

    @classmethod
    def from_inline(cls, text: str, name: str = "<inline>") -> ProgramSource:
        """Create program source from one inline AWK program string."""
        return cls(files=(SourceFile.create(name, text), ))

    @classmethod
    def from_files(cls, files: list[tuple[str, str]]) -> ProgramSource:
        """Create program source from the ordered set of `-f` inputs."""
        return cls(files=tuple(SourceFile.create(name, text) for name, text in files))

    def point(self, file_index: int, offset: int) -> SourcePoint:
        """Create a source point inside the tracked program."""
        return SourcePoint(file_index=file_index, offset=offset)

    def span(self, start: SourcePoint, end: SourcePoint) -> SourceSpan:
        """Create a span between two points in the same logical program."""
        return SourceSpan(self, start, end)

    def resolve(self, point: SourcePoint) -> ResolvedLocation:
        """Resolve a point to a file name, line, column, and source line text."""
        if not self.files:
            return ResolvedLocation(source_name="<inline>", line=1, column=1, line_text="")

        file_index = min(max(point.file_index, 0), len(self.files) - 1)
        return self.files[file_index].resolve(point.offset)

    def eof_point(self) -> SourcePoint:
        """Return the logical end-of-program point."""
        if not self.files:
            return SourcePoint(file_index=0, offset=0)

        last_index = len(self.files) - 1
        return SourcePoint(file_index=last_index, offset=len(self.files[last_index].text))


@dataclass(frozen=True)
class SourceSpan:
    source: ProgramSource
    start: SourcePoint
    end: SourcePoint

    def start_location(self) -> ResolvedLocation:
        """Resolve the starting position of the span for diagnostics."""
        return self.source.resolve(self.start)

    def format_start(self) -> str:
        """Format the start location as `file:line:column`."""
        location = self.start_location()
        return f"{location.source_name}:{location.line}:{location.column}"


def combine_spans(start: SourceSpan, end: SourceSpan) -> SourceSpan:
    """Create a span from the start of one node to the end of another."""
    if start.source is not end.source:
        raise ValueError("cannot combine spans from different sources")
    return SourceSpan(start.source, start.start, end.end)


class SourceCursor:
    """Iterate through program text while preserving original file boundaries."""

    def __init__(self, source: ProgramSource) -> None:
        """Initialize a cursor positioned at the start of `source`."""
        self.source = source
        self.file_index = 0
        self.offset = 0
        self.at_boundary_newline = False

    def point(self) -> SourcePoint:
        """Return the current point in the logical program stream."""
        self._normalize()
        if self.at_boundary_newline and self.file_index < len(self.source.files):
            return SourcePoint(self.file_index, len(self.source.files[self.file_index].text))
        if self.is_at_end():
            return self.source.eof_point()
        return SourcePoint(self.file_index, self.offset)

    def peek(self, offset: int = 0) -> str | None:
        """Return the current character, or a small lookahead, without consuming it."""
        if offset < 0:
            raise ValueError("peek offset must be non-negative")

        self._normalize()
        if offset == 0:
            if self.is_at_end():
                return None
            if self.at_boundary_newline:
                return "\n"
            return self.source.files[self.file_index].text[self.offset]

        probe = SourceCursor(self.source)
        probe.file_index = self.file_index
        probe.offset = self.offset
        probe.at_boundary_newline = self.at_boundary_newline
        for _ in range(offset):
            if probe.advance() is None:
                return None
        return probe.peek()

    def advance(self) -> str | None:
        """Consume and return the current character, if any."""
        char = self.peek()
        if char is None:
            return None

        if self.at_boundary_newline:
            # Multiple `-f` files behave like one logical program. When a file
            # does not end with a newline, present a synthetic separator before
            # advancing into the next file.
            self.file_index += 1
            self.offset = 0
            self.at_boundary_newline = False
            return char

        self.offset += 1
        return char

    def is_at_end(self) -> bool:
        """Report whether the cursor has consumed the logical program."""
        self._normalize()
        if not self.source.files:
            return True
        if self.at_boundary_newline:
            return False
        last_file = len(self.source.files) - 1
        return self.file_index == last_file and self.offset >= len(self.source.files[last_file].text)

    def _normalize(self) -> None:
        """Advance past exhausted files and expose synthetic file separators."""
        while self.source.files and self.file_index < len(self.source.files):
            if self.at_boundary_newline:
                return

            current_file = self.source.files[self.file_index]
            if self.offset < len(current_file.text):
                return

            if self.file_index + 1 >= len(self.source.files):
                return

            if current_file.text.endswith("\n"):
                self.file_index += 1
                self.offset = 0
                continue

            self.at_boundary_newline = True
            return


SourceText = ProgramSource
