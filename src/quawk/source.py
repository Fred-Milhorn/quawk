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
class SourceChunk:
    name: str
    text: str
    start_offset: int
    line_starts: tuple[int, ...]

    @classmethod
    def create(cls, name: str, text: str, start_offset: int) -> SourceChunk:
        return cls(
            name=name,
            text=text,
            start_offset=start_offset,
            line_starts=build_line_starts(text),
        )

    @property
    def end_offset(self) -> int:
        return self.start_offset + len(self.text)

    def resolve(self, offset: int) -> ResolvedLocation:
        local_offset = min(max(offset - self.start_offset, 0), len(self.text))
        effective_offset = local_offset
        if local_offset == len(self.text):
            while effective_offset > 0 and self.text[effective_offset - 1] == "\n":
                effective_offset -= 1

        line_index = bisect_right(self.line_starts, effective_offset) - 1
        line_start = self.line_starts[line_index]
        next_line_start = (
            self.line_starts[line_index + 1] if line_index + 1 < len(self.line_starts) else len(self.text)
        )
        line_text = self.text[line_start:next_line_start].rstrip("\n")
        return ResolvedLocation(
            source_name=self.name,
            line=line_index + 1,
            column=(effective_offset - line_start) + 1,
            line_text=line_text,
        )


@dataclass(frozen=True)
class SourceText:
    text: str
    chunks: tuple[SourceChunk, ...]

    @classmethod
    def from_inline(cls, text: str, name: str = "<inline>") -> SourceText:
        return cls(text=text, chunks=(SourceChunk.create(name, text, 0), ))

    @classmethod
    def from_files(cls, files: list[tuple[str, str]]) -> SourceText:
        parts: list[str] = []
        chunks: list[SourceChunk] = []
        offset = 0

        for index, (name, text) in enumerate(files):
            parts.append(text)
            chunks.append(SourceChunk.create(name, text, offset))
            offset += len(text)
            if index + 1 < len(files):
                separator = "\n"
                parts.append(separator)
                chunks.append(SourceChunk.create(name, separator, offset))
                offset += len(separator)

        return cls(text="".join(parts), chunks=tuple(chunks))

    def span(self, start_offset: int, end_offset: int) -> SourceSpan:
        return SourceSpan(self, start_offset, end_offset)

    def resolve(self, offset: int) -> ResolvedLocation:
        if not self.chunks:
            return ResolvedLocation("<inline>", 1, 1, "")

        clamped_offset = min(max(offset, 0), len(self.text))
        chunk_index = bisect_right([chunk.start_offset for chunk in self.chunks], clamped_offset) - 1
        chunk = self.chunks[max(chunk_index, 0)]
        while clamped_offset > chunk.end_offset and chunk_index + 1 < len(self.chunks):
            chunk_index += 1
            chunk = self.chunks[chunk_index]
        return chunk.resolve(clamped_offset)


@dataclass(frozen=True)
class SourceSpan:
    source: SourceText
    start_offset: int
    end_offset: int

    def start(self) -> ResolvedLocation:
        return self.source.resolve(self.start_offset)

    def format_start(self) -> str:
        location = self.start()
        return f"{location.source_name}:{location.line}:{location.column}"


def combine_spans(start: SourceSpan, end: SourceSpan) -> SourceSpan:
    if start.source is not end.source:
        raise ValueError("cannot combine spans from different sources")
    return SourceSpan(start.source, start.start_offset, end.end_offset)
