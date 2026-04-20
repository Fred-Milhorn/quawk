from __future__ import annotations

from quawk import jit
from quawk.lexer import lex
from quawk.parser import parse
from quawk.source import ProgramSource


def parse_program(source_text: str):
    return parse(lex(ProgramSource.from_inline(source_text)))


DYNAMIC_PRINTF_PROGRAM = 'BEGIN { fmt = "%d %d\\n"; printf fmt, 1, 2 }'


def test_t270_representative_dynamic_printf_program_executes_through_public_execution() -> None:
    program = parse_program(DYNAMIC_PRINTF_PROGRAM)

    assert jit.execute(program) == 0
    assert jit.lower_to_llvm_ir(program)
