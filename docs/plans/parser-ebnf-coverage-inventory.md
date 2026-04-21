# Parser/EBNF Coverage Inventory

This inventory is the `T-313` deliverable for `P37`.

It maps the documented grammar in `docs/quawk.ebnf` to the current
parser-focused test surface:

- direct parser tests in `tests/test_parser.py`
- parser goldens in `tests/test_parser_goldens.py`
- file-backed conformance fixtures in `tests/conformance/`

The section labels below are the same names used by
`tests/test_parser_conformance.py`.

## How To Read This Inventory

- `Overall parser evidence` means the current checked-in parser-focused tests
  prove at least one representative form for that grammar area today.
- `Fixture matrix` means the current `tests/conformance/` surface covers
  that grammar area explicitly.
- `partial` means the area has some evidence today, but not enough to claim the
  whole documented surface is directly pinned.

Current result:

- the parser-focused test surface already covers most documented productions
- the conformance fixture matrix now covers every labeled documented grammar
  section used by `tests/test_parser_conformance.py`
- the remaining work is now concentrated in parser-vs-doc sync decisions
  (`T-316`) and final closeout validation (`T-317`)

## Top-Level Items And Structure

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `program` | covered | covered | all conformance fixtures; `tests/test_parser.py` multi-item and single-item parses | base top-level shape is already pinned |
| `item.function_def` | covered | covered | `tests/conformance/function_surface.awk`; direct and golden function coverage | — |
| `function_def` | covered | covered | `tests/conformance/function_surface.awk`; direct function-definition test; `function_surface` golden | body/action integration is already covered |
| `function_def.param_list` | covered | covered | `tests/conformance/function_surface.awk`; direct and golden function coverage | — |
| `item.pattern_action` | covered | covered | all conformance fixtures; bare-action and pattern-only direct tests | covered across BEGIN, record, END, and expression forms |
| `pattern.BEGIN` | covered | covered | `begin_*` fixtures; multiple direct tests | — |
| `pattern.END` | covered | covered | `mixed_begin_record_end` fixture; END direct tests | — |
| `pattern.expr` | covered | covered | `tests/conformance/expression_pattern.awk`; `regex_filter` fixture; direct expression-pattern test | — |
| `pattern.expr_regex` | covered | covered | `regex_filter` fixture; regex expression-pattern direct tests | — |
| `pattern.range` | covered | covered | `tests/conformance/range_for_loops.awk`; direct and golden range-pattern coverage | — |
| `action` | covered | covered | all action-bearing fixtures; many direct tests | — |
| `stmt_list` | covered | covered | multi-statement conformance fixtures now cover both semicolon and newline-separated lists | — |
| `sep.statement` | covered | covered | conformance fixtures now include semicolon and NEWLINE-separated statement boundaries | — |

## Statements

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `stmt.block` | covered | covered | `begin_while_loop` fixture; while/do-while direct tests | nested braced statement bodies are pinned |
| `stmt.if` | covered | covered | `begin_if_less` fixture; `range_if_else` direct/golden coverage | — |
| `stmt.while` | covered | covered | `begin_while_loop` fixture; direct tests | — |
| `stmt.do_while` | covered | covered | `tests/conformance/control_flow_terms.awk`; direct and golden do-while coverage | — |
| `stmt.for` | covered | covered | `tests/conformance/range_for_loops.awk`; classic `for` direct tests | — |
| `stmt.for_in` | covered | covered | `tests/conformance/range_for_loops.awk`; direct `for ... in` tests | — |
| `stmt.break` | covered | covered | `tests/conformance/control_flow_terms.awk`; direct break/continue test | — |
| `stmt.continue` | covered | covered | `tests/conformance/control_flow_terms.awk`; direct break/continue test | — |
| `stmt.next` | covered | covered | `tests/conformance/control_flow_terms.awk`; direct and golden `next` coverage | — |
| `stmt.nextfile` | covered | covered | `tests/conformance/control_flow_terms.awk`; direct and golden `nextfile` coverage | — |
| `stmt.exit` | covered | covered | `tests/conformance/control_flow_terms.awk`; direct and golden exit coverage | — |
| `stmt.return` | covered | covered | `tests/conformance/function_surface.awk`; direct and golden return coverage | — |
| `stmt.delete` | partial | covered | `tests/conformance/fields_delete.awk`; direct delete-target tests; `fields_arrays` golden | the EBNF currently suggests an extra optional bracket tail that the parser does not parse separately |
| `stmt.assignment` | covered | covered | `begin_assignment` and `begin_while_loop` fixtures; many direct tests | fixture coverage does not yet include compound assignment |
| `stmt.print` | covered | covered | multiple fixtures and direct tests | — |
| `stmt.printf` | covered | covered | `tests/conformance/printf_redirect_call.awk`; direct and golden printf coverage | — |
| `stmt.expr` | covered | covered | `tests/conformance/printf_redirect_call.awk` and `expression_surface.awk`; direct expression-statement coverage | — |

## Lists, LValues, And Expression Surface

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `expr_list` | covered | covered | conformance fixtures now cover print/printf lists and classic `for` init/update lists | — |
| `output_redirect` | covered | covered | `tests/conformance/printf_redirect_call.awk`; direct redirect tests | all three redirect kinds are now in the fixture matrix |
| `subscript_list` | covered | covered | `tests/conformance/fields_delete.awk`; direct tests; `fields_arrays` golden | — |
| `lvalue.name` | covered | covered | assignment fixtures; many direct tests | — |
| `lvalue.array` | covered | covered | `tests/conformance/fields_delete.awk`; direct tests; `fields_arrays` golden | — |
| `lvalue.field` | covered | covered | `tests/conformance/fields_delete.awk`; dynamic field assignment direct test | — |
| `expr.number` | covered | covered | multiple fixtures and direct tests | — |
| `expr.string` | covered | covered | `begin_print_literal` and `mixed_begin_record_end` fixtures; direct tests | — |
| `expr.regex` | covered | covered | `tests/conformance/expression_surface.awk`; `regex_filter` fixture; direct regex tests | — |
| `expr.name` | covered | covered | assignment and while fixtures; direct tests | — |
| `expr.field` | covered | covered | `mixed_begin_record_end` and `regex_filter` fixtures; direct tests | — |
| `expr.call` | covered | covered | `tests/conformance/function_surface.awk` and `printf_redirect_call.awk`; direct and golden call coverage | — |
| `expr.grouped` | covered | covered | `begin_boolean_expr` fixture; direct tests | — |
| `expr.assign` | covered | covered | `tests/conformance/range_for_loops.awk`; direct assignment-expression tests; `printf_assign_forms` golden | — |
| `expr.conditional` | covered | covered | `tests/conformance/function_surface.awk` and `expression_surface.awk`; direct and golden conditional coverage | — |
| `expr.logical_or` | covered | covered | `tests/conformance/expression_surface.awk`; direct logical-or test | — |
| `expr.logical_and` | covered | covered | `begin_boolean_expr` fixture; direct tests | — |
| `expr.less` | covered | covered | `begin_if_less`, `begin_while_loop`, and `begin_boolean_expr` fixtures; direct tests | — |
| `expr.compare_other` | covered | covered | `tests/conformance/expression_surface.awk` and `range_for_loops.awk`; direct comparison-family test | — |
| `expr.equal` | covered | covered | `begin_boolean_expr` fixture; direct test | — |
| `expr.match` | covered | covered | `tests/conformance/expression_surface.awk`; direct match/not-match test | — |
| `expr.in` | covered | covered | `tests/conformance/expression_surface.awk`; direct membership and `for ... in` tests | — |
| `expr.concat` | covered | covered | `tests/conformance/expression_surface.awk`; direct concat-boundary tests in `tests/test_parser.py` | — |
| `expr.add` | covered | covered | assignment and while fixtures; direct tests | — |
| `expr.mul` | covered | covered | `tests/conformance/expression_surface.awk`; direct arithmetic-family test | — |
| `expr.pow` | covered | covered | `tests/conformance/expression_surface.awk`; direct arithmetic-family test | — |
| `expr.unary` | covered | covered | `tests/conformance/expression_surface.awk` and `range_for_loops.awk`; direct unary tests | — |
| `expr.postfix` | covered | covered | `tests/conformance/expression_surface.awk` and `range_for_loops.awk`; direct postfix tests | — |

## Disambiguation Rules

| Section | Overall parser evidence | Fixture matrix | Current evidence | Notes |
|---|---|---|---|---|
| `disambiguation.concat` | covered | covered | `tests/conformance/expression_surface.awk`; targeted concat-boundary tests in `tests/test_parser.py` | — |
| `disambiguation.regex_vs_division` | covered | covered | `tests/conformance/expression_surface.awk`; targeted regex-vs-division tests in `tests/test_parser.py` | — |

## Documented Grammar Vs Current Parser Divergences

These notes are intentionally separate from the labeled inventory above because
they are not clean one-to-one EBNF sections today.

1. `getline` is parser-admitted as a special expression form, but
   `docs/quawk.ebnf` does not currently model it with a dedicated production.
   Current evidence: `test_parses_getline_into_named_target_with_file_source`,
   `test_parses_getline_target_only_variants`, and
   `test_format_program_includes_getline_expression_shape`.
2. Bare `length` is parser-admitted as a zero-argument builtin call without
   parentheses, but the documented `func_call` production currently requires
   `IDENT "(" arg_list? ")"`.
   Current evidence: `test_parses_bare_length_as_zero_argument_builtin_call`.
3. The documented `delete` production currently implies an extra optional
   bracketed subscript tail after `lvalue`, while the parser only accepts the
   ordinary lvalue forms it already knows how to parse.

Those divergences belong to `T-316` after fixture and direct-test coverage are
expanded enough to make the parser-facing contract decision explicit.
