from __future__ import annotations

import subprocess
from pathlib import Path

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

    assert "one-true-awk:p.3" in case_ids
    assert "one-true-awk:p.21" in case_ids
    assert "one-true-awk:p.39" in case_ids
    assert "one-true-awk:p.46" in case_ids
    assert "gawk:assignnumfield" in case_ids
    assert "gawk:assignnumfield2" in case_ids
    assert "gawk:exit2" in case_ids
    assert "gawk:numsubstr" in case_ids
    assert "gawk:strfieldnum" in case_ids
    assert "one-true-awk:p.1" not in case_ids
    assert "one-true-awk:p.43" not in case_ids


def test_run_upstream_case_executes_in_isolated_temp_dir(monkeypatch) -> None:
    selection = next(
        selection for selection in upstream_inventory.load_upstream_selection_manifest()
        if (selection.suite, selection.case_id) == ("one-true-awk", "p.12")
    )
    case = upstream_suite.load_upstream_case(selection)
    seen_cwds: list[Path] = []

    def fake_run(command, *, capture_output, text, check, cwd):
        assert capture_output is True
        assert text is True
        assert check is False
        workdir = Path(cwd)
        seen_cwds.append(workdir)
        assert workdir.is_dir()
        assert workdir.name.startswith("quawk-upstream-")
        assert workdir != upstream_inventory.REPO_ROOT
        (workdir / "tempbig").write_text("generated\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(upstream_suite.subprocess, "run", fake_run)

    result = upstream_suite.run_upstream_case(case, engine="quawk")

    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert len(seen_cwds) == 1
    assert not seen_cwds[0].exists()
