# P8 POSIX-core runtime and builtin baselines.
# These cases pin the remaining execution, builtin, and builtin-variable
# surface before the runtime implementation lands.

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_quawk(
    *args: str,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["quawk", *args],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        env=None if env is None else {**os.environ, **env},
        check=False,
    )


def test_range_pattern_without_action_prints_matching_records() -> None:
    result = run_quawk("/start/,/stop/", stdin="skip\nstart\nkeep\nstop\nafter\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "start\nkeep\nstop\n"
    assert result.stderr == ""


def test_do_while_executes_body_before_testing_condition() -> None:
    result = run_quawk("BEGIN { x = 0; do { print x; x = x + 1 } while (x < 2) }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n1\n"
    assert result.stderr == ""


def test_next_skips_to_the_next_record() -> None:
    result = run_quawk('/skip/ { next } { print $0 }', stdin="skip\nkeep\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "keep\n"
    assert result.stderr == ""


def test_nextfile_skips_remaining_records_in_current_file(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a\nstop\nb\n", encoding="utf-8")
    second.write_text("c\n", encoding="utf-8")

    result = run_quawk('/stop/ { nextfile } { print $0 }', str(first), str(second))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "a\nc\n"
    assert result.stderr == ""


def test_exit_returns_requested_status_after_prior_output() -> None:
    result = run_quawk('BEGIN { print "before"; exit 7; print "after" }')

    assert result.returncode == 7
    assert result.stdout == "before\n"
    assert result.stderr == ""


def test_printf_does_not_append_an_implicit_newline() -> None:
    result = run_quawk('BEGIN { printf "%s:%g", "x", 1 }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "x:1"
    assert result.stderr == ""


def test_parenthesized_printf_with_substr_and_string_width_executes() -> None:
    result = run_quawk('BEGIN { x = "A"; printf("%-5s|%4s\\n", substr(x, 1, 5), "B") }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "A    |   B\n"
    assert result.stderr == ""


def test_bare_print_uses_the_current_record() -> None:
    result = run_quawk("{ print }", stdin="a b\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "a b\n"
    assert result.stderr == ""


def test_multi_argument_print_uses_default_ofs() -> None:
    result = run_quawk('BEGIN { print 1, "x", 2 }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1 x 2\n"
    assert result.stderr == ""


def test_print_honors_ofs_and_ors() -> None:
    result = run_quawk('BEGIN { OFS = ","; ORS = "!"; print 1, 2; print "x" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1,2!x!"
    assert result.stderr == ""


def test_print_honors_ofmt_for_numeric_output() -> None:
    result = run_quawk('BEGIN { OFMT = "%.2f"; print 1.2345 }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1.23\n"
    assert result.stderr == ""


def test_fs_assignment_changes_field_splitting_for_subsequent_records() -> None:
    result = run_quawk('BEGIN { FS = "\\t" } { print $1; print $4 }', stdin="Canada\t3852\t24\tNorth America\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Canada\nNorth America\n"
    assert result.stderr == ""


def test_rs_assignment_changes_record_reads_for_subsequent_input() -> None:
    result = run_quawk('BEGIN { RS = ";" } { print $1 }', stdin="a b;c d;")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "a\nc\n"
    assert result.stderr == ""


def test_concatenation_honors_convfmt_for_numeric_to_string_coercion() -> None:
    result = run_quawk('BEGIN { CONVFMT = "%.2f"; x = 1.2345; print x "" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1.23\n"
    assert result.stderr == ""


def test_print_file_redirection_append_and_close(tmp_path: Path) -> None:
    output_path = tmp_path / "out.txt"

    result = run_quawk(
        (
            f'BEGIN {{ print "x" > "{output_path}"; close("{output_path}"); '
            f'print "y" >> "{output_path}"; close("{output_path}") }}'
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert output_path.read_text(encoding="utf-8") == "x\ny\n"


def test_print_pipe_output_and_close(tmp_path: Path) -> None:
    output_path = tmp_path / "pipe.txt"
    command = f"cat > {output_path}"

    result = run_quawk(f'BEGIN {{ print "x" | "{command}"; close("{command}") }}')

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
    assert output_path.read_text(encoding="utf-8") == "x\n"


def test_string_coercion_and_concatenation_follow_awk_rules() -> None:
    result = run_quawk('BEGIN { x = "12"; print x + 1; print x "a" }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "13\n12a\n"
    assert result.stderr == ""


def test_split_and_substr_builtins_execute() -> None:
    result = run_quawk('BEGIN { n = split("a b", a); print n; print a[1]; print substr("hello", 2, 3) }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "2\na\nell\n"
    assert result.stderr == ""


def test_bare_length_uses_the_current_record() -> None:
    result = run_quawk("{ print length, $0 }", stdin="a b c\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "5 a b c\n"
    assert result.stderr == ""


def test_string_and_regex_builtins_execute() -> None:
    result = run_quawk(
        'BEGIN { print index("banana", "na"); print match("banana", /ana/); '
        'print RSTART; print RLENGTH; print sprintf("%s:%c", tolower("AbC"), 66); print toupper("ab") }'
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n2\n2\n3\nabc:B\nAB\n"
    assert result.stderr == ""


def test_numeric_and_math_builtins_execute() -> None:
    result = run_quawk(
        "BEGIN { print int(3.9); print int(-3.9); print atan2(0, -1); "
        "print cos(0); print sin(0); print exp(1); print log(exp(1)); print sqrt(9) }"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n-3\n3.14159\n1\n0\n2.71828\n1\n3\n"
    assert result.stderr == ""


def test_rand_and_srand_use_the_package_owned_deterministic_sequence() -> None:
    result = run_quawk("BEGIN { print srand(1); print rand(); print rand(); print srand(5); print rand() }")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n0.51387\n0.175741\n1\n0.569327\n"
    assert result.stderr == ""


def test_system_returns_shell_status_and_allows_side_effects(tmp_path: Path) -> None:
    output_path = tmp_path / "system.txt"

    result = run_quawk(f"BEGIN {{ print system(\"printf ok > '{output_path}'\"); print system(\"exit 7\") }}")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0\n7\n"
    assert result.stderr == ""
    assert output_path.read_text(encoding="utf-8") == "ok"


def test_sub_and_gsub_update_named_targets() -> None:
    result = run_quawk('BEGIN { x = "bananas"; print sub(/ana/, "[&]", x); print x; print gsub(/a/, "A", x); print x }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\nb[ana]nas\n3\nb[AnA]nAs\n"
    assert result.stderr == ""


def test_two_argument_gsub_updates_the_current_record() -> None:
    result = run_quawk('{ gsub(/a/, "A"); print }', stdin="banana\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "bAnAnA\n"
    assert result.stderr == ""


def test_dynamic_field_assignment_updates_the_selected_field() -> None:
    result = run_quawk('{ i = 2; $i = 9; print $0 }', stdin="1 2 3\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1 9 3\n"
    assert result.stderr == ""


def test_builtin_variables_nr_fnr_and_nf_update_per_record() -> None:
    result = run_quawk("{ print NR; print FNR; print NF }", stdin="a b\nc d\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1\n2\n2\n2\n2\n"
    assert result.stderr == ""


def test_end_only_program_consumes_input_and_reports_final_nr(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a\nb\n", encoding="utf-8")
    second.write_text("c\n", encoding="utf-8")

    result = run_quawk("END { print NR }", str(first), str(second))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "3\n"
    assert result.stderr == ""


def test_backslash_continued_multiline_print_executes() -> None:
    result = run_quawk('BEGIN { print "population of", 6,\\\n"Asian countries in millions is", 3530 }')

    assert result.returncode == 0, result.stderr
    assert result.stdout == "population of 6 Asian countries in millions is 3530\n"
    assert result.stderr == ""


def test_argc_argv_and_string_v_preassignment_execute(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a\n", encoding="utf-8")
    second.write_text("b\n", encoding="utf-8")

    result = run_quawk(
        "-v",
        "x=hello",
        'BEGIN { print x; print ARGC; print ARGV[0]; print ARGV[1]; print ARGV[2] }',
        str(first),
        str(second),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"hello\n3\nquawk\n{first}\n{second}\n"
    assert result.stderr == ""


def test_environ_and_subsep_builtin_variables_execute() -> None:
    result = run_quawk(
        'BEGIN { print ENVIRON["QUAWK_TEST_ENV"]; print length(SUBSEP) }',
        env={"QUAWK_TEST_ENV": "present"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "present\n1\n"
    assert result.stderr == ""


def test_getline_main_string_updates_counters_without_replacing_current_record() -> None:
    result = run_quawk('{ print getline x; print NR ":" FNR ":" x ":" $0 ":" NF; exit }', stdin="a\nb c\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n2:2:b c:a:1\n"
    assert result.stderr == ""


def test_getline_main_record_replaces_current_record() -> None:
    result = run_quawk("{ print getline; print NR \":\" FNR \":\" NF \":\" $0; exit }", stdin="a\nb c\n")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n2:2:2:b c\n"
    assert result.stderr == ""


def test_getline_file_string_does_not_change_main_record_or_counters(tmp_path: Path) -> None:
    input_path = tmp_path / "getline.txt"
    input_path.write_text("u\nv\n", encoding="utf-8")

    result = run_quawk(
        f'{{ print getline x < "{input_path}"; print NR ":" FNR ":" x ":" $0 ":" NF; exit }}',
        stdin="a\n",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1:1:u:a:1\n"
    assert result.stderr == ""


def test_getline_file_record_replaces_current_record_without_changing_main_counters(tmp_path: Path) -> None:
    input_path = tmp_path / "getline.txt"
    input_path.write_text("u v\n", encoding="utf-8")

    result = run_quawk(
        f'{{ print getline < "{input_path}"; print NR ":" FNR ":" NF ":" $0; exit }}',
        stdin="a\n",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1:1:2:u v\n"
    assert result.stderr == ""


def test_close_resets_getline_file_streams(tmp_path: Path) -> None:
    input_path = tmp_path / "getline.txt"
    input_path.write_text("u\nv\n", encoding="utf-8")

    result = run_quawk(
        (
            f'BEGIN {{ print getline x < "{input_path}"; close("{input_path}"); '
            f'print getline x < "{input_path}"; print x }}'
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "1\n1\nu\n"
    assert result.stderr == ""
