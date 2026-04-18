from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_t295_benchmark_docs_record_the_post_p34_rebaseline_honestly() -> None:
    benchmark_text = (ROOT / "docs" / "benchmark.md").read_text(encoding="utf-8")

    assert "`T-295` post-`T-294` rebaseline note" in benchmark_text
    assert "geometric mean speedup (`optimized` vs `unoptimized`, `end_to_end`): `0.94x`" in benchmark_text
    assert "geometric mean speedup (`optimized` vs `unoptimized`, `lli_only`): `1.00x`" in benchmark_text
    assert "`branch_rewrite_loop`: `1.02x`" in benchmark_text
    assert "`scalar_fold_loop`: `0.99x`" in benchmark_text


def test_t295_roadmap_marks_the_rebaseline_done_with_honest_acceptance_text() -> None:
    roadmap_text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "| T-295 | P34 | P2 | Rebaseline optimized-vs-unoptimized benchmarks and docs for local-scalar promotion | T-293, T-294 | The optimized-vs-unoptimized suite is rerun against the post-`T-294` lowering, and roadmap/benchmark docs record the current `lli_only` outcome honestly, including when the suite-level geometric mean remains flat | done |" in roadmap_text
    assert "- no active `P34` tasks remain; any further LLVM-optimization work should start" in roadmap_text
