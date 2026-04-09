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
    assert "Operand '-' means standard input at that position." in result.stdout


def test_quawk_short_help_exits_zero() -> None:
    result = run_quawk("-h")

    assert result.returncode == 0, result.stderr
    assert "usage: quawk" in result.stdout
    assert "quawk [options] -f progfile" in result.stdout
    assert result.stderr == ""


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


def test_quawk_applies_numeric_v_assignment_before_execution() -> None:
    result = run_quawk("-v", "x=7", "BEGIN { print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "7\n"
    assert result.stderr == ""


def test_quawk_applies_repeated_v_assignments_in_argument_order() -> None:
    result = run_quawk("-v", "x=1", "-v", "x=3", "BEGIN { print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""


def test_quawk_applies_v_assignments_with_file_based_programs(tmp_path) -> None:
    program_path = tmp_path / "print_x.awk"
    program_path.write_text("BEGIN { print x }", encoding="utf-8")

    result = run_quawk("-v", "x=9", "-f", str(program_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "9\n"
    assert result.stderr == ""


def test_quawk_treats_first_positional_after_f_as_input_file(tmp_path) -> None:
    program_path = tmp_path / "print_records.awk"
    input_path = tmp_path / "records.txt"
    program_path.write_text('{ print FILENAME ":" $1 }', encoding="utf-8")
    input_path.write_text("alpha beta\ngamma delta\n", encoding="utf-8")

    result = run_quawk("-f", str(program_path), str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{input_path}:alpha\n{input_path}:gamma\n"
    assert result.stderr == ""


def test_quawk_dash_dash_stops_option_parsing_for_input_files(tmp_path) -> None:
    input_path = tmp_path / "--records.txt"
    input_path.write_text("alpha beta\n", encoding="utf-8")

    result = run_quawk('{ print FILENAME ":" $1 }', "--", str(input_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{input_path}:alpha\n"
    assert result.stderr == ""


def test_quawk_stdin_operand_dash_is_processed_in_file_order(tmp_path) -> None:
    file_path = tmp_path / "records.txt"
    file_path.write_text("from-file\n", encoding="utf-8")

    result = run_quawk('{ print FILENAME ":" $0 }', "-", str(file_path), stdin="from-stdin\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"-:from-stdin\n{file_path}:from-file\n"
    assert result.stderr == ""


def test_quawk_reports_invalid_v_assignment_format() -> None:
    result = run_quawk("-v", "x", "BEGIN { print 1 }")

    assert result.returncode == 2
    assert result.stderr == "quawk: invalid -v assignment 'x': expected name=value\n"


def test_quawk_reports_invalid_v_assignment_name() -> None:
    result = run_quawk("-v", "1x=2", "BEGIN { print 1 }")

    assert result.returncode == 2
    assert result.stderr == "quawk: invalid -v variable name '1x'\n"


def test_quawk_applies_string_v_assignment_before_execution() -> None:
    result = run_quawk("-v", "x=hello", 'BEGIN { print x; print x "!" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello\nhello!\n"
    assert result.stderr == ""


def test_quawk_rejects_v_assignment_to_function_name() -> None:
    result = run_quawk("-v", "f=1", "function f(x) { return x }\nBEGIN { print f(2) }")

    assert result.returncode == 2
    assert result.stderr == "quawk: cannot assign to function name via -v: f\n"


def test_quawk_prints_unset_begin_scalars_as_empty_strings() -> None:
    result = run_quawk("BEGIN { print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "\n"
    assert result.stderr == ""


def test_quawk_prints_unset_mixed_program_scalars_as_empty_strings() -> None:
    result = run_quawk('BEGIN { print x } END { print "done" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "\ndone\n"
    assert result.stderr == ""


def test_quawk_preserves_unset_scalar_assignment_string_view() -> None:
    result = run_quawk("BEGIN { y = x; print y }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "\n"
    assert result.stderr == ""


def test_quawk_preserves_unset_scalar_string_and_numeric_views() -> None:
    result = run_quawk("BEGIN { print x; print x + 1 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "\n1\n"
    assert result.stderr == ""


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
        "      AssignStmt span=<inline>:1:9 op=PlainAssign\n"
        "        NameLValue span=<inline>:1:9 name='x'\n"
        "        Value\n"
        "          BinaryExpr span=<inline>:1:13 op=ADD\n"
        "            NumericLiteralExpr span=<inline>:1:13 value=1.0\n"
        "            NumericLiteralExpr span=<inline>:1:17 value=2.0\n"
        "      PrintStmt span=<inline>:1:20\n"
        "        NameExpr span=<inline>:1:26 name='x'\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_array_assignment_ast() -> None:
    result = run_quawk("--parse", 'BEGIN { a["x"] = 1; print a["x"] }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      AssignStmt span=<inline>:1:9 op=PlainAssign\n"
        "        ArrayLValue span=<inline>:1:9 name='a'\n"
        "          StringLiteralExpr span=<inline>:1:11 value='x'\n"
        "        Value\n"
        "          NumericLiteralExpr span=<inline>:1:18 value=1.0\n"
        "      PrintStmt span=<inline>:1:21\n"
        "        ArrayIndexExpr span=<inline>:1:27 array_name='a'\n"
        "          StringLiteralExpr span=<inline>:1:29 value='x'\n"
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


def test_quawk_parse_flag_prints_break_and_continue_ast() -> None:
    result = run_quawk("--parse", "BEGIN { while (1) { break; continue } }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      WhileStmt span=<inline>:1:9\n"
        "        Condition\n"
        "          NumericLiteralExpr span=<inline>:1:16 value=1.0\n"
        "        Body\n"
        "          BlockStmt span=<inline>:1:19\n"
        "            BreakStmt span=<inline>:1:21\n"
        "            ContinueStmt span=<inline>:1:28\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_equality_expression_ast() -> None:
    result = run_quawk("--parse", "BEGIN { print 1 == 1 }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        BinaryExpr span=<inline>:1:15 op=EQUAL\n"
        "          NumericLiteralExpr span=<inline>:1:15 value=1.0\n"
        "          NumericLiteralExpr span=<inline>:1:20 value=1.0\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_parenthesized_logical_and_ast() -> None:
    result = run_quawk("--parse", "BEGIN { print (1 < 2) && (2 < 3) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Program span=<inline>:1:1\n"
        "  PatternAction span=<inline>:1:1\n"
        "    BeginPattern span=<inline>:1:1\n"
        "    Action span=<inline>:1:7\n"
        "      PrintStmt span=<inline>:1:9\n"
        "        BinaryExpr span=<inline>:1:16 op=LOGICAL_AND\n"
        "          BinaryExpr span=<inline>:1:16 op=LESS\n"
        "            NumericLiteralExpr span=<inline>:1:16 value=1.0\n"
        "            NumericLiteralExpr span=<inline>:1:20 value=2.0\n"
        "          BinaryExpr span=<inline>:1:27 op=LESS\n"
        "            NumericLiteralExpr span=<inline>:1:27 value=2.0\n"
        "            NumericLiteralExpr span=<inline>:1:31 value=3.0\n"
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
    assert "@.fmt.num = private unnamed_addr constant [6 x i8] c\"\\25\\2E\\36\\67\\0A\\00\"" in result.stdout
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


def test_quawk_ir_flag_prints_backend_ir_for_claimed_unset_scalar_value_cases() -> None:
    result = run_quawk("--ir", "BEGIN { print x; print x + 1 }")

    assert result.returncode == 0, result.stderr
    assert "@qk_scalar_get(" in result.stdout
    assert "@qk_scalar_get_number(" in result.stdout
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


def test_quawk_ir_flag_prints_equality_expression_ir() -> None:
    result = run_quawk("--ir", "BEGIN { print 1 == 1 }")

    assert result.returncode == 0, result.stderr
    assert "fcmp oeq double 1.000000000000000e+00, 1.000000000000000e+00" in result.stdout
    assert "uitofp i1 %boolnum." in result.stdout or "uitofp i1 %cmp." in result.stdout
    assert "call i32 (ptr, ...) @printf(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_logical_and_expression_ir() -> None:
    result = run_quawk("--ir", "BEGIN { print (1 < 2) && (2 < 3) }")

    assert result.returncode == 0, result.stderr
    assert "fcmp olt double 1.000000000000000e+00, 2.000000000000000e+00" in result.stdout
    assert "fcmp olt double 2.000000000000000e+00, 3.000000000000000e+00" in result.stdout
    assert "phi i1 [ false, %and.false." in result.stdout
    assert "uitofp i1 %and." in result.stdout
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


def test_quawk_ir_flag_prints_runtime_comparison_helper_for_field_patterns() -> None:
    result = run_quawk("--ir", '$1 > 5000 { next } { print }')

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert "@qk_compare_values" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_numeric_concat_record_programs() -> None:
    result = run_quawk("--ir", '{ print NR " " 10 / NR }')

    assert result.returncode == 0, result.stderr
    assert "@qk_get_nr(" in result.stdout
    assert "@qk_concat(" in result.stdout
    assert "fdiv double" in result.stdout
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
    assert result.stderr == (f"{second_path}:1:1: error: expected statement, got RPAREN\n"
                             ")\n"
                             "^\n")


def test_quawk_reports_missing_progfile_without_traceback() -> None:
    missing_path = ROOT / "tests" / "fixtures" / "diagnostics" / "does_not_exist.awk"
    result = run_quawk("-f", str(missing_path))

    assert result.returncode == 2
    assert result.stderr == f"quawk: {missing_path}: No such file or directory\n"


def test_quawk_ir_flag_prints_backend_ir_for_supported_p21_logical_or_program() -> None:
    result = run_quawk("--ir", "BEGIN { print (1 || 0) }")

    assert result.returncode == 0, result.stderr
    assert "phi i1" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_p24_match_program() -> None:
    result = run_quawk("--ir", 'BEGIN { print ("abc" ~ /b/); print ("abc" !~ /d/) }')

    assert result.returncode == 0, result.stderr
    assert "@qk_regex_match_text(" in result.stdout
    assert result.stderr == ""


def test_quawk_supports_the_current_p21_target_forms_under_ir_and_asm() -> None:
    p21_programs = [
        "BEGIN { print (1 || 0) }",
        "BEGIN { print (1 <= 0) }",
        "BEGIN { print (1 > 0) }",
        "BEGIN { print (1 >= 0) }",
        "BEGIN { print (1 != 0) }",
    ]

    for flag in ("--ir", "--asm"):
        for source_text in p21_programs:
            result = run_quawk(flag, source_text)

            assert result.returncode == 0, result.stderr
            assert result.stdout != ""
            assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_p24_membership_program() -> None:
    result = run_quawk("--ir", 'BEGIN { a["x"] = 1; print ("x" in a); print ("y" in a) }')

    assert result.returncode == 0, result.stderr
    assert "@qk_array_contains(" in result.stdout
    assert result.stderr == ""


def test_quawk_supports_the_current_p21_target_forms_for_public_execution() -> None:
    p21_programs = [
        "BEGIN { print (1 || 0) }",
        "BEGIN { print (1 <= 0) }",
        "BEGIN { print (1 > 0) }",
        "BEGIN { print (1 >= 0) }",
        "BEGIN { print (1 != 0) }",
    ]

    expected = {
        "BEGIN { print (1 || 0) }": "1\n",
        "BEGIN { print (1 <= 0) }": "0\n",
        "BEGIN { print (1 > 0) }": "1\n",
        "BEGIN { print (1 >= 0) }": "1\n",
        "BEGIN { print (1 != 0) }": "1\n",
    }

    for source_text in p21_programs:
        result = run_quawk(source_text)

        assert result.returncode == 0, result.stderr
        assert result.stdout == expected[source_text]
        assert result.stderr == ""


def test_quawk_supports_p21_string_and_numeric_comparison_semantics() -> None:
    result = run_quawk(
        'BEGIN { x = "abc"; y = "10"; print (x > y); x = "2"; y = "10"; print (x > y); print (x <= y); print (x != y) }'
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n0\n1\n1\n"
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_p22_arithmetic_program() -> None:
    result = run_quawk("--ir", "BEGIN { print (8 - 3); print (2 * 4); print (8 / 2); print (7 % 4); print (2 ^ 3) }")

    assert result.returncode == 0, result.stderr
    assert "fsub double" in result.stdout
    assert "fmul double" in result.stdout
    assert "fdiv double" in result.stdout
    assert "@llvm.trunc.f64" in result.stdout
    assert "@llvm.pow.f64" in result.stdout
    assert result.stderr == ""


def test_quawk_supports_the_current_p22_target_forms_under_ir_and_asm() -> None:
    p22_programs = [
        "BEGIN { print (8 - 3) }",
        "BEGIN { print (2 * 4) }",
        "BEGIN { print (8 / 2) }",
        "BEGIN { print (7 % 4) }",
        "BEGIN { print (2 ^ 3) }",
    ]

    for flag in ("--ir", "--asm"):
        for source_text in p22_programs:
            result = run_quawk(flag, source_text)

            assert result.returncode == 0, result.stderr
            assert result.stdout != ""
            assert result.stderr == ""


def test_quawk_supports_the_current_p22_target_forms_for_public_execution() -> None:
    p22_programs = [
        "BEGIN { print (8 - 3) }",
        "BEGIN { print (2 * 4) }",
        "BEGIN { print (8 / 2) }",
        "BEGIN { print (7 % 4) }",
        "BEGIN { print (2 ^ 3) }",
    ]

    expected = {
        "BEGIN { print (8 - 3) }": "5\n",
        "BEGIN { print (2 * 4) }": "8\n",
        "BEGIN { print (8 / 2) }": "4\n",
        "BEGIN { print (7 % 4) }": "3\n",
        "BEGIN { print (2 ^ 3) }": "8\n",
    }

    for source_text in p22_programs:
        result = run_quawk(source_text)

        assert result.returncode == 0, result.stderr
        assert result.stdout == expected[source_text]
        assert result.stderr == ""


def test_quawk_supports_p22_arithmetic_precedence_and_assignment_semantics() -> None:
    result = run_quawk("BEGIN { x = 8 - 3 * 2 / 1 % 4 ^ 2; print x; print (2 ^ 3 % 3) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "2\n2\n"
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_p23_ternary_program() -> None:
    result = run_quawk("--ir", 'BEGIN { print (1 ? 2 : 3); print (0 ? "yes" : "no") }')

    assert result.returncode == 0, result.stderr
    assert "select i1" in result.stdout
    assert result.stderr == ""


def test_quawk_supports_the_current_p23_target_forms_under_ir_and_asm() -> None:
    p23_programs = [
        "BEGIN { print (1 ? 2 : 3) }",
        "BEGIN { print (0 ? 2 : 3) }",
        'BEGIN { print (1 ? "yes" : "no") }',
        "BEGIN { print (1 ? (0 ? 2 : 3) : 4) }",
    ]

    for flag in ("--ir", "--asm"):
        for source_text in p23_programs:
            result = run_quawk(flag, source_text)

            assert result.returncode == 0, result.stderr
            assert result.stdout != ""
            assert result.stderr == ""


def test_quawk_supports_the_current_p23_target_forms_for_public_execution() -> None:
    expected = {
        "BEGIN { print (1 ? 2 : 3) }": "2\n",
        "BEGIN { print (0 ? 2 : 3) }": "3\n",
        'BEGIN { print (1 ? "yes" : "no") }': "yes\n",
        "BEGIN { print (1 ? (0 ? 2 : 3) : 4) }": "3\n",
    }

    for source_text, stdout in expected.items():
        result = run_quawk(source_text)

        assert result.returncode == 0, result.stderr
        assert result.stdout == stdout
        assert result.stderr == ""


def test_quawk_supports_p23_ternary_string_and_numeric_branch_semantics() -> None:
    result = run_quawk(
        'BEGIN { x = 1; print (x ? "left" : "right"); x = 0; print (x ? 10 : 20); print ((x ? 1 : 0) ? "a" : "b") }'
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "left\n20\nb\n"
    assert result.stderr == ""


def test_quawk_supports_the_current_p24_target_forms_under_ir_and_asm() -> None:
    p24_programs = [
        'BEGIN { print ("abc" ~ /b/) }',
        'BEGIN { print ("abc" !~ /d/) }',
        'BEGIN { a["x"] = 1; print ("x" in a) }',
    ]

    for flag in ("--ir", "--asm"):
        for source_text in p24_programs:
            result = run_quawk(flag, source_text)

            assert result.returncode == 0, result.stderr
            assert result.stdout != ""
            assert result.stderr == ""


def test_quawk_supports_the_current_p24_target_forms_for_public_execution() -> None:
    expected = {
        'BEGIN { print ("abc" ~ /b/) }': "1\n",
        'BEGIN { print ("abc" !~ /d/) }': "1\n",
        'BEGIN { a["x"] = 1; print ("x" in a) }': "1\n",
    }

    for source_text, stdout in expected.items():
        result = run_quawk(source_text)

        assert result.returncode == 0, result.stderr
        assert result.stdout == stdout
        assert result.stderr == ""


def test_quawk_supports_p24_match_and_membership_semantics() -> None:
    result = run_quawk(
        'BEGIN { a["x"] = 1; a[2] = 3; print ("abc" ~ /b/); print ("abc" !~ /d/); print ("y" in a); print (2 in a) }'
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1\n0\n1\n"
    assert result.stderr == ""



def test_quawk_ir_flag_prints_backend_ir_for_supported_function_programs() -> None:
    result = run_quawk("--ir", "function f(x) { return x + 1 }\nBEGIN { print f(2) }")

    assert result.returncode == 0, result.stderr
    assert "define double @qk_fn_f(" in result.stdout
    assert "call double @qk_fn_f(" in result.stdout
    assert result.stderr == ""


def test_quawk_executes_supported_function_program_with_local_parameter_scope() -> None:
    result = run_quawk("function f(x) { x = x + 1; return x }\nBEGIN { x = 10; print f(2); print x }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n10\n"
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_nextfile_programs() -> None:
    result = run_quawk("--ir", "/stop/ { nextfile }\n{ print $0 }")

    assert result.returncode == 0, result.stderr
    assert "@qk_nextfile(" in result.stdout
    assert "call void @qk_nextfile(ptr %rt)" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_exit_programs() -> None:
    result = run_quawk("--ir", 'BEGIN { print "before"; exit 7 }\nEND { print "done" }')

    assert result.returncode == 0, result.stderr
    assert "@qk_request_exit(" in result.stdout
    assert "@qk_exit_status(" in result.stdout
    assert "call void @qk_request_exit(ptr %rt, i32 %exit.status" in result.stdout or "call void @qk_request_exit(ptr %rt, i32 7)" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_scalar_string_programs() -> None:
    result = run_quawk("--ir", 'BEGIN { x = "12"; print x + 1; print x "a" }')

    assert result.returncode == 0, result.stderr
    assert "@qk_scalar_set_string(" in result.stdout
    assert "@qk_scalar_get_number(" in result.stdout
    assert "@qk_concat(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_string_v_preassignments() -> None:
    result = run_quawk("--ir", "-v", "x=hello", 'BEGIN { print x }')

    assert result.returncode == 0, result.stderr
    assert "@qk_scalar_set_string(" in result.stdout
    assert "@.driver.scalar.value.0" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_print_surface_programs() -> None:
    result = run_quawk("--ir", 'BEGIN { OFS = ","; ORS = "!"; print 1, 2; print }')

    assert result.returncode == 0, result.stderr
    assert "@qk_print_number_fragment(" in result.stdout
    assert "@qk_print_output_separator(" in result.stdout
    assert "@qk_print_output_record_separator(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_formatting_variable_programs() -> None:
    result = run_quawk("--ir", 'BEGIN { OFMT = "%.2f"; CONVFMT = "%.3f"; print 1.2345; print 1.2345 "" }')

    assert result.returncode == 0, result.stderr
    assert "@qk_print_number_fragment(" in result.stdout
    assert "@qk_format_number(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_input_separator_programs() -> None:
    result = run_quawk("--ir", 'BEGIN { FS = ":"; RS = ";" } { print $1 }')

    assert result.returncode == 0, result.stderr
    assert "@qk_scalar_set_string(" in result.stdout
    assert "@qk_get_field(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_nf_rebuild_programs() -> None:
    result = run_quawk("--ir", '{ OFS = "|"; NF = 2; print; $5 = "five"; print }')

    assert result.returncode == 0, result.stderr
    assert "@qk_scalar_set_number(" in result.stdout
    assert "@qk_set_field_string(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_bare_length() -> None:
    result = run_quawk("--ir", "{ print length, $0 }")

    assert result.returncode == 0, result.stderr
    assert "@strlen(" in result.stdout
    assert "@qk_get_field(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_output_redirect_programs() -> None:
    result = run_quawk('--ir', 'BEGIN { print "x" > "out"; printf "%s", "y" >> "out"; close("out") }')

    assert result.returncode == 0, result.stderr
    assert "@qk_open_output(" in result.stdout
    assert "@qk_close_output(" in result.stdout
    assert "@fprintf(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_getline_programs() -> None:
    result = run_quawk("--ir", '{ print getline x; print getline < "input.txt" }')

    assert result.returncode == 0, result.stderr
    assert "@qk_getline_main_string(" in result.stdout
    assert "@qk_getline_file_record(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_parenthesized_printf_with_substr() -> None:
    result = run_quawk('--ir', 'BEGIN { x = "A"; printf("%-39s\\n", substr(x, 1, 39)) }')

    assert result.returncode == 0, result.stderr
    assert "@qk_substr3(" in result.stdout
    assert "call i32 (ptr, ...) @printf(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_string_and_regex_builtins() -> None:
    result = run_quawk(
        "--ir",
        'BEGIN { x = "bananas"; print index(x, "na"); print match(x, /ana/); '
        'print sub(/ana/, "[&]", x); print sprintf("%s:%c", tolower("AbC"), 66); print toupper("ab") }',
    )

    assert result.returncode == 0, result.stderr
    assert "@qk_index(" in result.stdout
    assert "@qk_match(" in result.stdout
    assert "@qk_substitute(" in result.stdout
    assert "@qk_sprintf(" in result.stdout
    assert "@qk_tolower(" in result.stdout
    assert "@qk_toupper(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_numeric_and_system_builtins() -> None:
    result = run_quawk(
        "--ir",
        'BEGIN { print int(3.9); print atan2(0, -1); print cos(0); print exp(1); '
        'print log(exp(1)); print sqrt(9); print srand(1); print rand(); print system("exit 7") }',
    )

    assert result.returncode == 0, result.stderr
    assert "@qk_int_builtin(" in result.stdout
    assert "@qk_atan2(" in result.stdout
    assert "@qk_cos(" in result.stdout
    assert "@qk_exp(" in result.stdout
    assert "@qk_log(" in result.stdout
    assert "@qk_sqrt(" in result.stdout
    assert "@qk_srand1(" in result.stdout
    assert "@qk_rand(" in result.stdout
    assert "@qk_system(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_do_while_programs() -> None:
    result = run_quawk("--ir", "BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_begin(" in result.stdout
    assert "dowhile.body" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_next_programs() -> None:
    result = run_quawk("--ir", "/skip/ { next }\n{ print $0 }")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert "phase.exit" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_expression_pattern_programs() -> None:
    result = run_quawk("--ir", "1 { print $0 }")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_supported_default_print_expression_patterns() -> None:
    result = run_quawk("--ir", "1")

    assert result.returncode == 0, result.stderr
    assert "define void @quawk_record(" in result.stdout
    assert "call void @qk_print_string(ptr %rt, ptr %field" in result.stdout
    assert result.stderr == ""


def test_quawk_executes_supported_nextfile_program_through_backend(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a\nstop\nb\n", encoding="utf-8")
    second.write_text("c\n", encoding="utf-8")

    result = run_quawk('/stop/ { nextfile }\n{ print $0 }', str(first), str(second))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "a\nc\n"
    assert result.stderr == ""


def test_quawk_executes_supported_output_redirect_program_through_backend(tmp_path: Path) -> None:
    output_path = tmp_path / "out.txt"

    result = run_quawk(
        (
            f'BEGIN {{ print "x" > "{output_path}"; close("{output_path}"); '
            f'printf "%s", "y" >> "{output_path}"; close("{output_path}") }}'
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert output_path.read_text(encoding="utf-8") == "x\ny"


def test_quawk_executes_supported_exit_program_with_end() -> None:
    result = run_quawk('BEGIN { print "before"; exit 7 }\nEND { print "done" }')

    assert result.returncode == 7, result.stderr
    assert result.stdout == "before\ndone\n"
    assert result.stderr == ""


def test_quawk_executes_supported_scalar_string_program_through_backend() -> None:
    result = run_quawk('BEGIN { x = "12"; print x + 1; print x "a" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "13\n12a\n"
    assert result.stderr == ""


def test_quawk_executes_string_v_preassignments_through_backend() -> None:
    result = run_quawk("-v", "x=12", 'BEGIN { print x + 1; print x "a" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "13\n12a\n"
    assert result.stderr == ""


def test_quawk_preserves_string_v_plus_function_value_behavior() -> None:
    result = run_quawk("-v", "x=hello", "function f(y) { return y + 1 }\nBEGIN { print x; print f(1) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello\n2\n"
    assert result.stderr == ""


def test_quawk_ir_flag_prints_backend_ir_for_string_v_plus_function_programs() -> None:
    result = run_quawk("--ir", "-v", "x=hello", "function f(y) { return y + 1 }\nBEGIN { print x; print f(1) }")

    assert result.returncode == 0, result.stderr
    assert "declare i32 @puts(ptr)" in result.stdout
    assert "@qk_fn_f(" in result.stdout
    assert result.stderr == ""


def test_quawk_executes_supported_print_surface_program_through_backend() -> None:
    result = run_quawk('BEGIN { OFS = ","; ORS = "!"; print 1, 2; print }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1,2!!"
    assert result.stderr == ""


def test_quawk_executes_supported_formatting_variable_program_through_backend() -> None:
    result = run_quawk('BEGIN { OFMT = "%.2f"; CONVFMT = "%.3f"; print 1.2345; print 1.2345 "" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1.23\n1.234\n"
    assert result.stderr == ""


def test_quawk_executes_nf_rebuild_program_through_backend() -> None:
    result = run_quawk('{ OFS = "|"; NF = 2; print; $5 = "five"; print }', stdin="one two three\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "one|two\none|two|||five\n"
    assert result.stderr == ""


def test_quawk_executes_supported_do_while_program_through_backend() -> None:
    result = run_quawk("BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n"
    assert result.stderr == ""


def test_quawk_executes_supported_next_program_through_backend() -> None:
    result = run_quawk("/skip/ { next }\n{ print $0 }", stdin="skip\nkeep\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "keep\n"
    assert result.stderr == ""


def test_quawk_executes_supported_expression_pattern_program_through_backend() -> None:
    result = run_quawk("1 { print $0 }", stdin="keep\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "keep\n"
    assert result.stderr == ""


def test_quawk_executes_supported_default_print_expression_pattern_through_backend() -> None:
    result = run_quawk("1", stdin="keep\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "keep\n"
    assert result.stderr == ""
