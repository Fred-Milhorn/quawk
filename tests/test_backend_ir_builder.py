from __future__ import annotations

from quawk.backend.ir_builder import LLVMIRBuilder
from quawk.backend.state import LoweringState


def test_ir_builder_emits_control_flow_blocks_with_phi() -> None:
    state = LoweringState()
    builder = LLVMIRBuilder(state)

    true_label = builder.label("cond.true")
    false_label = builder.label("cond.false")
    end_label = builder.label("cond.end")

    builder.cond_branch("%flag", true_label, false_label)
    builder.mark_label(true_label)
    true_value = builder.binop("sum", "fadd", "double", "1.0", "2.0")
    builder.branch(end_label)
    builder.mark_label(false_label)
    false_value = builder.binop("diff", "fsub", "double", "5.0", "3.0")
    builder.branch(end_label)
    builder.mark_label(end_label)
    result = builder.phi("result", "double", [(true_value, true_label), (false_value, false_label)])

    assert result == "%result.2"
    assert state.instructions == [
        "  br i1 %flag, label %cond.true.0, label %cond.false.1",
        "cond.true.0:",
        "  %sum.0 = fadd double 1.0, 2.0",
        "  br label %cond.end.2",
        "cond.false.1:",
        "  %diff.1 = fsub double 5.0, 3.0",
        "  br label %cond.end.2",
        "cond.end.2:",
        "  %result.2 = phi double [ %sum.0, %cond.true.0 ], [ %diff.1, %cond.false.1 ]",
    ]


def test_ir_builder_wraps_calls_and_selects() -> None:
    state = LoweringState()
    builder = LLVMIRBuilder(state)

    call_value = builder.call("num", "double", "@qk_parse_number_text", ["ptr %text"])
    selected = builder.select("pick", "%cond", "double", call_value, "0.0")
    builder.call_void("@llvm.lifetime.end.p0", ["i64 8", "ptr %slot"])

    assert selected == "%pick.1"
    assert state.instructions == [
        "  %num.0 = call double @qk_parse_number_text(ptr %text)",
        "  %pick.1 = select i1 %cond, double %num.0, double 0.0",
        "  call void @llvm.lifetime.end.p0(i64 8, ptr %slot)",
    ]


def test_ir_builder_gep_helpers_match_runtime_abi_rendering() -> None:
    state = LoweringState()
    builder = LLVMIRBuilder(state)

    ptr_value = builder.gep("strptr", 4, "@.str.0")

    assert ptr_value == "%strptr.0"
    assert state.instructions == [
        "  %strptr.0 = getelementptr inbounds [4 x i8], ptr @.str.0, i64 0, i64 0"
    ]
    assert builder.inline_gep(4, "@.str.0") == "getelementptr inbounds [4 x i8], ptr @.str.0, i64 0, i64 0"
    assert builder.constant_gep(4, "@.str.0") == "getelementptr inbounds ([4 x i8], ptr @.str.0, i64 0, i64 0)"
