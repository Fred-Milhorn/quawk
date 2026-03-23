# Host-runtime tests for mixed-program execution.
# These cases exercise the interpreter path directly so P3 sequencing changes
# are pinned below the CLI layer.

from __future__ import annotations

import io

from quawk.jit import execute_with_inputs
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource


def parse_program(source_text: str) -> Program:
    """Parse inline AWK source into the frontend program model."""
    return parse(lex(ProgramSource.from_inline(source_text)))


def test_execute_with_inputs_sequences_begin_record_and_end(capsys, monkeypatch) -> None:
    program = parse_program('BEGIN { print "start" }\n{ print $1 }\nEND { print "done" }')

    monkeypatch.setattr("sys.stdin", io.StringIO("alpha beta\ngamma delta\n"))

    assert execute_with_inputs(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "start\nalpha\ngamma\ndone\n"
    assert captured.err == ""


def test_execute_with_inputs_runs_begin_and_end_without_input(capsys) -> None:
    program = parse_program('BEGIN { x = 1 + 2; print x }\nEND { print "done" }')

    assert execute_with_inputs(program, [], None) == 0
    captured = capsys.readouterr()
    assert captured.out == "3\ndone\n"
    assert captured.err == ""
