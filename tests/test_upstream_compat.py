from __future__ import annotations

from pathlib import Path

from quawk.compat import upstream_compat


def test_upstream_projects_use_pinned_sources_and_wrapper_paths(tmp_path: Path) -> None:
    onetrueawk, gawk = upstream_compat.upstream_projects(tmp_path)

    assert onetrueawk.source_dir == tmp_path / "third_party" / "onetrueawk"
    assert onetrueawk.work_dir == tmp_path / "build" / "upstream" / "work" / "onetrueawk"
    assert onetrueawk.binary_relpath == Path("a.out")
    assert onetrueawk.wrapper_path == tmp_path / "build" / "upstream" / "bin" / "one-true-awk"

    assert gawk.source_dir == tmp_path / "third_party" / "gawk"
    assert gawk.work_dir == tmp_path / "build" / "upstream" / "work" / "gawk"
    assert gawk.binary_relpath == Path("gawk")
    assert gawk.wrapper_path == tmp_path / "build" / "upstream" / "bin" / "gawk"


def test_copy_source_tree_skips_git_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "copy"
    source_dir.mkdir()
    (source_dir / ".git").write_text("gitdir: /tmp/demo\n", encoding="utf-8")
    (source_dir / "README").write_text("demo\n", encoding="utf-8")
    (source_dir / "nested").mkdir()
    (source_dir / "nested" / "file.txt").write_text("ok\n", encoding="utf-8")

    upstream_compat.copy_source_tree(source_dir, destination_dir)

    assert not (destination_dir / ".git").exists()
    assert (destination_dir / "README").read_text(encoding="utf-8") == "demo\n"
    assert (destination_dir / "nested" / "file.txt").read_text(encoding="utf-8") == "ok\n"


def test_build_commands_match_expected_bootstrap_steps(tmp_path: Path) -> None:
    onetrueawk, gawk = upstream_compat.upstream_projects(tmp_path)

    assert upstream_compat.build_commands(onetrueawk) == [("make",)]
    assert upstream_compat.build_commands(gawk) == [
        (
            str(gawk.work_dir / "configure"),
            "--disable-nls",
            "--without-readline",
        ),
        ("make", "-C", "support", "libsupport.a"),
        ("make", "gawk"),
    ]


def test_stabilize_gawk_generated_files_touches_checked_in_generated_artifacts(tmp_path: Path) -> None:
    work_dir = tmp_path / "gawk"
    (work_dir / "extension").mkdir(parents=True)

    generated_paths = (
        work_dir / "aclocal.m4",
        work_dir / "configure",
        work_dir / "Makefile.in",
        work_dir / "configh.in",
        work_dir / "extension" / "aclocal.m4",
        work_dir / "extension" / "configure",
        work_dir / "extension" / "Makefile.in",
    )
    for path in generated_paths:
        path.write_text("generated\n", encoding="utf-8")

    before = {path: path.stat().st_mtime_ns for path in generated_paths}

    upstream_compat.stabilize_gawk_generated_files(work_dir)

    after = {path: path.stat().st_mtime_ns for path in generated_paths}
    for path in generated_paths:
        assert after[path] >= before[path]
