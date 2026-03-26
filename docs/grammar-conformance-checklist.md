# Grammar Conformance Checklist

This checklist captures the remaining grammar, design, and AST drift that is
tracked by `P10` and `T-122` through `T-126`.

## Remaining Gaps

| Area | Doc Source | Current Drift | Baseline | Next Task |
|---|---|---|---|---|
| Classic `for` init/update accept `expr_list` | [grammar.ebnf](/Users/fred/dev/quawk/docs/grammar.ebnf) | Parser narrows init/update to assignment statements only | [test_p10_grammar_alignment.py](/Users/fred/dev/quawk/tests/test_p10_grammar_alignment.py) | `T-123`, `T-124` |
| `for (IDENT in expr)` accepts a general iterable expression | [grammar.ebnf](/Users/fred/dev/quawk/docs/grammar.ebnf) | Parser/runtime narrow the iterable to a bare array name | [test_p10_grammar_alignment.py](/Users/fred/dev/quawk/tests/test_p10_grammar_alignment.py) | `T-123`, `T-124` |
| Current execution model description matches shipped behavior | [design.md](/Users/fred/dev/quawk/docs/design.md) | Current-state prose still understates the implemented feature surface and backend split | [grammar-alignment.md](/Users/fred/dev/quawk/docs/grammar-alignment.md) | `T-125` |
| Current parser AST vs future normalized AST are clearly distinguished | [quawk.asdl](/Users/fred/dev/quawk/docs/quawk.asdl) | The documented AST role is still broader and differently shaped than the implemented parser tree | [grammar-alignment.md](/Users/fred/dev/quawk/docs/grammar-alignment.md) | `T-126` |

## Existing Coverage That Already Helps

- parser conformance matrix: [test_parser_conformance.py](/Users/fred/dev/quawk/tests/test_parser_conformance.py)
- parser AST goldens: [test_parser_goldens.py](/Users/fred/dev/quawk/tests/test_parser_goldens.py)
- semantic diagnostic baselines: [test_p5_functions_semantics.py](/Users/fred/dev/quawk/tests/test_p5_functions_semantics.py)
- POSIX-core frontend baselines: [test_p7_posix_core_frontend.py](/Users/fred/dev/quawk/tests/test_p7_posix_core_frontend.py)
- runtime/builtin coverage: [test_p8_runtime_baselines.py](/Users/fred/dev/quawk/tests/test_p8_runtime_baselines.py)

## Exit Signal For This Checklist

This checklist can be retired or collapsed into broader docs when:

- the `T-122` xfail baselines are burned down
- `design.md` describes the current implementation honestly
- the AST docs clearly separate current and future shapes
