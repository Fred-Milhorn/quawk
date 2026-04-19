# Agent Workflow Documentation Alignment Plan

This plan records the follow-on work to align `AGENTS.md` with the repository's
current contributor, testing, compatibility, and architecture documentation.

The goal is to make `AGENTS.md` useful as the first local workflow file a coding
agent reads, while keeping the broader docs as the detailed references for their
own domains.

## Why This Follow-On Exists

`AGENTS.md` captures the current `uv`-first command style, marker-based pytest
suites, and commit-message workflow. The surrounding docs now contain additional
rules that are important for coding agents but are either missing from
`AGENTS.md` or only implicit there.

Important missing or under-described areas:

- full bootstrap prerequisites, including LLVM command-line tools, editable dev
  install, submodule initialization, and reference-engine bootstrap
- static validation commands for formatting, linting, and typing
- compatibility reference policy for pinned One True Awk and pinned
  `gawk --posix`
- the architecture rule that claimed AWK semantics execute through the compiled
  backend/runtime path rather than a Python semantic fallback
- test and corpus decision rules for user-visible AWK behavior
- a compact source-of-truth map for which docs to update with each kind of
  change
- dirty-worktree and staging guidance that prevents unrelated user changes from
  being committed accidentally
- relative-link guidance for documentation changes
- stale references to `docs/agent-workflow.md` when the checked-in agent
  workflow file is currently `AGENTS.md`

## Desired Steady State

After this alignment:

- `AGENTS.md` is either the canonical agent workflow document or clearly points
  to the canonical replacement
- README and contributor links resolve to the actual agent workflow document
- coding agents can bootstrap, test, lint, type-check, and validate
  compatibility work without searching several docs first
- implementation guidance in `AGENTS.md` reflects the current compiled
  backend/runtime architecture
- doc update expectations are explicit enough that behavior changes update
  `SPEC.md`, `docs/design.md`, grammar/AST docs, roadmap, and changelog when
  relevant
- docs touched by the cleanup use relative links rather than absolute local
  filesystem links

## Proposed Cleanup Phases

### Phase 1: Resolve the agent workflow document path

Choose one stable location for agent workflow guidance.

Preferred options:

- keep `AGENTS.md` canonical and update README/contributor links to point to it
- or add `docs/agent-workflow.md` as a small shim that points to `../AGENTS.md`
  if the historical docs path should remain valid

Acceptance:

- repository docs no longer point readers at a missing agent workflow file
- the chosen path is named consistently in README and contributor guidance

### Phase 2: Expand setup and validation guidance

Add the missing setup and validation details to `AGENTS.md`.

Include:

- required LLVM tools: `lli`, `clang`, `llvm-as`, `llvm-link`, and `llc`
- editable dev install through `uv pip install -e .[dev]`
- submodule initialization through `git submodule update --init --recursive`
- upstream reference bootstrap through `uv run quawk-upstream bootstrap`
- static validation commands:
  - `uv run ruff check .`
  - `uv run mypy src`
  - `uv run yapf --diff --recursive src tests`

Acceptance:

- a coding agent can read `AGENTS.md` and know the normal bootstrap, test, lint,
  type-check, and formatting commands
- compatibility-specific setup is clearly separated from the default fast path

### Phase 3: Add testing and compatibility decision rules

Summarize the testing policy from `docs/testing.md` and `docs/compatibility.md`
inside `AGENTS.md`.

Include:

- add tests before behavior changes
- prefer corpus cases for user-visible AWK behavior
- prefer ordinary Python tests for parser shape, diagnostics, backend internals,
  and narrow CLI contracts
- use `pytest.mark.xfail` only for clear temporary expected failures
- treat pinned One True Awk as the primary reference
- treat pinned `gawk --posix` as the secondary reference
- do not use host `awk` as a compatibility reference
- classify persistent reference disagreements or upstream failures in the
  checked-in divergence metadata and companion notes

Acceptance:

- `AGENTS.md` gives agents enough policy context to add the right kind of test
  without re-reading every compatibility doc
- compatibility workflow language does not imply exhaustive upstream ingestion
  or GNU-extension parity

### Phase 4: Add architecture and implementation guardrails

Summarize the core implementation constraints from `docs/design.md` and
`POSIX.md`.

Include:

- Python lexes, parses, normalizes, lowers, and orchestrates LLVM tooling
- claimed AWK semantics should execute through the compiled backend/runtime
  path
- do not add Python semantic fallback for claimed behavior
- record-driven programs should use reusable IR and streaming runtime support
  rather than Python-side input materialization or per-input lowering
- public feature claims should stay aligned with compiled backend/runtime
  support and inspection behavior

Acceptance:

- `AGENTS.md` prevents future implementation work from reintroducing stale
  host-runtime fallback as a steady-state solution
- architecture guidance remains short and points to detailed docs for nuance

### Phase 5: Add doc update and changelog rules

Add a source-of-truth map to `AGENTS.md`.

Expected mapping:

- public feature claims: `SPEC.md`
- architecture, execution model, and CLI contract: `docs/design.md`
- concrete grammar: `docs/quawk.ebnf`
- implemented AST shape: `docs/quawk.asdl`
- active backlog and task completion: `docs/roadmap.md`
- user-visible behavior and release notes: `CHANGELOG.md`
- release process changes: `docs/release-checklist.md`
- compatibility policy and upstream decisions: `docs/compatibility.md`

Acceptance:

- behavior, CLI, compatibility, grammar, AST, release, and roadmap changes have
  obvious documentation targets
- user-visible changes do not bypass the changelog expectation

### Phase 6: Tighten git and documentation hygiene

Add explicit agent-safe workflow notes.

Include:

- inspect `git status --short` before staging
- do not stage unrelated user changes
- use `git add -A` only when the worktree is agent-owned or the staged scope has
  been verified
- keep documentation links relative
- avoid adding new absolute local filesystem links
- clean up absolute links in docs touched by this alignment when practical

Acceptance:

- `AGENTS.md` gives clear staging guidance for dirty worktrees
- docs touched during the cleanup do not introduce new absolute local paths

## Out Of Scope

This plan does not require:

- changing implementation behavior
- changing pytest marker definitions
- removing documentation-contract tests
- rewriting every existing planning document
- fixing every pre-existing absolute link in untouched docs

Those items can be handled by their own focused tasks if needed.

## Validation Direction

Because this is documentation-only work, validation should focus on the affected
documentation surface.

Recommended checks:

```sh
uv run pytest -m docs_contract
```

If the cleanup touches command guidance that could affect normal development
workflow, also run:

```sh
uv run pytest -q -m core
```

Before finishing the implementation wave, review:

```sh
git status --short
git diff --stat
git diff
```

## Acceptance Direction

The alignment is complete when:

- `AGENTS.md` includes setup, validation, testing, compatibility, architecture,
  doc-update, changelog, git-safety, and relative-link guidance
- README and contributing docs point to the actual agent workflow document
- touched docs avoid new absolute local filesystem links
- the roadmap names this work as its own phase with clear tasks and completion
  criteria
- relevant documentation checks pass or any skipped checks are explained
