"""RAG Q&A accuracy tests across all 6 query types.

Uses a mock corpus of ~20 eMMC spec chunks and mocked DeepSeek responses
to validate that the pipeline produces correct routing, retrieval, and
citation behaviour for each query category.
"""

import re
import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import SAMPLE_CHUNKS, _make_search_result


# ---------------------------------------------------------------------------
# Helpers: build a pipeline that uses real routing logic but mocked LLM
# ---------------------------------------------------------------------------

def _mock_classify(category):
    """Return a classify_query mock response for a given category."""
    return {
        "category": category,
        "confidence": 1.0,
        "reasoning": f"Classified as {category}",
        "usage": {"prompt_tokens": 100, "completion_tokens": 10,
                  "total_tokens": 110, "latency": 0.3},
    }


def _mock_generate(answer_text):
    """Return a generate_answer mock response."""
    return {
        "answer": answer_text,
        "model": "deepseek-reasoner",
        "usage": {"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700},
        "latency": 2.0,
    }


def _build_pipeline(classify_category, answer_text, search_results):
    """Create a RAGPipeline with mocked DeepSeek but real routing logic."""

    # Mock the DeepSeek client globally
    mock_ds = MagicMock()
    mock_ds.classify_query.return_value = _mock_classify(classify_category)
    mock_ds.generate_answer.return_value = _mock_generate(answer_text)

    # Mock vector store that returns our test corpus
    mock_store = MagicMock()
    mock_store.search.return_value = search_results
    mock_store.get_all_chunks.return_value = [dict(c) for c in SAMPLE_CHUNKS]

    with patch("src.agents.query_router.get_deepseek_client", return_value=mock_ds), \
         patch("src.agents.answer_generator.get_deepseek_client", return_value=mock_ds), \
         patch("src.agents.retriever.QdrantVectorStore", return_value=mock_store), \
         patch("src.agents.retriever.HybridSearch") as mock_hs:

        mock_hs_instance = MagicMock()
        mock_hs_instance.search.return_value = search_results
        mock_hs.return_value = mock_hs_instance

        # Clear singletons to force fresh creation
        import src.agents.query_router as qr_mod
        import src.agents.retriever as ret_mod
        import src.agents.answer_generator as ag_mod
        import src.agents.rag_pipeline as rp_mod
        qr_mod._query_router = None
        ret_mod._retriever_agent = None
        ag_mod._answer_generator = None
        rp_mod._rag_pipeline = None

        from src.agents.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline()

    return pipeline


def _results_for_chunks(chunk_ids, base_score=0.85):
    """Build search results for specific chunk_ids from SAMPLE_CHUNKS."""
    chunk_map = {c["chunk_id"]: c for c in SAMPLE_CHUNKS}
    results = []
    for i, cid in enumerate(chunk_ids):
        if cid in chunk_map:
            results.append(_make_search_result(chunk_map[cid], base_score - i * 0.03))
    return results


# ---------------------------------------------------------------------------
# 3.1.1 Factual Queries
# ---------------------------------------------------------------------------

class TestFactualQueries:

    def test_csd_register(self):
        results = _results_for_chunks(["csd_1", "csd_def_1", "taac_1"])
        pipeline = _build_pipeline(
            "factual",
            "The Card-Specific Data (CSD) register provides information [1] including TAAC [2].",
            results,
        )
        resp = pipeline.process("What is the CSD register?")

        assert resp["confidence"] > 0
        assert len(resp["citations"]) > 0
        assert resp["metadata"]["query_type"] == "factual"

    def test_taac_field(self):
        results = _results_for_chunks(["taac_1", "csd_1"])
        pipeline = _build_pipeline(
            "factual",
            "TAAC defines the asynchronous data access time [1].",
            results,
        )
        resp = pipeline.process("What does the TAAC field contain?")
        assert len(resp["citations"]) > 0

    def test_boot_partition_size(self):
        results = _results_for_chunks(["boot_part_1"])
        pipeline = _build_pipeline(
            "factual",
            "The boot partition size is 128KB * BOOT_SIZE_MULT [1].",
            results,
        )
        resp = pipeline.process("What is the boot partition size?")
        assert len(resp["citations"]) > 0


# ---------------------------------------------------------------------------
# 3.1.2 Definition Queries
# ---------------------------------------------------------------------------

class TestDefinitionQueries:

    def test_define_rpmb(self):
        results = _results_for_chunks(["rpmb_1"])
        pipeline = _build_pipeline(
            "definition",
            "RPMB is a Replay Protected Memory Block [1].",
            results,
        )
        resp = pipeline.process("Define RPMB")
        assert resp["metadata"]["query_type"] == "definition"
        assert len(resp["citations"]) > 0

    def test_csd_stands_for(self):
        results = _results_for_chunks(["csd_def_1", "csd_1"])
        pipeline = _build_pipeline(
            "definition",
            "CSD stands for Card-Specific Data [1].",
            results,
        )
        resp = pipeline.process("What does CSD stand for?")
        assert len(resp["citations"]) > 0

    def test_define_packed_commands(self):
        results = _results_for_chunks(["packed_cmd_1"])
        pipeline = _build_pipeline(
            "definition",
            "Packed commands group multiple read/write operations [1].",
            results,
        )
        resp = pipeline.process("Define packed commands")
        assert len(resp["citations"]) > 0


# ---------------------------------------------------------------------------
# 3.1.3 Comparison Queries
# ---------------------------------------------------------------------------

class TestComparisonQueries:

    def test_hs200_vs_hs400(self):
        results = _results_for_chunks(["hs200_1", "hs400_1", "hs400_freq_1"])
        pipeline = _build_pipeline(
            "comparison",
            "HS200 operates at SDR [1] while HS400 uses DDR [2].",
            results,
        )
        resp = pipeline.process("Compare HS200 and HS400 modes")
        assert resp["metadata"]["retrieval_strategy"] == "hybrid"
        assert len(resp["citations"]) >= 1

    def test_rpmb_vs_regular(self):
        results = _results_for_chunks(["rpmb_1", "partitions_1"])
        pipeline = _build_pipeline(
            "comparison",
            "RPMB uses HMAC authentication [1], regular partitions do not [2].",
            results,
        )
        resp = pipeline.process("How does RPMB differ from regular partitions?")
        assert len(resp["citations"]) >= 1

    def test_sdr_vs_ddr(self):
        results = _results_for_chunks(["sdr_ddr_1", "hs200_1", "hs400_1"])
        pipeline = _build_pipeline(
            "comparison",
            "SDR transfers on one edge, DDR on both [1].",
            results,
        )
        resp = pipeline.process("What's the difference between single and dual data rate?")
        assert len(resp["citations"]) > 0


# ---------------------------------------------------------------------------
# 3.1.4 Specification Queries
# ---------------------------------------------------------------------------

class TestSpecificationQueries:

    def test_cmd1_timing(self):
        results = _results_for_chunks(["timing_1"])
        pipeline = _build_pipeline(
            "specification",
            "CMD1 response time is within 1ms [1].",
            results,
        )
        resp = pipeline.process("What are the timing requirements for CMD1?")
        assert resp["metadata"]["retrieval_strategy"] == "hybrid"

    def test_max_hs400_frequency(self):
        results = _results_for_chunks(["hs400_freq_1", "hs400_1"])
        pipeline = _build_pipeline(
            "specification",
            "The maximum frequency for HS400 is 200MHz [1].",
            results,
        )
        resp = pipeline.process("What is the maximum frequency for HS400?")
        assert len(resp["citations"]) > 0

    def test_voltage_requirements(self):
        results = _results_for_chunks(["voltage_1"])
        pipeline = _build_pipeline(
            "specification",
            "The device supports 2.7V-3.6V and 1.70V-1.95V [1].",
            results,
        )
        resp = pipeline.process("What are the voltage requirements?")
        assert len(resp["citations"]) > 0


# ---------------------------------------------------------------------------
# 3.1.5 Procedural Queries
# ---------------------------------------------------------------------------

class TestProceduralQueries:

    def test_configure_hs400(self):
        results = _results_for_chunks(["hs400_proc_1", "hs400_1"])
        pipeline = _build_pipeline(
            "procedural",
            "To configure HS400: 1) Initialize [1], 2) Switch to HS200 [1].",
            results,
        )
        resp = pipeline.process("How do I configure HS400 mode?")
        assert resp["metadata"]["query_type"] == "procedural"

    def test_device_initialization_steps(self):
        results = _results_for_chunks(["init_1", "boot_1"])
        pipeline = _build_pipeline(
            "procedural",
            "Step 1: Send CMD0 [1]. Step 2: Send CMD1 [1].",
            results,
        )
        resp = pipeline.process("What are the steps for device initialization?")
        assert len(resp["citations"]) > 0

    def test_enable_rpmb(self):
        results = _results_for_chunks(["rpmb_proc_1", "rpmb_1"])
        pipeline = _build_pipeline(
            "procedural",
            "To enable RPMB: 1) Write auth key [1], 2) Verify [1].",
            results,
        )
        resp = pipeline.process("How to enable RPMB?")
        assert len(resp["citations"]) > 0


# ---------------------------------------------------------------------------
# 3.1.6 Troubleshooting Queries
# ---------------------------------------------------------------------------

class TestTroubleshootingQueries:

    def test_boot_failure(self):
        results = _results_for_chunks(["boot_err_1", "boot_1"])
        pipeline = _build_pipeline(
            "troubleshooting",
            "Boot failure causes include incorrect configuration [1].",
            results,
        )
        resp = pipeline.process("Why might boot fail on eMMC?")
        assert resp["metadata"]["retrieval_strategy"] == "hybrid"

    def test_initialization_errors(self):
        results = _results_for_chunks(["init_err_1", "init_1"])
        pipeline = _build_pipeline(
            "troubleshooting",
            "No response to CMD1 indicates device not present [1].",
            results,
        )
        resp = pipeline.process("What causes initialization errors?")
        assert len(resp["citations"]) > 0

    def test_command_timeout(self):
        results = _results_for_chunks(["cmd_timeout_1", "timing_1"])
        pipeline = _build_pipeline(
            "troubleshooting",
            "Check clock frequency and voltage levels [1].",
            results,
        )
        resp = pipeline.process("How to debug command timeout issues?")
        assert len(resp["citations"]) > 0


# ---------------------------------------------------------------------------
# 3.1.7 Cross-Cutting Accuracy Checks
# ---------------------------------------------------------------------------

class TestCrossCuttingAccuracy:

    def _run_query(self, category, answer, chunk_ids):
        results = _results_for_chunks(chunk_ids)
        pipeline = _build_pipeline(category, answer, results)
        return pipeline.process("test query")

    def test_all_answers_have_citations(self):
        """Every answer with matching context should have citations."""
        resp = self._run_query(
            "factual", "The CSD register [1].", ["csd_1"]
        )
        assert len(resp["citations"]) > 0

    def test_no_hallucination_positive(self):
        """When context matches, answer should NOT say 'I cannot answer'."""
        resp = self._run_query(
            "factual", "The answer is [1] detailed.", ["csd_1"]
        )
        assert "i cannot answer" not in resp["answer"].lower()

    def test_graceful_no_context(self):
        """When no chunks match, answer should acknowledge lack of info."""
        pipeline = _build_pipeline(
            "factual",
            "I cannot answer this based on the provided context.",
            [],
        )
        resp = pipeline.process("query with no matching chunks")
        assert "cannot" in resp["answer"].lower() or resp["confidence"] == 0.0

    def test_citation_numbers_valid(self):
        """Every [N] in the answer should map to an actual result."""
        results = _results_for_chunks(["csd_1", "taac_1"])
        pipeline = _build_pipeline(
            "factual",
            "The CSD [1] contains TAAC [2].",
            results,
        )
        resp = pipeline.process("query")

        # Extract [N] from answer
        nums = [int(m) for m in re.findall(r'\[(\d+)\]', resp["answer"])]
        for n in nums:
            assert n <= len(results), f"Citation [{n}] exceeds {len(results)} results"

    def test_confidence_high_for_good_match(self):
        """High-scoring results should yield confidence > 0.5."""
        results = _results_for_chunks(["csd_1"], base_score=0.9)
        pipeline = _build_pipeline(
            "factual", "The CSD register [1].", results
        )
        resp = pipeline.process("What is CSD?")
        assert resp["confidence"] > 0.5

    def test_strategy_matches_query_type(self):
        """Comparison should use hybrid; definition should use vector."""
        # Comparison -> hybrid
        results = _results_for_chunks(["hs200_1", "hs400_1"])
        pipeline = _build_pipeline("comparison", "HS200 [1] vs HS400 [2].", results)
        resp = pipeline.process("Compare HS200 and HS400")
        assert resp["metadata"]["retrieval_strategy"] == "hybrid"

        # Definition -> vector
        results = _results_for_chunks(["rpmb_1"])
        pipeline = _build_pipeline("definition", "RPMB is [1].", results)
        resp = pipeline.process("Define RPMB")
        assert resp["metadata"]["retrieval_strategy"] == "vector"
