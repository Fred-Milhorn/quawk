# Runtime support layer tests.
# These cases pin the package-owned C runtime ABI and ensure the small support
# library compiles cleanly before the backend is rewired to use it.

from __future__ import annotations

import subprocess
from pathlib import Path

from quawk import runtime_support


def test_runtime_support_files_exist() -> None:
    assert runtime_support.runtime_header_path().is_file()
    assert runtime_support.runtime_source_path().is_file()


def test_runtime_support_compiles_to_object(tmp_path: Path) -> None:
    object_path = runtime_support.compile_runtime_object(tmp_path)

    assert object_path.is_file()


def test_runtime_support_header_and_abi_link_cleanly(tmp_path: Path) -> None:
    harness_path = tmp_path / "runtime_harness.c"
    executable_path = tmp_path / "runtime_harness"
    harness_path.write_text(
        "\n".join(
            [
                '#include "qk_runtime.h"',
                "",
                "int main(void)",
                "{",
                "    qk_runtime *runtime = qk_runtime_create(0, (char **)0, (const char *)0);",
                "    (void)qk_next_record(runtime);",
                "    (void)qk_get_field(runtime, 0);",
                '    qk_set_field_string(runtime, 0, "field0");',
                '    qk_print_string(runtime, "hello");',
                "    qk_print_number(runtime, 1.0);",
                '    qk_print_string_fragment(runtime, "x");',
                "    qk_print_number_fragment(runtime, 2.0);",
                "    qk_print_output_separator(runtime);",
                "    qk_print_output_record_separator(runtime);",
                '    (void)qk_getline_main_record(runtime);',
                '    (void)qk_getline_main_string(runtime, (const char **)0);',
                '    (void)qk_getline_file_record(runtime, "input.txt");',
                '    (void)qk_getline_file_string(runtime, "input.txt", (const char **)0);',
                '    FILE *output = qk_open_output(runtime, "out.txt", 1);',
                '    qk_write_output_string(output, "y");',
                "    qk_write_output_number(runtime, output, 3.0);",
                "    qk_write_output_separator(runtime, output);",
                "    qk_write_output_record_separator(runtime, output);",
                '    (void)qk_close_output(runtime, "out.txt");',
                '    (void)qk_regex_match_current_record(runtime, "foo");',
                '    (void)qk_capture_string_arg(runtime, "captured");',
                '    (void)qk_parse_number_text("12.5x");',
                '    (void)qk_index(runtime, "banana", "na");',
                '    (void)qk_match(runtime, "banana", "ana");',
                '    (void)qk_substitute(runtime, "a", "A", "banana", 1, (const char **)0);',
                '    (void)qk_sprintf(runtime, "%s:%d", 0, (const double *)0, (const char *const *)0);',
                '    (void)qk_tolower(runtime, "AbC");',
                '    (void)qk_toupper(runtime, "AbC");',
                "    (void)qk_atan2(0.0, -1.0);",
                "    (void)qk_cos(0.0);",
                "    (void)qk_exp(1.0);",
                "    (void)qk_int_builtin(-3.9);",
                "    (void)qk_log(1.0);",
                "    (void)qk_rand(runtime);",
                "    (void)qk_sin(0.0);",
                "    (void)qk_sqrt(9.0);",
                "    (void)qk_srand0(runtime);",
                "    (void)qk_srand1(runtime, 1.0);",
                '    (void)qk_system(runtime, "exit 0");',
                '    qk_array_set_string(runtime, "a", "k", "v");',
                "    qk_runtime_destroy(runtime);",
                "    return 0;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            runtime_support.find_clang(),
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(runtime_support.runtime_source_path()),
            str(harness_path),
            "-I",
            str(runtime_support.runtime_directory()),
            "-o",
            str(executable_path),
        ],
        check=True,
    )

    assert executable_path.is_file()
