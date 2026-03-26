# Grammar Conformance Checklist

This checklist captures the remaining grammar, design, and AST drift that is
tracked by `P10` and `T-122` through `T-126`.

## Remaining Gaps

No remaining `T-122` through `T-126` gaps are tracked here.

## Existing Coverage That Already Helps

- parser conformance matrix: [test_parser_conformance.py](/Users/fred/dev/quawk/tests/test_parser_conformance.py)
- parser AST goldens: [test_parser_goldens.py](/Users/fred/dev/quawk/tests/test_parser_goldens.py)
- semantic diagnostic baselines: [test_p5_functions_semantics.py](/Users/fred/dev/quawk/tests/test_p5_functions_semantics.py)
- POSIX-core frontend baselines: [test_p7_posix_core_frontend.py](/Users/fred/dev/quawk/tests/test_p7_posix_core_frontend.py)
- runtime/builtin coverage: [test_p8_runtime_baselines.py](/Users/fred/dev/quawk/tests/test_p8_runtime_baselines.py)

## Exit Signal For This Checklist

This checklist is now effectively retired:

- the `T-122` xfail baselines are burned down
- the AST docs now separate current and future shapes
