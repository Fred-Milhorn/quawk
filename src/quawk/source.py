from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


def build_line_starts(text: str) -> tuple[int, ...]:
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
        return cls(name=name, text=text, line_starts=build_line_starts(text))

    def resolve(self, offset: int) -> ResolvedLocation:
        clamped_offset = min(max(offset, 0), len(self.text))
        effective_offset = clamped_offset

        if clamped_offset == len(self.text):
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
        return cls(files=(SourceFile.create(name, text), ))

    @classmethod
    def from_files(cls, files: list[tuple[str, str]]) -> ProgramSource:
        return cls(files=tuple(SourceFile.create(name, text) for name, text in files))

    def point(self, file_index: int, offset: int) -> SourcePoint:
        return SourcePoint(file_index=file_index, offset=offset)

    def span(self, start: SourcePoint, end: SourcePoint) -> SourceSpan:
        return SourceSpan(self, start, end)

    def resolve(self, point: SourcePoint) -> ResolvedLocation:
        if not self.files:
            return ResolvedLocation(source_name="<inline>", line=1, column=1, line_text="")

        file_index = min(max(point.file_index, 0), len(self.files) - 1)
        return self.files[file_index].resolve(point.offset)

    def eof_point(self) -> SourcePoint:
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
        return self.source.resolve(self.start)

    def format_start(self) -> str:
        location = self.start_location()
        return f"{location.source_name}:{location.line}:{location.column}"


def combine_spans(start: SourceSpan, end: SourceSpan) -> SourceSpan:
    if start.source is not end.source:
        raise ValueError("cannot combine spans from different sources")
    return SourceSpan(start.source, start.start, end.end)


class SourceCursor:

    def __init__(self, source: ProgramSource) -> None:
        self.source = source
        self.file_index = 0
        self.offset = 0
        self.at_boundary_newline = False

    def point(self) -> SourcePoint:
        self._normalize()
        if self.at_boundary_newline and self.file_index < len(self.source.files):
            return SourcePoint(self.file_index, len(self.source.files[self.file_index].text))
        if self.is_at_end():
            return self.source.eof_point()
        return SourcePoint(self.file_index, self.offset)

    def peek(self) -> str | None:
        self._normalize()
        if self.is_at_end():
            return None
        if self.at_boundary_newline:
            return "\n"
        return self.source.files[self.file_index].text[self.offset]

    def advance(self) -> str | None:
        char = self.peek()
        if char is None:
            return None

        if self.at_boundary_newline:
            self.file_index += 1
            self.offset = 0
            self.at_boundary_newline = False
            return char

        self.offset += 1
        return char

    def is_at_end(self) -> bool:
        self._normalize()
        if not self.source.files:
            return True
        if self.at_boundary_newline:
            return False
        last_file = len(self.source.files) - 1
        return self.file_index == last_file and self.offset >= len(self.source.files[last_file].text)

    def _normalize(self) -> None:
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
