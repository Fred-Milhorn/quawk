import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
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
    assert result.stderr == "<inline>:1:8: error: expected PRINT, got EOF\nBEGIN {\n       ^\n"


def test_quawk_rejects_multiple_stop_stage_flags() -> None:
    result = run_quawk("--lex", "--parse", 'BEGIN { print "hello" }')

    assert result.returncode == 2
    assert "not allowed with argument" in result.stderr


def test_quawk_lex_flag_prints_tokens_and_stops() -> None:
    result = run_quawk("--lex", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "BEGIN lexeme='BEGIN' span=<inline>:1:1\n"
        "LBRACE lexeme='{' span=<inline>:1:7\n"
        "PRINT lexeme='print' span=<inline>:1:9\n"
        "STRING lexeme='\"hello\"' span=<inline>:1:15\n"
        "RBRACE lexeme='}' span=<inline>:1:23\n"
        "EOF lexeme='' span=<inline>:1:24\n"
    )
    assert result.stderr == ""


def test_quawk_parse_flag_prints_ast_and_stops() -> None:
    result = run_quawk("--parse", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "BeginProgram span=<inline>:1:1\n"
        "  PrintStatement span=<inline>:1:9\n"
        "    literal='hello'\n"
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


def test_quawk_asm_flag_prints_assembly_and_stops() -> None:
    result = run_quawk("--asm", 'BEGIN { print "hello" }')

    assert result.returncode == 0, result.stderr
    assert "quawk_main" in result.stdout
    assert "puts" in result.stdout
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
    assert result.stderr == (f"{program_path}:1:8: error: expected PRINT, got EOF\n"
                             "BEGIN {\n"
                             "       ^\n")


def test_quawk_reports_the_correct_file_for_multi_file_errors() -> None:
    first_path = ROOT / "tests" / "fixtures" / "diagnostics" / "first.awk"
    second_path = ROOT / "tests" / "fixtures" / "diagnostics" / "second_bad.awk"
    result = run_quawk("-f", str(first_path), "-f", str(second_path))

    assert result.returncode == 2
    assert result.stderr == (f"{second_path}:1:1: error: unsupported token: 'x'\n"
                             "x\n"
                             "^\n")
