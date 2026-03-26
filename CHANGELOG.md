# Changelog

All notable user-visible changes to `quawk` should be recorded in this file.

Format conventions:
- keep entries concise and release-focused
- group changes by release version
- keep unreleased work in the `Unreleased` section until cut
- prefer user-visible behavior, compatibility, CLI, packaging, and documentation changes over internal refactors

## Unreleased

### Added
- Public feature matrix in `SPEC.md`.
- Versioned release checklist in `docs/release-checklist.md`.
- Release-smoke baseline coverage for the supported CLI path and release artifacts.

### Changed
- CLI help now documents stable run-path behavior for `-f`, `--`, and `-` stdin operands.
- Compatibility coverage now uses a seeded supported corpus plus a checked-in divergence manifest.

## 0.1.0

Initial public implementation milestone.
