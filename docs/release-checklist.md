# Release Checklist

Use this checklist before cutting a `quawk` release.

## Scope

- Confirm `SPEC.md` matches the user-visible feature set.
- Confirm `CHANGELOG.md` has an `Unreleased` entry for user-visible behavior,
  compatibility, CLI, packaging, and documentation changes.
- Confirm `docs/roadmap.md` reflects the current active phase and does not leave
  completed roadmap tasks in `Immediate Next Tasks`.
- Confirm compatibility-impacting changes are documented in
  `docs/compatibility.md`.

## Validation

Run the relevant local checks with the repo-managed toolchain:

```sh
uv run pytest -q -m core
uv run pytest -q -m conformance
uv run pytest -m compat_reference
uv run pytest -m compat_corpus
uv run ruff check .
uv run mypy src
uv run yapf --diff --recursive src tests
```

Required compatibility suites should fail, not skip, when the pinned reference
engines are missing.

## Artifact Review

- Verify no generated benchmark output, local NOAA data, temporary files, or
  build products are staged.
- Verify `git diff --cached --stat` contains only release-scope changes.
- Verify the final commit message and release notes describe compatibility and
  user-visible behavior clearly.
