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


def test_t290_scalar_fold_loop_baseline_keeps_loop_temporaries_in_quawk_state() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(SCALAR_FOLD_LOOP_PROGRAM))

    for needle in (
        "%varptr.n.",
        "%varptr.s.",
        "%varptr.bias.",
        "%varptr.scale.",
        "%varptr.i.",
        "%varptr.base.",
        "%varptr.x.",
        "%varptr.y.",
        "%varptr.z.",
        "%varptr.dead.",
    ):
        assert needle in llvm_ir
    assert llvm_ir.count("getelementptr inbounds %quawk.state, ptr %state") >= 10


def test_t290_branch_rewrite_loop_baseline_keeps_branch_locals_in_quawk_state() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(BRANCH_REWRITE_LOOP_PROGRAM))

    for needle in (
        "%varptr.n.",
        "%varptr.total.",
        "%varptr.limit.",
        "%varptr.i.",
        "%varptr.left.",
        "%varptr.right.",
        "%varptr.always.",
    ):
        assert needle in llvm_ir
    assert llvm_ir.count("getelementptr inbounds %quawk.state, ptr %state") >= 7


def test_t290_field_aggregate_baseline_stays_runtime_shaped_and_state_backed() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(FIELD_AGGREGATE_PROGRAM))

    for needle in (
        "%varptr.a.",
        "%varptr.b.",
        "%varptr.c.",
        "%varptr.derived.",
        "%varptr.total.",
        "%varptr.count.",
    ):
        assert needle in llvm_ir
    assert "call ptr @qk_get_field_inline(ptr %rt, i64 1)" in llvm_ir
    assert "call ptr @qk_get_field_inline(ptr %rt, i64 2)" in llvm_ir
    assert "call ptr @qk_get_field_inline(ptr %rt, i64 3)" in llvm_ir
