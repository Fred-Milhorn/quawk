# Release Checklist

This checklist is the versioned release workflow for `quawk`.

Use it when cutting a release candidate or final release. Keep changes to this
file reviewed in-repo so release process updates stay visible.

## Scope

This checklist currently covers:
- pre-release validation
- release metadata and changelog updates
- artifact and tag publication steps

It does not define:
- a long-term support policy
- binary packaging beyond the current Python package and source tree workflow

## Release Steps

1. Confirm the target version and release type.
   - Decide whether the cut is a release candidate or final release.
   - Confirm the version string that will ship.
2. Update versioned release metadata.
   - Update `src/quawk/__init__.py` if the release changes the package version.
   - Verify any matching version references in docs or packaging metadata.
3. Update [CHANGELOG.md](/Users/fred/dev/quawk/CHANGELOG.md).
   - Move completed `Unreleased` items into a new dated version section.
   - Keep the changelog focused on user-visible behavior, compatibility, CLI, and toolchain changes.
4. Re-read the public contract docs.
   - Verify [README.md](/Users/fred/dev/quawk/README.md), [SPEC.md](/Users/fred/dev/quawk/SPEC.md), and [docs/design.md](/Users/fred/dev/quawk/docs/design.md) agree on the shipped surface.
   - Verify [docs/roadmap.md](/Users/fred/dev/quawk/docs/roadmap.md) no longer advertises completed tasks as immediate next work.
5. Run the release validation checks.
   - `uv run pytest -q`
   - `uv run pytest -q -m smoke`
   - `uv run ruff check .`
   - `uv run mypy src`
   - `uv run yapf --diff --recursive src tests`
6. Check reference-environment assumptions.
   - Confirm the documented Python baseline still matches the tested environment.
   - Confirm LLVM command-line tools required by the current runtime are available and documented.
7. Review open release blockers.
   - No unexpected failing tests.
   - No stale `xfail` reasons in the release-smoke baseline.
   - No unclassified or stale compatibility divergences in the checked-in manifests.
   - Any allowed upstream compatibility divergences are still reflected in [docs/compatibility.md](/Users/fred/dev/quawk/docs/compatibility.md).
8. Create the release commit and tag.
   - Commit the version/changelog/doc updates.
   - Create an annotated tag for the release version.
9. Publish and record the result.
   - Push the release commit and tag.
   - If a release page or package upload is used, link the tag and published artifacts from the release notes.

## Sign-off

Before publishing, confirm:
- the release version is intentional
- the changelog describes the shipped delta
- the documented supported surface matches the tested one
- the release validation checks passed on the target tree
