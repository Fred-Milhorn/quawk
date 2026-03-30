from __future__ import annotations

from pathlib import Path

import pytest

from quawk import corpus

pytestmark = pytest.mark.compat


def make_case() -> corpus.CorpusCase:
    case_dir = Path("/tmp/corpus-case")
    return corpus.CorpusCase(
        id="demo",
        description="demo case",
        case_dir=case_dir,
        program_path=case_dir / "program.awk",
        input_path=None,
        input_paths=(),
        input_operands=(),
        operand_separator=False,
        cli_args=(),
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
    input_path = Path("/tmp/input.txt")

    assert corpus.build_engine_command("quawk", program_path) == ["quawk", "-f", str(program_path)]
    assert corpus.build_engine_command("one-true-awk", program_path) == [
        str(corpus.upstream_projects()[0].wrapper_path),
        "-f",
        str(program_path),
    ]
    assert corpus.build_engine_command("gawk-posix", program_path) == [
        str(corpus.upstream_projects()[1].wrapper_path),
        "--posix",
        "-f",
        str(program_path),
    ]
    assert corpus.build_engine_command("quawk", program_path, cli_args=("-F:",), input_operands=(str(input_path), )) == [
        "quawk",
        "-F:",
        "-f",
        str(program_path),
        str(input_path),
    ]


def test_build_engine_command_supports_operand_separator_and_literal_operands() -> None:
    program_path = Path("/tmp/program.awk")
    input_path = Path("/tmp/--records.txt")

    assert corpus.build_engine_command(
        "quawk",
        program_path,
        input_operands=("-", str(input_path)),
        operand_separator=True,
    ) == [
        "quawk",
        "-f",
        str(program_path),
        "--",
        "-",
        str(input_path),
    ]


def test_engine_executable_uses_pinned_reference_wrappers() -> None:
    assert corpus.engine_executable("quawk") == "quawk"
    assert corpus.engine_executable("one-true-awk").endswith("build/upstream/bin/one-true-awk")
    assert corpus.engine_executable("gawk-posix").endswith("build/upstream/bin/gawk")


def test_is_engine_available_checks_quawk_on_path_and_references_on_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_which(name: str) -> str | None:
        seen.append(name)
        if name == "quawk":
            return "/tmp/quawk"
        return None

    def fake_is_file(self: Path) -> bool:
        return self.name == "gawk"

    monkeypatch.setattr(corpus.shutil, "which", fake_which)
    monkeypatch.setattr(Path, "is_file", fake_is_file)

    assert corpus.is_engine_available("quawk") is True
    assert corpus.is_engine_available("gawk-posix") is True
    assert corpus.is_engine_available("one-true-awk") is False
    assert seen == ["quawk"]


def test_missing_engines_reports_engine_names_not_host_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(name: str) -> str | None:
        assert name == "quawk"
        return "/tmp/quawk"

    def fake_is_file(self: Path) -> bool:
        return self.name == "one-true-awk"

    monkeypatch.setattr(corpus.shutil, "which", fake_which)
    monkeypatch.setattr(Path, "is_file", fake_is_file)

    assert corpus.missing_engines() == ("gawk-posix",)


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


def test_load_case_reads_optional_args_and_input_files(tmp_path: Path) -> None:
    case_dir = tmp_path / "with-args"
    case_dir.mkdir()
    (case_dir / "program.awk").write_text("{ print $2 }\n", encoding="utf-8")
    (case_dir / "stdin.txt").write_text("unused\n", encoding="utf-8")
    (case_dir / "one.txt").write_text("a:b\n", encoding="utf-8")
    (case_dir / "two.txt").write_text("c:d\n", encoding="utf-8")
    (case_dir / "expected.stdout").write_text("b\nd\n", encoding="utf-8")
    (case_dir / "case.toml").write_text(
        '\n'.join(
            [
                'id = "with_args"',
                'description = "demo"',
                'program = "program.awk"',
                'input = "stdin.txt"',
                'inputs = ["one.txt", "two.txt"]',
                'args = ["-F:"]',
                'tags = ["supported"]',
                "",
                "[expect]",
                'stdout = "expected.stdout"',
                "exit = 0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    case = corpus.load_case(case_dir / "case.toml")

    assert case.cli_args == ("-F:",)
    assert case.input_paths == (case_dir / "one.txt", case_dir / "two.txt")
    assert case.input_operands == (str(case_dir / "one.txt"), str(case_dir / "two.txt"))
    assert case.input_text() == "unused\n"


def test_load_case_reads_optional_operands_and_separator(tmp_path: Path) -> None:
    case_dir = tmp_path / "with-operands"
    case_dir.mkdir()
    (case_dir / "program.awk").write_text("{ print FILENAME }\n", encoding="utf-8")
    (case_dir / "stdin.txt").write_text("from-stdin\n", encoding="utf-8")
    (case_dir / "--records.txt").write_text("alpha beta\n", encoding="utf-8")
    (case_dir / "expected.stdout").write_text("--\n", encoding="utf-8")
    (case_dir / "case.toml").write_text(
        '\n'.join(
            [
                'id = "with_operands"',
                'description = "demo"',
                'program = "program.awk"',
                'input = "stdin.txt"',
                'operands = ["-", "--records.txt"]',
                'operand_separator = true',
                'tags = ["supported"]',
                "",
                "[expect]",
                'stdout = "expected.stdout"',
                "exit = 0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    case = corpus.load_case(case_dir / "case.toml")

    assert case.input_paths == ()
    assert case.input_operands == ("-", str(case_dir / "--records.txt"))
    assert case.operand_separator is True
    assert case.input_text() == "from-stdin\n"


def test_load_divergence_manifest_accepts_empty_manifest(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    case_dir = corpus_root / "demo"
    case_dir.mkdir(parents=True)
    (case_dir / "program.awk").write_text('BEGIN { print "ok" }\n', encoding="utf-8")
    (case_dir / "expected.stdout").write_text("ok\n", encoding="utf-8")
    (case_dir / "case.toml").write_text(
        '\n'.join(
            [
                'id = "demo"',
                'description = "demo"',
                'program = "program.awk"',
                'tags = ["supported"]',
                "",
                "[expect]",
                'stdout = "expected.stdout"',
                "exit = 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (corpus_root / "divergences.toml").write_text("# no classified divergences yet\n", encoding="utf-8")

    assert corpus.load_divergence_manifest(root=corpus_root) == {}


def test_load_divergence_manifest_rejects_unknown_case_ids(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    case_dir = corpus_root / "demo"
    case_dir.mkdir(parents=True)
    (case_dir / "program.awk").write_text('BEGIN { print "ok" }\n', encoding="utf-8")
    (case_dir / "expected.stdout").write_text("ok\n", encoding="utf-8")
    (case_dir / "case.toml").write_text(
        '\n'.join(
            [
                'id = "demo"',
                'description = "demo"',
                'program = "program.awk"',
                'tags = ["supported"]',
                "",
                "[expect]",
                'stdout = "expected.stdout"',
                "exit = 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (corpus_root / "divergences.toml").write_text(
        '\n'.join(
            [
                "[[divergence]]",
                'case_id = "missing"',
                'classification = "implementation-defined"',
                'summary = "demo"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown corpus case"):
        corpus.load_divergence_manifest(root=corpus_root)


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


def test_differential_validation_errors_require_classified_reference_disagreements() -> None:
    case = make_case()
    result = corpus.DifferentialCaseResult(
        case=case,
        results_by_engine={
            "quawk": make_result("quawk", stdout="ok\n"),
            "one-true-awk": make_result("one-true-awk", stdout="left\n"),
            "gawk-posix": make_result("gawk-posix", stdout="right\n"),
        },
    )

    errors = corpus.differential_validation_errors(result, {})

    assert errors[0] == "unclassified reference disagreement"


def test_differential_validation_errors_reject_stale_divergence_entries() -> None:
    case = make_case()
    result = corpus.DifferentialCaseResult(
        case=case,
        results_by_engine={
            "quawk": make_result("quawk", stdout="ok\n"),
            "one-true-awk": make_result("one-true-awk", stdout="ok\n"),
            "gawk-posix": make_result("gawk-posix", stdout="ok\n"),
        },
    )
    divergences = {
        "demo": corpus.DivergenceEntry(
            case_id="demo",
            classification="implementation-defined",
            summary="stale",
        )
    }

    assert corpus.differential_validation_errors(result, divergences) == [
        "stale divergence manifest entry: implementation-defined - stale"
    ]


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
    monkeypatch.setattr(
        corpus,
        "run_case_differential",
        lambda case: corpus.DifferentialCaseResult(case, {}, ("one-true-awk",)),
    )
    monkeypatch.setattr(corpus, "missing_engines", lambda engines=corpus.DEFAULT_DIFFERENTIAL_ENGINES: ("one-true-awk",))
    monkeypatch.setattr(corpus, "load_divergence_manifest", lambda root=None, path=None: {})

    exit_code = corpus.main(["--differential"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == "SKIP demo\n"
    assert captured.err == "corpus: missing differential engines: one-true-awk\n"


def test_main_differential_allows_classified_ref_disagreements_without_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = make_case()
    monkeypatch.setattr(corpus, "select_cases", lambda case_ids: [case])
    monkeypatch.setattr(corpus, "missing_engines", lambda engines=corpus.DEFAULT_DIFFERENTIAL_ENGINES: ())
    monkeypatch.setattr(
        corpus,
        "load_divergence_manifest",
        lambda root=None, path=None: {
            "demo": corpus.DivergenceEntry(
                case_id="demo",
                classification="implementation-defined",
                summary="demo divergence",
            )
        },
    )
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
    assert captured.out == "REF-DISAGREE demo [implementation-defined]\n"
    assert captured.err == ""


def test_main_differential_fails_unclassified_ref_disagreements(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = make_case()
    monkeypatch.setattr(corpus, "select_cases", lambda case_ids: [case])
    monkeypatch.setattr(corpus, "missing_engines", lambda engines=corpus.DEFAULT_DIFFERENTIAL_ENGINES: ())
    monkeypatch.setattr(corpus, "load_divergence_manifest", lambda root=None, path=None: {})
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

    assert exit_code == 1
    assert captured.out == "REF-DISAGREE demo\n"
    assert captured.err == ""
