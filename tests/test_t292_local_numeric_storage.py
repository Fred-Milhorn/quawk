from __future__ import annotations

from quawk import jit
from quawk.lexer import lex
from quawk.parser import Program, parse
from quawk.source import ProgramSource

SCALAR_FOLD_LOOP_PROGRAM = (
    "{ n = 4; s = 0; bias = 17; scale = 3; "
    "for (i = 0; i < n; i++) { "
    "base = bias * scale; x = base + i; y = x + 4; z = y - 4; dead = z * 2; "
    "s += z "
    "} "
    "; print s }"
)

BRANCH_REWRITE_LOOP_PROGRAM = (
    "{ n = 4; total = 0; limit = 100; "
    "for (i = 0; i < n; i++) { "
    "left = i * 2; right = left + 10; "
    "if (right > limit) { total += right - limit } else { total += limit - right }; "
    "always = (i - i) + 1; total += always "
    "} "
    "; print total }"
)

FIELD_AGGREGATE_PROGRAM = (
    "{ a = $1 + 0; b = $2 + 0; c = $3 + 0; derived = (b * 3) + c; "
    "if (a < 700) { total += derived; count += 1 } } "
    "END { print total + count }"
)


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def extract_function_body(llvm_ir: str, function_name: str) -> str:
    marker = f"define void @{function_name}(ptr %rt, ptr %state) {{"
    start = llvm_ir.index(marker)
    end = llvm_ir.index("\n}\n", start) + 3
    return llvm_ir[start:end]


def test_t292_scalar_fold_loop_uses_local_numeric_allocas_in_record_phase() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(SCALAR_FOLD_LOOP_PROGRAM))
    record_ir = extract_function_body(llvm_ir, "quawk_record")

    for needle in (
        "%localvar.n.",
        "%localvar.s.",
        "%localvar.bias.",
        "%localvar.scale.",
        "%localvar.i.",
        "%localvar.base.",
        "%localvar.x.",
        "%localvar.y.",
        "%localvar.z.",
        "%localvar.dead.",
    ):
        assert needle in record_ir
    assert "%varptr.n." not in record_ir
    assert "%varptr.dead." not in record_ir


def test_t292_branch_rewrite_loop_uses_local_numeric_allocas_in_record_phase() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(BRANCH_REWRITE_LOOP_PROGRAM))
    record_ir = extract_function_body(llvm_ir, "quawk_record")

    for needle in (
        "%localvar.n.",
        "%localvar.total.",
        "%localvar.limit.",
        "%localvar.i.",
        "%localvar.left.",
        "%localvar.right.",
        "%localvar.always.",
    ):
        assert needle in record_ir
    assert "%varptr.left." not in record_ir
    assert "%varptr.always." not in record_ir


def test_t292_field_aggregate_splits_local_record_scalars_from_state_backed_cross_phase_names() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(FIELD_AGGREGATE_PROGRAM))
    record_ir = extract_function_body(llvm_ir, "quawk_record")
    end_ir = extract_function_body(llvm_ir, "quawk_end")

    for needle in ("%localvar.a.", "%localvar.b.", "%localvar.c.", "%localvar.derived."):
        assert needle in record_ir
    assert "%varptr.a." not in record_ir
    assert "%varptr.derived." not in record_ir
    assert "%varptr.total." in record_ir
    assert "%varptr.count." in record_ir
    assert "%varptr.total." in end_ir
    assert "%varptr.count." in end_ir
    assert "call ptr @qk_get_field_inline(ptr %rt, i64 1)" in record_ir
