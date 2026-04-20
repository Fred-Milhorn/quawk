# Documentation-Test Cleanup Plan

This document records the follow-on cleanup to stop treating repository
documentation as a pytest-enforced contract.

This cleanup is now landed:

- dedicated `docs_contract` and `roadmap_contract` pytest surfaces are removed
- pure document-assertion pytest files are deleted
- mixed files keep executable or tooling checks while dropping exact repo-doc
  wording assertions
- contributor guidance no longer tells users to run document-test suites

The goal is not to remove useful engineering docs. The goal is to remove tests
whose primary purpose is asserting exact document text, and to reword project
guidance so tests are described as validating executable behavior rather than
repository prose.

## Why This Follow-On Exists

The repository currently mixes two different ideas:

- tests that validate parser, runtime, compatibility, and tooling behavior
- tests that assert exact wording in `SPEC.md`, `docs/design.md`,
  `docs/testing.md`, `docs/roadmap.md`, `docs/benchmark.md`, and related plan
  documents

That second category has grown into a dedicated test surface:

- `docs_contract`
- `roadmap_contract`

There is also a broader tail of feature-task tests that use document assertions
as completion receipts.

If the desired policy is "tests test the code, not the documents," that whole
layer needs to be removed coherently rather than one file at a time.

## Current Problem Shape

The current document-test coupling shows up in several places.

### 1. Dedicated pytest machinery

- `pyproject.toml` defines `docs_contract` and `roadmap_contract` markers
- `tests/conftest.py` auto-tags tests whose names contain `roadmap` and skips
  them by default unless `QUAWK_RUN_ROADMAP_TESTS=1`
- `AGENTS.md` and `docs/testing.md` tell contributors and agents to run these
  documentation-oriented suites

### 2. Pure document-assertion test files

Representative files that appear to exist only to pin document text include:

- `tests/test_t156_aot_contract_docs.py`
- `tests/test_t179_testing_surface_names.py`
- `tests/test_t180_testing_docs_and_commands.py`
- `tests/test_t182_corpus_harness_and_smoke_docs.py`
- `tests/test_t183_testing_workflow_audit.py`
- `tests/test_execution_model_docs.py`
- `tests/test_t295_local_scalar_rebaseline_docs.py`

These are likely deletion candidates rather than edit candidates.

### 3. Hybrid feature tests with document assertions mixed in

A larger set of tests reads repo docs while also covering code or workflow
behavior. Those files need selective pruning so real executable coverage is not
accidentally deleted along with the doc assertions.

Representative examples include tests that read:

- `SPEC.md`
- `docs/design.md`
- `docs/roadmap.md`
- `docs/compatibility.md`
- `docs/benchmark.md`

### 4. Policy language that implies docs are test-enforced contract

Representative wording to rework:

- `docs/testing.md` describing roadmap state as tracked without a "custom
  validator" while the repo still effectively validates roadmap text through
  pytest
- `AGENTS.md` commands and examples that explicitly include `docs_contract` and
  `roadmap_contract`
- roadmap/process wording that uses doc assertions as evidence that a task is
  complete

## Desired Steady State

After this cleanup:

- tests validate executable behavior, compatibility behavior, and engineering
  tooling behavior
- the repo no longer has dedicated documentation-only pytest surfaces
- roadmap and planning docs remain useful planning artifacts, but they are not
  enforced by exact-string pytest assertions
- contributor guidance no longer tells people to run document-test suites or
  implies that documentation itself is a checked contract

This does **not** require deleting all "source of truth" phrasing everywhere.
That wording can remain where it describes product inputs or data ownership,
such as:

- grammar files defining parsing rules
- ASDL files defining AST structure
- the benchmark harness defining how measurements are produced

The cleanup target is narrower: remove wording that implies repository prose is
itself validated by tests.

## Proposed Cleanup Phases

### Phase 1: Audit document assertions

Produce an explicit inventory of tests that assert repository document text.

Split them into two buckets:

- pure document-assertion tests that can be deleted outright
- hybrid tests that need selective pruning

This phase should leave a concrete file list before any mass deletion starts.

### Phase 2: Remove dedicated document-test surfaces

Delete the explicit documentation-test machinery:

- remove `docs_contract` and `roadmap_contract` markers from `pyproject.toml`
- remove collection-time auto-tagging and default skipping in `tests/conftest.py`
- remove commands and examples that instruct users to run doc-only pytest
  surfaces

The result should be that there is no longer a first-class pytest suite whose
purpose is document validation.

### Phase 3: Delete pure document tests

Delete test files whose primary purpose is asserting exact text in repo docs.

The expectation is that most of the dedicated `*_docs.py`, `*_rebaseline.py`,
and roadmap-text receipt files in this category will disappear entirely.

### Phase 4: Prune hybrid tests

For mixed files:

- remove document-text assertions
- keep any still-useful executable, parser, runtime, or tooling assertions
- split tests only when needed to preserve non-doc behavior coverage cleanly

The guiding rule is that surviving tests should still make sense if every repo
doc string changed tomorrow.

### Phase 5: Reword policy and workflow docs

Update repository guidance so it no longer implies docs are pytest-enforced
contract.

Likely files:

- `AGENTS.md`
- `docs/testing.md`
- possibly `docs/roadmap.md`
- any workflow docs or examples that recommend doc-test commands

This phase should also remove wording that treats roadmap/document assertions as
normal completion evidence for implementation tasks.

### Phase 6: Rebaseline test workflow

After the cleanup:

- recommended pytest commands should cover executable-behavior suites only
- contributor docs should describe tests as validating code behavior
- the remaining test tree should be free of dedicated doc-validation surfaces

## Out Of Scope

This cleanup does **not** automatically require:

- rewriting every planning document in the repo
- deleting useful architecture or roadmap documentation
- removing all references to docs from tests when the test is actually checking a
  machine-consumed artifact
- changing compatibility manifests or other data files that are genuinely part
  of a test harness

## Risks And Guardrails

### Risk: deleting real coverage hidden inside mixed files

Some task files mix:

- runtime or routing assertions
- roadmap or spec wording assertions

Guardrail:

- prune mixed files surgically
- only delete a whole file when it is clearly document-only

### Risk: leaving stale contributor workflow instructions

If the pytest markers are removed but docs still tell users to run them, the
repo becomes confusing.

Guardrail:

- remove the code-level machinery and the workflow guidance in the same cleanup
  wave

### Risk: replacing one metadata system with another

The goal is not to invent a new manifest that tracks document cleanup status.

Guardrail:

- keep the cleanup ordinary and code-reviewable: tests, config, and docs change
  together with no new validator layer

## Acceptance Direction

This cleanup should end with:

- no dedicated `docs_contract` or `roadmap_contract` pytest surface
- no tests whose primary purpose is asserting exact text in repository
  documentation
- no contributor guidance that instructs users to run documentation-test suites
- no workflow wording that implies repository prose is a pytest-enforced
  contract
- remaining tests that clearly validate executable behavior, compatibility, or
  tooling behavior rather than document wording

That is the cleaner steady state implied by the desired policy.
