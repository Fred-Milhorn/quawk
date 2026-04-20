"""Behavior-oriented coverage for local scalar mem2reg optimization (from T-293)."""

from __future__ import annotations

from quawk import jit
from quawk.ast import Program
from quawk.lexer import lex
from quawk.parser import parse
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


def parse_program(source_text: str) -> Program:
    return parse(lex(ProgramSource.from_inline(source_text)))


def extract_function_body(llvm_ir: str, function_name: str) -> str:
    marker = f"define void @{function_name}(ptr %rt, ptr %state) {{"
    start = llvm_ir.index(marker)
    end = llvm_ir.index("\n}\n", start) + 3
    return llvm_ir[start:end]


def test_t293_scalar_fold_loop_moves_promoted_zero_initialization_to_entry() -> None:
    llvm_ir = jit.lower_to_llvm_ir(parse_program(SCALAR_FOLD_LOOP_PROGRAM))
    record_ir = extract_function_body(llvm_ir, "quawk_record")

    loop_start = record_ir.index("for.cond.")
    entry_ir = record_ir[:loop_start]
    loop_body_ir = record_ir[loop_start:]

    for name in ("base", "x", "y", "z", "dead"):
        zero_store = f"store double 0.000000000000000e+00, ptr %localvar.{name}."
        assert zero_store in entry_ir
        assert zero_store not in loop_body_ir


def test_t293_scalar_fold_loop_optimized_record_ir_collapses_promoted_temps() -> None:
    llvm_ir = jit.optimize_ir(jit.lower_to_llvm_ir(parse_program(SCALAR_FOLD_LOOP_PROGRAM)))
    record_ir = extract_function_body(llvm_ir, "quawk_record")

    assert "alloca double" not in record_ir
    assert "store double" not in record_ir
    assert "load double, ptr %localvar." not in record_ir
    assert "%localvar.i." in record_ir
    assert "%localvar.s." in record_ir
    assert "= phi double" in record_ir
    for name in ("base", "x", "y", "z", "dead"):
        assert f"%localvar.{name}." not in record_ir


def test_t293_branch_rewrite_loop_optimized_record_ir_rewrites_promoted_temps_to_ssa() -> None:
    llvm_ir = jit.optimize_ir(jit.lower_to_llvm_ir(parse_program(BRANCH_REWRITE_LOOP_PROGRAM)))
    record_ir = extract_function_body(llvm_ir, "quawk_record")

    assert "alloca double" not in record_ir
    assert "store double" not in record_ir
    assert "load double, ptr %localvar." not in record_ir
    assert "%localvar.i." in record_ir
    assert "%localvar.total." in record_ir
    assert "= phi double" in record_ir
    assert "select i1" in record_ir
    for name in ("left", "right", "always"):
        assert f"%localvar.{name}." not in record_ir
