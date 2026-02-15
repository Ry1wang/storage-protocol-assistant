"""Tests for the retrieval components (vector, keyword, hybrid search)."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.retrieval.keyword_search import KeywordSearch, _tokenize
from src.retrieval.hybrid_search import HybridSearch


# --- Tokenizer ---

class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_empty(self):
        assert _tokenize("") == []


# --- KeywordSearch ---

class TestKeywordSearch:

    def _make_store(self, chunks):
        store = Mock()
        store.get_all_chunks.return_value = chunks
        return store

    def _sample_chunks(self):
        return [
            {
                "chunk_id": "c1",
                "text": "eMMC device types and voltage ranges",
                "doc_id": "doc1",
                "page_numbers": [1],
                "section_title": "Device Types",
                "section_path": "Ch1 > Device Types",
                "chunk_type": "text",
            },
            {
                "chunk_id": "c2",
                "text": "UFS protocol command set overview",
                "doc_id": "doc2",
                "page_numbers": [5],
                "section_title": "Commands",
                "section_path": "Ch2 > Commands",
                "chunk_type": "text",
            },
            {
                "chunk_id": "c3",
                "text": "eMMC bus speed modes and timing",
                "doc_id": "doc1",
                "page_numbers": [10],
                "section_title": "Bus Speed",
                "section_path": "Ch3 > Bus Speed",
                "chunk_type": "text",
            },
        ]

    def test_search_returns_relevant(self):
        chunks = self._sample_chunks()
        store = self._make_store(chunks)
        ks = KeywordSearch(vector_store=store)

        results = ks.search("eMMC device", top_k=5)

        assert len(results) >= 1
        # c1 should rank highest (contains both "emmc" and "device")
        assert results[0]["chunk_id"] == "c1"

    def test_search_respects_top_k(self):
        chunks = self._sample_chunks()
        store = self._make_store(chunks)
        ks = KeywordSearch(vector_store=store)

        results = ks.search("eMMC", top_k=1)
        assert len(results) == 1

    def test_search_doc_id_filter(self):
        chunks = self._sample_chunks()
        store = self._make_store(chunks)
        ks = KeywordSearch(vector_store=store)

        results = ks.search("protocol", top_k=5, doc_id="doc2")
        for r in results:
            assert r["doc_id"] == "doc2"

    def test_search_empty_index(self):
        store = self._make_store([])
        ks = KeywordSearch(vector_store=store)

        results = ks.search("anything", top_k=5)
        assert results == []

    def test_rebuild_index(self):
        store = self._make_store([])
        ks = KeywordSearch(vector_store=store)
        ks.search("test")  # builds index

        # Now return chunks on rebuild
        store.get_all_chunks.return_value = self._sample_chunks()
        ks.rebuild_index()

        results = ks.search("eMMC", top_k=5)
        assert len(results) >= 1


# --- HybridSearch (RRF fusion) ---

class TestHybridSearch:

    def test_rrf_fusion_merges_both_sources(self):
        hs = HybridSearch.__new__(HybridSearch)
        hs.rrf_k = 60

        vector_results = [
            {"chunk_id": "c1", "text": "a", "doc_id": "d1", "page_numbers": [1],
             "section_title": "S1", "section_path": "S1", "score": 0.9},
            {"chunk_id": "c2", "text": "b", "doc_id": "d1", "page_numbers": [2],
             "section_title": "S2", "section_path": "S2", "score": 0.8},
        ]
        keyword_results = [
            {"chunk_id": "c3", "text": "c", "doc_id": "d1", "page_numbers": [3],
             "section_title": "S3", "section_path": "S3", "score": 5.0},
            {"chunk_id": "c1", "text": "a", "doc_id": "d1", "page_numbers": [1],
             "section_title": "S1", "section_path": "S1", "score": 3.0},
        ]

        fused = hs._reciprocal_rank_fusion(vector_results, keyword_results, top_k=10)

        chunk_ids = [r["chunk_id"] for r in fused]
        # c1 appears in both lists, should rank highest
        assert chunk_ids[0] == "c1"
        # All 3 unique chunks present
        assert set(chunk_ids) == {"c1", "c2", "c3"}

    def test_rrf_respects_top_k(self):
        hs = HybridSearch.__new__(HybridSearch)
        hs.rrf_k = 60

        results_a = [
            {"chunk_id": f"c{i}", "text": f"t{i}", "doc_id": "d1",
             "page_numbers": [i], "section_title": "S", "section_path": "S",
             "score": 1.0 - i * 0.1}
            for i in range(5)
        ]
        results_b = list(reversed(results_a))

        fused = hs._reciprocal_rank_fusion(results_a, results_b, top_k=2)
        assert len(fused) == 2


# --- RetrieverAgent reranking ---

class TestRetrieverAgentRerank:

    @patch("src.agents.retriever.HybridSearch")
    @patch("src.agents.retriever.QdrantVectorStore")
    def test_rerank_section_clustering(self, mock_qdrant, mock_hybrid):
        from src.agents.retriever import RetrieverAgent

        agent = RetrieverAgent(vector_store=mock_qdrant.return_value)

        results = [
            {"chunk_id": "c1", "text": "a", "score": 0.5,
             "section_path": "Ch1 > Intro", "section_title": "Intro",
             "doc_id": "d1", "page_numbers": [1]},
            {"chunk_id": "c2", "text": "b", "score": 0.5,
             "section_path": "Ch1 > Intro", "section_title": "Intro",
             "doc_id": "d1", "page_numbers": [2]},
            {"chunk_id": "c3", "text": "c", "score": 0.6,
             "section_path": "Ch2 > Other", "section_title": "Other",
             "doc_id": "d1", "page_numbers": [5]},
        ]

        reranked = agent._rerank_results("test query", results)

        # c1 and c2 share a section (count=2), so get 1.15x boost: 0.5*1.15=0.575
        # c3 is alone, no boost: 0.6*1.0=0.6
        # So c3 should still be first, but c1/c2 are boosted above their raw 0.5
        assert reranked[0]["chunk_id"] == "c3"
        assert reranked[1]["score"] > 0.5  # boosted

    @patch("src.agents.retriever.HybridSearch")
    @patch("src.agents.retriever.QdrantVectorStore")
    def test_rerank_empty(self, mock_qdrant, mock_hybrid):
        from src.agents.retriever import RetrieverAgent

        agent = RetrieverAgent(vector_store=mock_qdrant.return_value)
        assert agent._rerank_results("query", []) == []
