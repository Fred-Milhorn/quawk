from __future__ import annotations

from pathlib import Path

from quawk import jit
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource

ROOT = Path(__file__).resolve().parent.parent


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def current_public_route(program: Program, initial_variables: jit.InitialVariables | None = None) -> str:
    string_initial_variables = jit.initial_variables_require_string_runtime(initial_variables)
    if jit.requires_host_runtime_execution(program):
        return "rejected"
    if (
        (
            jit.requires_host_runtime_value_execution(program)
            and not string_initial_variables
            and not jit.supports_claimed_value_runtime_subset(program)
        )
        or (string_initial_variables and jit.has_function_definitions(program))
    ):
        return "host"
    return "backend"


def test_t203_matrix_records_the_representative_claimed_value_fallback_rows() -> None:
    matrix_text = (ROOT / "docs" / "plans" / "claimed-value-fallback-matrix.md").read_text(encoding="utf-8")

    assert "# Claimed Value-Fallback Matrix" in matrix_text
    assert "| Unset scalar string-context read | `BEGIN { print x }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes |" in matrix_text
    assert "| Unset scalar propagation through assignment | `BEGIN { y = x; print y }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes |" in matrix_text
    assert "| Mixed unset-scalar string and numeric views | `BEGIN { print x; print x + 1 }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes |" in matrix_text
    assert "| Plain scalar-name read after assignment | `BEGIN { x = 1; print x }` | none | yes | no | `supports_claimed_value_runtime_subset(program) == True` keeps public execution on the backend/runtime path | yes |" in matrix_text
    assert '| String `-v` plus user-defined functions | `function f(y) { return y + 1 } BEGIN { print x; print f(1) }` | `-v x=hello` | yes | yes | `initial_variables_require_string_runtime(initial_variables) == True` and `has_function_definitions(program) == True` | no |' in matrix_text
    assert "`-v x=hello 'BEGIN { print x }'` is not part of this remaining matrix" in matrix_text


def test_t203_inventory_rows_match_the_current_value_fallback_boundary() -> None:
    unset_print = parse_program("BEGIN { print x }")
    unset_assignment = parse_program("BEGIN { y = x; print y }")
    mixed_views = parse_program("BEGIN { print x; print x + 1 }")
    assigned_print = parse_program("BEGIN { x = 1; print x }")
    string_v_with_function = parse_program("function f(y) { return y + 1 }\nBEGIN { print x; print f(1) }")
    string_v_without_function = parse_program("BEGIN { print x }")

    assert jit.requires_host_runtime_value_execution(unset_print) is True
    assert jit.requires_host_runtime_value_execution(unset_assignment) is True
    assert jit.requires_host_runtime_value_execution(mixed_views) is True
    assert jit.requires_host_runtime_value_execution(assigned_print) is True
    assert jit.supports_claimed_value_runtime_subset(unset_print) is True
    assert jit.supports_claimed_value_runtime_subset(unset_assignment) is True
    assert jit.supports_claimed_value_runtime_subset(mixed_views) is True
    assert jit.supports_claimed_value_runtime_subset(assigned_print) is True

    assert current_public_route(unset_print) == "backend"
    assert current_public_route(unset_assignment) == "backend"
    assert current_public_route(mixed_views) == "backend"
    assert current_public_route(assigned_print) == "backend"

    assert jit.requires_host_runtime_value_execution(string_v_with_function) is False
    assert jit.supports_claimed_value_runtime_subset(string_v_with_function) is False
    assert current_public_route(string_v_with_function, [("x", "hello")]) == "host"

    assert jit.requires_host_runtime_value_execution(string_v_without_function) is True
    assert jit.supports_claimed_value_runtime_subset(string_v_without_function) is True
    assert current_public_route(string_v_without_function, [("x", "hello")]) == "backend"
