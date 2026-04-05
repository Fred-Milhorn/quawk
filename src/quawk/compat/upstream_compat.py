"""Bootstrap pinned upstream awk reference builds for compatibility work."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final


@dataclass(frozen=True)
class UpstreamProject:
    """Pinned upstream source plus its local build/wrapper paths."""

    name: str
    source_dir: Path
    work_dir: Path
    binary_relpath: Path
    wrapper_path: Path


REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]


def upstream_projects(root: Path | None = None) -> tuple[UpstreamProject, ...]:
    """Return the pinned upstream reference projects."""
    base = REPO_ROOT if root is None else root
    build_root = base / "build" / "upstream"
    bin_dir = build_root / "bin"
    return (
        UpstreamProject(
            name="one-true-awk",
            source_dir=base / "third_party" / "onetrueawk",
            work_dir=build_root / "work" / "onetrueawk",
            binary_relpath=Path("a.out"),
            wrapper_path=bin_dir / "one-true-awk",
        ),
        UpstreamProject(
            name="gawk",
            source_dir=base / "third_party" / "gawk",
            work_dir=build_root / "work" / "gawk",
            binary_relpath=Path("gawk"),
            wrapper_path=bin_dir / "gawk",
        ),
    )


def validate_sources(projects: tuple[UpstreamProject, ...]) -> list[str]:
    """Return missing-source validation errors."""
    errors: list[str] = []
    for project in projects:
        if not project.source_dir.is_dir():
            errors.append(f"missing source tree: {project.source_dir}")
            continue
        if not (project.source_dir / ".git").exists():
            errors.append(f"expected initialized git submodule: {project.source_dir}")
    return errors


def copy_source_tree(source_dir: Path, destination_dir: Path) -> None:
    """Copy one upstream source tree into an ignored local work directory."""
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, destination_dir, ignore=_ignore_submodule_metadata)


def _ignore_submodule_metadata(directory: str, names: list[str]) -> set[str]:
    """Skip nested git metadata when mirroring a submodule tree."""
    ignored: set[str] = set()
    if ".git" in names:
        ignored.add(".git")
    return ignored


def build_commands(project: UpstreamProject) -> list[tuple[str, ...]]:
    """Return the build commands for one pinned upstream project."""
    if project.name == "one-true-awk":
        return [("make",)]
    if project.name == "gawk":
        return [
            (
                str(project.work_dir / "configure"),
                "--disable-nls",
                "--without-readline",
            ),
            ("make", "-C", "support", "libsupport.a"),
            ("make", "gawk"),
        ]
    raise AssertionError(f"unsupported upstream project: {project.name}")


def prepare_work_tree(project: UpstreamProject) -> None:
    """Normalize copied upstream trees before running their build steps."""
    if project.name != "gawk":
        return
    stabilize_gawk_generated_files(project.work_dir)


def stabilize_gawk_generated_files(work_dir: Path) -> None:
    """Keep gawk's checked-in generated files newer than their git checkout deps.

    The pinned gawk submodule is a git checkout, not a release tarball. In that
    layout some checked-in `m4/*.m4` inputs can be slightly newer than the
    generated `aclocal.m4`/`configure`/`Makefile.in` files, which makes plain
    `make` try to rerun autotools utilities that are not otherwise required for
    the compatibility bootstrap.
    """
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
        path.touch()


def bootstrap(root: Path | None = None) -> None:
    """Build the pinned upstream references into ignored local wrapper paths."""
    projects = upstream_projects(root)
    errors = validate_sources(projects)
    if errors:
        detail = "\n".join(errors)
        raise RuntimeError(f"cannot bootstrap upstream references:\n{detail}")

    projects[0].wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    for project in projects:
        copy_source_tree(project.source_dir, project.work_dir)
        prepare_work_tree(project)
        for command in build_commands(project):
            run_command(command, cwd=project.work_dir)

        built_binary = project.work_dir / project.binary_relpath
        if not built_binary.is_file():
            raise RuntimeError(f"{project.name} build did not produce expected binary: {built_binary}")
        project.wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built_binary, project.wrapper_path)


def run_command(command: tuple[str, ...], cwd: Path) -> None:
    """Run one external build command."""
    subprocess.run(command, cwd=cwd, check=True)


def main(argv: list[str] | None = None) -> int:
    """Run the upstream compatibility bootstrap CLI."""
    parser = argparse.ArgumentParser(
        prog="upstream_compat.py",
        description="Bootstrap pinned One True Awk and gawk builds under build/upstream.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("bootstrap", help="Build local reference wrappers from third_party submodules.")
    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        bootstrap()
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
