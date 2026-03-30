from __future__ import annotations

from quawk import upstream_inventory, upstream_suite


def test_load_upstream_case_for_onetrueawk_program_file_uses_compare_inputs() -> None:
    selection = next(
        selection for selection in upstream_inventory.load_upstream_selection_manifest()
        if (selection.suite, selection.case_id) == ("one-true-awk", "p.12")
    )

    case = upstream_suite.load_upstream_case(selection)

    assert case.id == "one-true-awk:p.12"
    assert case.oracle == "reference-agreement"
    assert case.program_path == selection.path
    assert case.input_operands == (
        str(selection.path.parent / "test.countries"),
        str(selection.path.parent / "test.countries"),
    )
    assert case.expectation is None


def test_load_upstream_case_for_gawk_ok_fixture_reads_expectation() -> None:
    selection = next(
        selection for selection in upstream_inventory.load_upstream_selection_manifest()
        if (selection.suite, selection.case_id) == ("gawk", "assignnumfield2")
    )

    case = upstream_suite.load_upstream_case(selection)

    assert case.id == "gawk:assignnumfield2"
    assert case.oracle == "expected-output"
    assert case.input_operands == ()
    assert case.expectation is not None
    assert case.expectation.comparable_fields() == (0, "1\n", "")


def test_selected_upstream_cases_return_only_runnable_entries() -> None:
    case_ids = [case.id for case in upstream_suite.selected_upstream_cases()]

    assert case_ids == [
        "one-true-awk:p.12",
        "one-true-awk:p.13",
        "gawk:assignnumfield",
        "gawk:assignnumfield2",
    ]
