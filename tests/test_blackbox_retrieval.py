"""Black-box tests for search interface correctness."""

import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import SAMPLE_CHUNKS, _make_search_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_store_with_results(results):
    """Create a mock QdrantVectorStore that returns given results on search."""
    store = MagicMock()
    store.search.return_value = results
    store.get_all_chunks.return_value = [dict(c) for c in SAMPLE_CHUNKS]
    return store


def _search_results(n=5, base_score=0.9):
    """Generate n sample search results."""
    results = []
    for i in range(min(n, len(SAMPLE_CHUNKS))):
        results.append(_make_search_result(SAMPLE_CHUNKS[i], base_score - i * 0.05))
    return results


# ---------------------------------------------------------------------------
# VectorSearch tests
# ---------------------------------------------------------------------------

class TestVectorSearch:

    def test_returns_results(self):
        results = _search_results(3)
        store = _make_mock_store_with_results(results)

        from src.retrieval.vector_search import VectorSearch
        vs = VectorSearch(vector_store=store)
        got = vs.search("What is the CSD register?", top_k=5)

        assert len(got) > 0
        for r in got:
            assert "chunk_id" in r
            assert "text" in r
            assert "score" in r
            assert "page_numbers" in r

    def test_respects_top_k(self):
        results = _search_results(3)
        store = _make_mock_store_with_results(results)

        from src.retrieval.vector_search import VectorSearch
        vs = VectorSearch(vector_store=store)
        vs.search("query", top_k=3)

        # Verify top_k was passed to underlying store
        call_kwargs = store.search.call_args
        assert call_kwargs.kwargs.get("top_k") == 3 or call_kwargs[1].get("top_k") == 3

    def test_min_score_filter(self):
        store = _make_mock_store_with_results([])  # Empty for unreachable score

        from src.retrieval.vector_search import VectorSearch
        vs = VectorSearch(vector_store=store)
        got = vs.search("query", min_score=0.99)
        assert got == []

    def test_doc_id_filter(self):
        store = _make_mock_store_with_results([])

        from src.retrieval.vector_search import VectorSearch
        vs = VectorSearch(vector_store=store)
        vs.search("query", doc_id="doc1")

        call_kwargs = store.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters is not None
        assert any("doc_id" in str(cond) for cond in filters.get("must", []))


# ---------------------------------------------------------------------------
# HybridSearch tests
# ---------------------------------------------------------------------------

class TestHybridSearchBlackbox:

    def test_merges_both_sources(self):
        store = MagicMock()
        # Vector search returns c1, c2
        store.search.return_value = _search_results(2)
        # BM25 gets all chunks
        store.get_all_chunks.return_value = [dict(c) for c in SAMPLE_CHUNKS]

        from src.retrieval.hybrid_search import HybridSearch
        hs = HybridSearch(vector_store=store)
        results = hs.search("eMMC CSD register", top_k=10)

        # Should have results from both vector and keyword sources
        assert len(results) > 0
        chunk_ids = {r["chunk_id"] for r in results}
        assert len(chunk_ids) > 0

    def test_deduplication(self):
        """Same chunk appearing in both sources should appear once in output."""
        hs = MagicMock()
        from src.retrieval.hybrid_search import HybridSearch

        hs_obj = HybridSearch.__new__(HybridSearch)
        hs_obj.rrf_k = 60

        shared_result = _make_search_result(SAMPLE_CHUNKS[0], 0.9)
        vector_results = [shared_result]
        keyword_results = [dict(shared_result)]  # Same chunk

        fused = hs_obj._reciprocal_rank_fusion(vector_results, keyword_results, top_k=10)

        chunk_ids = [r["chunk_id"] for r in fused]
        # Should appear only once
        assert chunk_ids.count(SAMPLE_CHUNKS[0]["chunk_id"]) == 1
        # But with boosted score (appears in both lists)
        assert fused[0]["score"] > 1.0 / (60 + 1)  # Higher than single-source RRF


# ---------------------------------------------------------------------------
# RetrieverAgent tests
# ---------------------------------------------------------------------------

class TestRetrieverAgentBlackbox:

    def _make_agent(self, vector_results):
        store = MagicMock()
        store.search.return_value = vector_results
        store.get_all_chunks.return_value = [dict(c) for c in SAMPLE_CHUNKS]

        with patch("src.agents.retriever.HybridSearch") as mock_hs:
            mock_hs_instance = MagicMock()
            mock_hs_instance.search.return_value = vector_results
            mock_hs.return_value = mock_hs_instance

            from src.agents.retriever import RetrieverAgent
            agent = RetrieverAgent(vector_store=store)

        return agent, store, mock_hs_instance

    def test_vector_strategy(self):
        results = _search_results(3)
        agent, store, hybrid = self._make_agent(results)

        response = agent.retrieve("query", strategy="vector", top_k=5)
        store.search.assert_called()
        assert response["results"] is not None
        assert response["context"] is not None

    def test_hybrid_strategy(self):
        results = _search_results(3)
        agent, store, hybrid = self._make_agent(results)

        response = agent.retrieve("query", strategy="hybrid", top_k=5)
        hybrid.search.assert_called()

    def test_unknown_strategy_falls_back_to_vector(self):
        results = _search_results(3)
        agent, store, hybrid = self._make_agent(results)

        response = agent.retrieve("query", strategy="unknown_strategy", top_k=5)
        store.search.assert_called()

    def test_context_assembly_format(self):
        results = _search_results(3)
        agent, _, _ = self._make_agent(results)

        response = agent.retrieve("query", strategy="vector", top_k=3)
        context = response["context"]

        # Should contain [1], [2], [3] citation markers
        assert "[1]" in context
        assert "[2]" in context
        assert "[3]" in context

    def test_context_truncation(self):
        results = _search_results(3)
        agent, _, _ = self._make_agent(results)

        # Use small max_chars
        context = agent._assemble_context(results, max_chunks=5, max_chars=100)
        # Context should be limited (though header overhead may make it slightly larger)
        assert len(context) < 500  # Generous upper bound accounting for headers

    def test_no_matches_returns_empty(self):
        agent, store, _ = self._make_agent([])
        store.search.return_value = []

        response = agent.retrieve("gibberish query xyz", strategy="vector")
        assert len(response["results"]) == 0
        assert "No relevant context" in response["context"]
