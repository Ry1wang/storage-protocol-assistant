"""Black-box tests for the end-to-end RAG pipeline."""

import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import SAMPLE_CHUNKS, _make_search_result


# ---------------------------------------------------------------------------
# Helper: create RAGPipeline with all agents mocked
# ---------------------------------------------------------------------------

def _make_pipeline(
    route_type="factual",
    route_strategy="vector",
    search_results=None,
    answer_text="The answer is 3.3V [1].",
    confidence=0.85,
):
    """Build a RAGPipeline with fully mocked agents."""

    if search_results is None:
        search_results = [
            _make_search_result(SAMPLE_CHUNKS[0], 0.85),
            _make_search_result(SAMPLE_CHUNKS[1], 0.78),
        ]

    # Mock router
    mock_router = MagicMock()
    mock_router.route.return_value = {
        "query": "test query",
        "query_type": route_type,
        "confidence": 1.0,
        "reasoning": f"Classified as {route_type}",
        "retrieval_strategy": route_strategy,
        "search_params": {"top_k": 10, "min_score": None, "filters": {}},
        "usage": {"prompt_tokens": 100, "completion_tokens": 10,
                  "total_tokens": 110, "latency": 0.3},
    }

    # Mock retriever
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = {
        "results": search_results,
        "context": "Mocked context with [1] and [2].",
        "metadata": {
            "strategy": route_strategy,
            "num_results": len(search_results),
            "top_score": search_results[0]["score"] if search_results else 0.0,
            "latency": 0.5,
        },
    }

    # Mock generator
    mock_generator = MagicMock()
    mock_generator.generate.return_value = {
        "answer": answer_text,
        "citations": [
            {
                "number": 1,
                "section_title": "CSD Register",
                "section_path": "7.1 CSD Register",
                "page_numbers": [45],
                "text_preview": "The Card-Specific Data...",
                "score": 0.85,
                "doc_id": "emmc_51",
            }
        ],
        "confidence": confidence,
        "metadata": {
            "model": "deepseek-reasoner",
            "query_type": route_type,
            "num_sources": len(search_results),
            "num_citations_used": 1,
            "usage": {"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700},
            "latency": 2.0,
        },
    }

    with patch("src.agents.rag_pipeline.get_query_router", return_value=mock_router), \
         patch("src.agents.rag_pipeline.get_retriever_agent", return_value=mock_retriever), \
         patch("src.agents.rag_pipeline.get_answer_generator", return_value=mock_generator):
        from src.agents.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline()

    return pipeline, mock_router, mock_retriever, mock_generator


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFullPipelineSuccess:

    def test_returns_complete_response(self):
        pipeline, _, _, _ = _make_pipeline()
        response = pipeline.process("What is the CSD register?")

        assert "query_id" in response
        assert "answer" in response
        assert "citations" in response
        assert "confidence" in response
        assert "metadata" in response

    def test_metadata_completeness(self):
        pipeline, _, _, _ = _make_pipeline()
        response = pipeline.process("What is the CSD register?")

        meta = response["metadata"]
        assert "query_type" in meta
        assert "retrieval_strategy" in meta
        assert "total_latency" in meta
        assert "token_usage" in meta


class TestStrategyOverride:

    def test_vector_override(self):
        pipeline, router, retriever, _ = _make_pipeline(route_strategy="hybrid")
        response = pipeline.process("query", strategy_override="vector")

        # Retriever should be called with "vector" not "hybrid"
        call_kwargs = retriever.retrieve.call_args
        assert call_kwargs.kwargs.get("strategy") == "vector" or \
               (call_kwargs[1].get("strategy") if len(call_kwargs) > 1 else None) == "vector"
        assert response["metadata"]["retrieval_strategy"] == "vector"

    def test_hybrid_override(self):
        pipeline, _, retriever, _ = _make_pipeline(route_strategy="vector")
        response = pipeline.process("query", strategy_override="hybrid")

        assert response["metadata"]["retrieval_strategy"] == "hybrid"


class TestParameterOverrides:

    def test_top_k_override(self):
        pipeline, _, retriever, _ = _make_pipeline()
        pipeline.process("query", top_k=5)

        call_kwargs = retriever.retrieve.call_args
        # top_k should appear in the search_params passed via **search_params
        assert "5" in str(call_kwargs)

    def test_min_score_override(self):
        pipeline, _, retriever, _ = _make_pipeline()
        pipeline.process("query", min_score=0.8)

        call_kwargs = retriever.retrieve.call_args
        assert "0.8" in str(call_kwargs)


class TestErrorHandling:

    def test_pipeline_error_returns_error_dict(self):
        pipeline, _, retriever, _ = _make_pipeline()
        retriever.retrieve.side_effect = RuntimeError("Connection failed")

        response = pipeline.process("query")

        assert "error" in response["answer"].lower() or "error" in str(response.get("metadata", {}))
        assert response["confidence"] == 0.0

    def test_empty_retrieval_results(self):
        pipeline, _, _, gen = _make_pipeline(search_results=[])
        gen.generate.return_value = {
            "answer": "I cannot answer this based on the provided context.",
            "citations": [],
            "confidence": 0.0,
            "metadata": {
                "model": "deepseek-reasoner",
                "query_type": "factual",
                "num_sources": 0,
                "num_citations_used": 0,
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                "latency": 1.0,
            },
        }

        response = pipeline.process("query about nonexistent topic")
        assert response["confidence"] == 0.0


class TestBatchProcessing:

    def test_processes_multiple_queries(self):
        pipeline, _, _, _ = _make_pipeline()
        queries = ["query 1", "query 2", "query 3"]
        responses = pipeline.process_batch(queries)

        assert len(responses) == 3
        for r in responses:
            assert "query_id" in r
            assert "answer" in r
