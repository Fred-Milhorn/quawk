# CLI-level behavioral tests.
# These cases exercise the installed `quawk` command, including stage-dump
# modes, diagnostics, and end-to-end command-line behavior.

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_quawk_help_exits_zero() -> None:
    result = run_quawk("--help")

    assert result.returncode == 0, result.stderr
    assert "usage: quawk" in result.stdout
    assert "--version" in result.stdout


def test_quawk_version_exits_zero() -> None:
    result = run_quawk("--version")

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("quawk 0.1.0")


def test_quawk_requires_program_source() -> None:
    result = run_quawk()

    assert result.returncode == 2
    assert "missing AWK program text or -f progfile" in result.stderr


def test_quawk_reports_parse_errors() -> None:
    result = run_quawk("BEGIN {")

    assert result.returncode == 2
    assert result.stderr == "<inline>:1:8: error: expected statement, got EOF\nBEGIN {\n       ^\n"


def test_quawk_rejects_multiple_stop_stage_flags() -> None:
    result = run_quawk("--lex", "--parse", 'BEGIN { print "hello" }')

    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr


def test_quawk_lex_flag_prints_tokens_and_stops() -> None:
    result = run_quawk("--lex", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "BEGIN text='BEGIN' span=<inline>:1:1\n"
        "LBRACE text='{' span=<inline>:1:7\n"
        "PRINT text='print' span=<inline>:1:9\n"
        "STRING text='\"hello\"' span=<inline>:1:15\n"
        "RBRACE text='}' span=<inline>:1:23\n"
        "EOF span=<inline>:1:24\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_ast_and_stops() -> None:
    result = run_quawk("--parse", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        StringLiteralExpr span=<inline>:1:15 value='hello'\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_numeric_expression_ast() -> None:
    result = run_quawk("--parse", "BEGIN { print 1 + 2 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        BinaryExpr span=<inline>:1:15 op=ADD\n"
        "          NumericLiteralExpr span=<inline>:1:15 value=1.0\n"
        "          NumericLiteralExpr span=<inline>:1:19 value=2.0\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_assignment_ast() -> None:
    result = run_quawk("--parse", "BEGIN { x = 1 + 2; print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      AssignStmt span=<inline>:1:9 name='x'\n"
        "        BinaryExpr span=<inline>:1:13 op=ADD\n"
        "          NumericLiteralExpr span=<inline>:1:13 value=1.0\n"
        "          NumericLiteralExpr span=<inline>:1:17 value=2.0\n"
        "      PrintStmt span=<inline>:1:20\n"
        "        NameExpr span=<inline>:1:26 name='x'\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_bare_action_ast() -> None:
    result = run_quawk("--parse", "{ print $1 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    Action span=<inline>:1:1\n"
        "      PrintStmt span=<inline>:1:3\n"
        "        FieldExpr span=<inline>:1:9 index=1\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_control_flow_ast() -> None:
    result = run_quawk("--parse", "BEGIN { if (1 < 2) print 3 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      IfStmt span=<inline>:1:9\n"
        "        Condition\n"
        "          BinaryExpr span=<inline>:1:13 op=LESS\n"
        "            NumericLiteralExpr span=<inline>:1:13 value=1.0\n"
        "            NumericLiteralExpr span=<inline>:1:17 value=2.0\n"
        "        Then\n"
        "          PrintStmt span=<inline>:1:20\n"
        "            NumericLiteralExpr span=<inline>:1:26 value=3.0\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_mixed_program_ast() -> None:
    result = run_quawk("--parse", 'BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        StringLiteralExpr span=<inline>:1:15 value='start'\n"
        "  PatternAction span=<inline>:2:1\n"
        "    Action span=<inline>:2:1\n"
        "      PrintStmt span=<inline>:2:3\n"
        "        FieldExpr span=<inline>:2:9 index=2\n"
        "  PatternAction span=<inline>:3:1\n"
        "    EndPattern span=<inline>:3:1\n"
        "    Action span=<inline>:3:5\n"
        "      PrintStmt span=<inline>:3:7\n"
        "        StringLiteralExpr span=<inline>:3:13 value='done'\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_end_only_program_ast() -> None:
    result = run_quawk("--parse", 'END { print "done" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    EndPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:5\n"
        "      PrintStmt span=<inline>:1:7\n"
        "        StringLiteralExpr span=<inline>:1:13 value='done'\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_regex_pattern_action_ast() -> None:
    result = run_quawk("--parse", "/foo/ { print $0 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    ExprPattern span=<inline>:1:1\n"
        "      RegexLiteralExpr span=<inline>:1:1 raw_text='/foo/'\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        FieldExpr span=<inline>:1:15 index=0\n"
    )
    assert result.stderr == ""


def test_quawk_ir_flag_prints_llvm_ir_and_stops() -> None:
    result = run_quawk("--ir", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert "declare i32 @puts(ptr)" in result.stdout
    assert "@.str.0 = private unnamed_addr constant [6 x i8] c\"\\68\\65\\6C\\6C\\6F\\00\"" in result.stdout
    assert "define i32 @quawk_main()" in result.stdout
    assert "call i32 @puts(ptr %strptr.0)" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_numeric_print_ir_and_stops() -> None:
    result = run_quawk("--ir", "BEGIN { print 1 + 2 }")

    assert result.returncode == 0, result.stderr
    assert "declare i32 @printf(ptr, ...)" in result.stdout
    assert "@.fmt.num = private unnamed_addr constant [4 x i8] c\"\\25\\67\\0A\\00\"" in result.stdout
    assert "fadd double 1.000000000000000e+00, 2.000000000000000e+00" in result.stdout
    assert "call i32 (ptr, ...) @printf(ptr %fmtptr.0, double %add.1)" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_assignment_ir_and_stops() -> None:
    result = run_quawk("--ir", "BEGIN { x = 1 + 2; print x }")

    assert result.returncode == 0, result.stderr
    assert "alloca double" in result.stdout
    assert "store double %add.1, ptr %var.x.0" in result.stdout
    assert "load double, ptr %var.x.0" in result.stdout
    assert "call i32 (ptr, ...) @printf(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_record_program_ir_and_stops() -> None:
    result = run_quawk("--ir", "{ print $1 }")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(ptr %rt, ptr %state)" in result.stdout
    assert "@qk_get_field" in result.stdout
    assert "ptr %field1" not in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_reusable_record_program_ir() -> None:
    result = run_quawk("--ir", "{ print $1 }")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert "@qk_get_field" in result.stdout
    assert "ptr %field1" not in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_control_flow_ir_and_stops() -> None:
    result = run_quawk("--ir", "BEGIN { if (1 < 2) print 3 }")

    assert result.returncode == 0, result.stderr
    assert "fcmp olt double 1.000000000000000e+00, 2.000000000000000e+00" in result.stdout
    assert "br i1 %cmp." in result.stdout
    assert "label %if.then.0, label %if.end.1" in result.stdout
    assert "if.then.0:" in result.stdout
    assert "if.end.1:" in result.stdout
    assert result.stderr == ""


def test_quawk_asm_flag_prints_assembly_and_stops() -> None:
    result = run_quawk("--asm", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert "quawk_main" in result.stdout
    assert "puts" in result.stdout
    assert result.stderr == ""


def test_quawk_asm_flag_prints_mixed_program_assembly() -> None:
    result = run_quawk("--asm", 'BEGIN { print "start" } { print $2 } END { print "done" }')

    assert result.returncode == 0, result.stderr
    assert "quawk_begin" in result.stdout
    assert "quawk_record" in result.stdout
    assert "quawk_end" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_reusable_mixed_program_ir() -> None:
    result = run_quawk("--ir", 'BEGIN { print "start" } { print $2 } END { print "done" }')

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_begin(" in result.stdout
    assert "define void @quawk_record(" in result.stdout
    assert "define void @quawk_end(" in result.stdout
    assert "@qk_get_field" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_reusable_regex_program_ir() -> None:
    result = run_quawk("--ir", "/foo/ { print $0 }", stdin="foo\nbar\nfood\n")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert "@qk_regex_match_current_record" in result.stdout
    assert result.stderr == ""


def test_quawk_reports_string_escape_errors_with_token_location() -> None:
    result = run_quawk(r'BEGIN { print "bad\q" }')

    assert result.returncode == 2
    assert result.stderr == (
        "<inline>:1:15: error: unsupported escape sequence: \\q\n"
        'BEGIN { print "bad\\q" }\n'
        "              ^\n"
    )


def test_quawk_reports_file_based_errors_with_file_line_and_column() -> None:
    program_path = ROOT / "tests" / "fixtures" / "diagnostics" / "bad_parse.awk"
    result = run_quawk("-f", str(program_path))

    assert result.returncode == 2
    assert result.stderr == (f"{program_path}:1:8: error: expected statement, got EOF\n"
                             "BEGIN {\n"
                             "       ^\n")


def test_quawk_reports_the_correct_file_for_multi_file_errors() -> None:
    first_path = ROOT / "tests" / "fixtures" / "diagnostics" / "first.awk"
    second_path = ROOT / "tests" / "fixtures" / "diagnostics" / "second_bad.awk"
    result = run_quawk("-f", str(first_path), "-f", str(second_path))

    assert result.returncode == 2
    assert result.stderr == (f"{second_path}:1:1: error: expected statement, got IDENT\n"
                             "x\n"
                             "^\n")


def test_quawk_reports_missing_progfile_without_traceback() -> None:
    missing_path = ROOT / "tests" / "fixtures" / "diagnostics" / "does_not_exist.awk"
    result = run_quawk("-f", str(missing_path))

    assert result.returncode == 2
    assert result.stderr == f"quawk: {missing_path}: No such file or directory\n"
