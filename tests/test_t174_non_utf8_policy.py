from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_t174_spec_documents_the_byte_tolerant_input_policy() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "| Input data decoding policy | implemented |" in spec_text
    assert "file-backed `getline` follow a byte-tolerant text policy" in spec_text
    assert "AWK source files still load as UTF-8 text" in spec_text


def test_t174_posix_plan_records_the_policy_and_t_nf_reclassification() -> None:
    posix_text = (ROOT / "POSIX.md").read_text(encoding="utf-8")

    assert "### T-174 Byte-Oriented Input Policy Result" in posix_text
    assert "preserve undecodable bytes with" in posix_text
    assert "`t.NF` skip reason was stale" in posix_text
    assert "remaining `NF`-driven" in posix_text


def test_t174_roadmap_marks_the_policy_task_done() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-174 | P15 | P1 | Decide and implement the non-UTF-8 input policy | T-167 |" in roadmap_text
    assert "| T-174 | P15 | P1 | Decide and implement the non-UTF-8 input policy | T-167 | Reviewed cases such as `t.NF` either run under a documented byte-oriented policy or are explicitly marked out-of-scope in the public contract | done |" in roadmap_text
