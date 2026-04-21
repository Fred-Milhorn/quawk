# Parser/EBNF Coverage Inventory

This inventory is the `T-313` deliverable for `P37`.

It maps the documented grammar in `docs/quawk.ebnf` to the current
parser-focused test surface:

- direct parser tests in `tests/test_parser.py`
- parser goldens in `tests/test_parser_goldens.py`
- file-backed conformance fixtures in `tests/parser_conformance/`

The section labels below are the same names used by
`tests/test_parser_conformance.py`.

## How To Read This Inventory

- `Overall parser evidence` means the current checked-in parser-focused tests
  prove at least one representative form for that grammar area today.
- `Fixture matrix` means the current `tests/parser_conformance/` surface covers
  that grammar area explicitly.
- `partial` means the area has some evidence today, but not enough to claim the
  whole documented surface is directly pinned.

Current result:

- the parser-focused test surface already covers most documented productions
- the conformance fixture matrix still covers only a starter subset
- the remaining work is mostly to widen fixture coverage (`T-314`) and add
  ambiguity-focused direct tests (`T-315`)

## Top-Level Items And Structure

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `program` | covered | covered | all conformance fixtures; `tests/test_parser.py` multi-item and single-item parses | base top-level shape is already pinned |
| `item.function_def` | covered | uncovered | `test_parses_function_definition_and_call`; `tests/parser_goldens/function_surface.awk` | no conformance fixture yet |
| `function_def` | covered | uncovered | direct function-definition test; `function_surface` golden | body/action integration is already covered |
| `function_def.param_list` | covered | uncovered | one-parameter direct test; two-parameter `function_surface` golden | no conformance fixture yet |
| `item.pattern_action` | covered | covered | all conformance fixtures; bare-action and pattern-only direct tests | covered across BEGIN, record, END, and expression forms |
| `pattern.BEGIN` | covered | covered | `begin_*` fixtures; multiple direct tests | — |
| `pattern.END` | covered | covered | `mixed_begin_record_end` fixture; END direct tests | — |
| `pattern.expr` | covered | partial | `test_parses_expression_pattern_without_action`; `regex_filter` fixture | fixture coverage only covers regex-shaped expression patterns today |
| `pattern.expr_regex` | covered | covered | `regex_filter` fixture; regex expression-pattern direct tests | — |
| `pattern.range` | covered | uncovered | `test_parses_range_pattern_and_if_else`; `tests/parser_goldens/range_if_else.awk` | no conformance fixture yet |
| `action` | covered | covered | all action-bearing fixtures; many direct tests | — |
| `stmt_list` | covered | partial | `begin_assignment` and `begin_while_loop` fixtures; many direct tests | fixture coverage covers semicolon-separated statement lists, not newline-heavy forms |
| `sep.statement` | covered | partial | semicolon-separated fixtures; newline-separation direct tests | newline-separated simple statements are not in the fixture matrix yet |

## Statements

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `stmt.block` | covered | covered | `begin_while_loop` fixture; while/do-while direct tests | nested braced statement bodies are pinned |
| `stmt.if` | covered | covered | `begin_if_less` fixture; `range_if_else` direct/golden coverage | — |
| `stmt.while` | covered | covered | `begin_while_loop` fixture; direct tests | — |
| `stmt.do_while` | covered | uncovered | `test_parses_do_while_next_nextfile_and_exit`; `tests/parser_goldens/do_while_next_exit.awk`; newline-before-`while` direct test | no conformance fixture yet |
| `stmt.for` | covered | uncovered | classic `for` direct tests, including comma lists and newline body | no conformance fixture yet |
| `stmt.for_in` | covered | uncovered | direct tests for plain and parenthesized iterables | no conformance fixture yet |
| `stmt.break` | covered | uncovered | `test_parses_break_and_continue_inside_while_block` | no conformance fixture yet |
| `stmt.continue` | covered | uncovered | `test_parses_break_and_continue_inside_while_block` | no conformance fixture yet |
| `stmt.next` | covered | uncovered | `test_parses_do_while_next_nextfile_and_exit`; `do_while_next_exit` golden | no conformance fixture yet |
| `stmt.nextfile` | covered | uncovered | `test_parses_do_while_next_nextfile_and_exit`; `do_while_next_exit` golden | no conformance fixture yet |
| `stmt.exit` | covered | uncovered | `test_parses_do_while_next_nextfile_and_exit`; `do_while_next_exit` golden | no conformance fixture yet |
| `stmt.return` | covered | uncovered | `test_parses_function_definition_and_call`; `function_surface` golden | no conformance fixture yet |
| `stmt.delete` | partial | uncovered | `test_parses_delete_statement`; `test_parses_dynamic_fields_multi_subscripts_and_delete_name`; `tests/parser_goldens/fields_arrays.awk` | the EBNF currently suggests an extra optional bracket tail that the parser does not parse separately |
| `stmt.assignment` | covered | covered | `begin_assignment` and `begin_while_loop` fixtures; many direct tests | fixture coverage does not yet include compound assignment |
| `stmt.print` | covered | covered | multiple fixtures and direct tests | — |
| `stmt.printf` | covered | uncovered | `test_parses_printf_expr_stmt_and_assignment_forms`; `test_parses_parenthesized_printf_with_substr_argument`; `tests/parser_goldens/printf_assign_forms.awk` | no conformance fixture yet |
| `stmt.expr` | covered | uncovered | direct tests for `getline`, `close(...)`, prefix increment, and postfix increment | no conformance fixture yet |

## Lists, LValues, And Expression Surface

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `expr_list` | covered | uncovered | direct tests for `for` init/update lists and `printf` argument lists | conformance fixtures only use single-expression lists today |
| `output_redirect` | covered | uncovered | `test_parses_print_and_printf_output_redirects` | all three redirect kinds are covered directly, but not in fixtures |
| `subscript_list` | covered | uncovered | `test_parses_dynamic_fields_multi_subscripts_and_delete_name`; `fields_arrays` golden | no conformance fixture yet |
| `lvalue.name` | covered | covered | assignment fixtures; many direct tests | — |
| `lvalue.array` | covered | uncovered | array assignment/read direct tests; `fields_arrays` golden | no conformance fixture yet |
| `lvalue.field` | covered | uncovered | dynamic field assignment direct test | no conformance fixture yet |
| `expr.number` | covered | covered | multiple fixtures and direct tests | — |
| `expr.string` | covered | covered | `begin_print_literal` and `mixed_begin_record_end` fixtures; direct tests | — |
| `expr.regex` | covered | partial | regex literal direct tests; `regex_filter` fixture | fixture coverage only covers regex literals in pattern position |
| `expr.name` | covered | covered | assignment and while fixtures; direct tests | — |
| `expr.field` | covered | covered | `mixed_begin_record_end` and `regex_filter` fixtures; direct tests | — |
| `expr.call` | covered | uncovered | function-call direct tests; `function_surface` golden; builtin-call direct tests | no conformance fixture yet |
| `expr.grouped` | covered | covered | `begin_boolean_expr` fixture; direct tests | — |
| `expr.assign` | covered | uncovered | `print (x = 1)` direct test; `printf_assign_forms` golden | no conformance fixture yet |
| `expr.conditional` | covered | uncovered | `test_parses_remaining_expression_families`; `function_surface` golden | no conformance fixture yet |
| `expr.logical_or` | covered | uncovered | `test_parses_remaining_expression_families` | no conformance fixture yet |
| `expr.logical_and` | covered | covered | `begin_boolean_expr` fixture; direct tests | — |
| `expr.less` | covered | covered | `begin_if_less`, `begin_while_loop`, and `begin_boolean_expr` fixtures; direct tests | — |
| `expr.compare_other` | covered | uncovered | `test_parses_remaining_expression_families` covers `<=`, `>`, `>=`, and `!=` | no conformance fixture yet |
| `expr.equal` | covered | covered | `begin_boolean_expr` fixture; direct test | — |
| `expr.match` | covered | uncovered | `test_parses_remaining_expression_families` | no conformance fixture yet |
| `expr.in` | covered | uncovered | `test_parses_remaining_expression_families`; `for ... in` direct tests | no conformance fixture yet |
| `expr.concat` | partial | uncovered | `test_parses_remaining_expression_families` parses a simple adjacency case | still needs broader ambiguity coverage |
| `expr.add` | covered | covered | assignment and while fixtures; direct tests | — |
| `expr.mul` | covered | uncovered | `test_parses_remaining_expression_families` | no conformance fixture yet |
| `expr.pow` | covered | uncovered | `test_parses_remaining_expression_families` | no conformance fixture yet |
| `expr.unary` | covered | uncovered | `test_parses_remaining_expression_families` | no conformance fixture yet |
| `expr.postfix` | covered | uncovered | classic `for` direct tests; `test_parses_remaining_expression_families` | no conformance fixture yet |

## Disambiguation Rules

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `disambiguation.concat` | partial | uncovered | direct concat coverage in `test_parses_remaining_expression_families` | adjacency/blocker boundaries still need targeted direct tests |
| `disambiguation.regex_vs_division` | partial | uncovered | direct tests cover both regex literals and `/` as division, but not an ambiguity-focused pair | needs targeted direct coverage in `T-315` |

## Documented Grammar Vs Current Parser Divergences

These notes are intentionally separate from the labeled inventory above because
they are not clean one-to-one EBNF sections today.

1. `getline` is parser-admitted as a special expression form, but
   `docs/quawk.ebnf` does not currently model it with a dedicated production.
   Current evidence: `test_parses_getline_into_named_target_with_file_source`
   and `test_format_program_includes_getline_expression_shape`.
2. Bare `length` is parser-admitted as a zero-argument builtin call without
   parentheses, but the documented `func_call` production currently requires
   `IDENT "(" arg_list? ")"`.
   Current evidence: `test_parses_bare_length_as_zero_argument_builtin_call`.
3. The documented `delete` production currently implies an extra optional
   bracketed subscript tail after `lvalue`, while the parser only accepts the
   ordinary lvalue forms it already knows how to parse.

Those divergences belong to `T-316` after fixture and direct-test coverage are
expanded enough to make the parser-facing contract decision explicit.
