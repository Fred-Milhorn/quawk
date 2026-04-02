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
                '    qk_print_string(runtime, "hello");',
                "    qk_print_number(runtime, 1.0);",
                '    qk_print_string_fragment(runtime, "x");',
                "    qk_print_number_fragment(runtime, 2.0);",
                "    qk_print_output_separator(runtime);",
                "    qk_print_output_record_separator(runtime);",
                '    FILE *output = qk_open_output(runtime, "out.txt", 1);',
                '    qk_write_output_string(output, "y");',
                "    qk_write_output_number(runtime, output, 3.0);",
                "    qk_write_output_separator(runtime, output);",
                "    qk_write_output_record_separator(runtime, output);",
                '    (void)qk_close_output(runtime, "out.txt");',
                '    (void)qk_regex_match_current_record(runtime, "foo");',
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
