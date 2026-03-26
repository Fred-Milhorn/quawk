from __future__ import annotations

from pathlib import Path

import pytest

from quawk import corpus


def make_case() -> corpus.CorpusCase:
    case_dir = Path("/tmp/corpus-case")
    return corpus.CorpusCase(
        id="demo",
        description="demo case",
        case_dir=case_dir,
        program_path=case_dir / "program.awk",
        input_path=None,
        expected_stdout_path=None,
        expected_stderr_path=None,
        expected_exit=0,
        tags=(),
        xfail_reason=None,
    )


def make_result(
    engine: corpus.EngineName,
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> corpus.NormalizedCorpusResult:
    return corpus.NormalizedCorpusResult(
        engine=engine,
        command=(engine, "-f", "program.awk"),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_build_engine_command_uses_expected_process_prefixes() -> None:
    program_path = Path("/tmp/program.awk")

    assert corpus.build_engine_command("quawk", program_path) == ["quawk", "-f", str(program_path)]
    assert corpus.build_engine_command("one-true-awk", program_path) == ["awk", "-f", str(program_path)]
    assert corpus.build_engine_command("gawk-posix", program_path) == ["gawk", "--posix", "-f", str(program_path)]


def test_is_engine_available_uses_resolved_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_which(name: str) -> str | None:
        seen.append(name)
        if name == "gawk":
            return "/usr/bin/gawk"
        return None

    monkeypatch.setattr(corpus.shutil, "which", fake_which)

    assert corpus.is_engine_available("gawk-posix") is True
    assert corpus.is_engine_available("one-true-awk") is False
    assert seen == ["gawk", "awk"]


def test_normalize_result_only_normalizes_line_endings() -> None:
    raw = corpus.CorpusResult(
        engine="quawk",
        command=("quawk", "-f", "program.awk"),
        returncode=1,
        stdout="a\r\nb\r\n",
        stderr="x\r\ny\r\n",
    )

    normalized = corpus.normalize_result(raw)

    assert normalized.returncode == 1
    assert normalized.stdout == "a\nb\n"
    assert normalized.stderr == "x\ny\n"


def test_differential_result_reports_pass_when_references_and_quawk_match() -> None:
    case = make_case()
    agreed = make_result("one-true-awk", stdout="ok\n")
    result = corpus.DifferentialCaseResult(
        case=case,
        results_by_engine={
            "quawk": make_result("quawk", stdout="ok\n"),
            "one-true-awk": agreed,
            "gawk-posix": make_result("gawk-posix", stdout="ok\n"),
        },
    )

    assert result.references_agree() is True
    assert result.quawk_matches_references() is True
    assert result.status() == "PASS"


def test_differential_result_reports_fail_when_references_agree_and_quawk_differs() -> None:
    case = make_case()
    result = corpus.DifferentialCaseResult(
        case=case,
        results_by_engine={
            "quawk": make_result("quawk", stdout="bad\n"),
            "one-true-awk": make_result("one-true-awk", stdout="ok\n"),
            "gawk-posix": make_result("gawk-posix", stdout="ok\n"),
        },
    )

    assert result.references_agree() is True
    assert result.quawk_matches_references() is False
    assert result.status() == "FAIL"
    assert any("quawk: exit=0 stdout='bad\\n'" in line for line in result.detail_lines())


def test_differential_result_reports_reference_disagreement() -> None:
    case = make_case()
    result = corpus.DifferentialCaseResult(
        case=case,
        results_by_engine={
            "quawk": make_result("quawk", stdout="ok\n"),
            "one-true-awk": make_result("one-true-awk", stdout="left\n"),
            "gawk-posix": make_result("gawk-posix", stdout="right\n"),
        },
    )

    assert result.references_agree() is False
    assert result.status() == "REF-DISAGREE"


def test_run_case_differential_reports_missing_engines_without_running(monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case()

    monkeypatch.setattr(corpus, "missing_engines", lambda engines=corpus.DEFAULT_DIFFERENTIAL_ENGINES: ("gawk-posix",))

    def fail_run_case_for_engines(*args: object, **kwargs: object) -> dict[corpus.EngineName, corpus.NormalizedCorpusResult]:
        raise AssertionError("run_case_for_engines should not be called when engines are missing")

    monkeypatch.setattr(corpus, "run_case_for_engines", fail_run_case_for_engines)

    result = corpus.run_case_differential(case)

    assert result.status() == "SKIP"
    assert result.missing_engines == ("gawk-posix",)


def test_run_case_for_engines_normalizes_each_engine_once(monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case()
    seen: list[corpus.EngineName] = []

    def fake_run_case(run_case_arg: corpus.CorpusCase, engine: corpus.EngineName = "quawk") -> corpus.CorpusResult:
        assert run_case_arg is case
        seen.append(engine)
        return corpus.CorpusResult(
            engine=engine,
            command=(engine, "-f", "program.awk"),
            returncode=0,
            stdout="x\r\n",
            stderr="",
        )

    monkeypatch.setattr(corpus, "run_case", fake_run_case)

    results = corpus.run_case_for_engines(case)

    assert seen == ["quawk", "one-true-awk", "gawk-posix"]
    assert results["quawk"].stdout == "x\n"


def test_main_differential_returns_nonzero_and_reports_missing_engines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = make_case()
    monkeypatch.setattr(corpus, "select_cases", lambda case_ids: [case])
    monkeypatch.setattr(corpus, "run_case_differential", lambda case: corpus.DifferentialCaseResult(case, {}, ("awk",)))
    monkeypatch.setattr(corpus, "missing_engines", lambda engines=corpus.DEFAULT_DIFFERENTIAL_ENGINES: ("awk",))

    exit_code = corpus.main(["--differential"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == "SKIP demo\n"
    assert captured.err == "corpus: missing differential engines: awk\n"


def test_main_differential_passes_ref_disagreements_without_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = make_case()
    monkeypatch.setattr(corpus, "select_cases", lambda case_ids: [case])
    monkeypatch.setattr(corpus, "missing_engines", lambda engines=corpus.DEFAULT_DIFFERENTIAL_ENGINES: ())
    monkeypatch.setattr(
        corpus,
        "run_case_differential",
        lambda case: corpus.DifferentialCaseResult(
            case=case,
            results_by_engine={
                "quawk": make_result("quawk", stdout="q\n"),
                "one-true-awk": make_result("one-true-awk", stdout="a\n"),
                "gawk-posix": make_result("gawk-posix", stdout="b\n"),
            },
        ),
    )

    exit_code = corpus.main(["--differential"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "REF-DISAGREE demo\n"
    assert captured.err == ""
