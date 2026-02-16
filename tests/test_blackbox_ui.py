"""Black-box tests for Streamlit UI process_query() and helpers."""

import pytest
from unittest.mock import patch, MagicMock
import uuid


# ---------------------------------------------------------------------------
# Helper: Mock streamlit session state
# ---------------------------------------------------------------------------

class FakeSessionState(dict):
    """Dict that also supports attribute access like st.session_state."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def _make_session_state(use_llm=True, strategy="auto", top_k=10, min_score=None):
    state = FakeSessionState()
    state["use_llm"] = use_llm
    state["retrieval_strategy"] = strategy
    state["top_k"] = top_k
    state["min_score"] = min_score
    state["qdrant_client"] = MagicMock()
    state["sqlite_client"] = MagicMock()
    return state


def _mock_pipeline_response(answer="According to [1], the value is 3.3V.",
                            citations=None, confidence=0.85):
    if citations is None:
        citations = [{
            "number": 1,
            "section_title": "CSD Register",
            "section_path": "7.1 CSD Register",
            "page_numbers": [45],
            "text_preview": "The Card-Specific Data...",
            "score": 0.85,
            "doc_id": "emmc_51",
        }]
    return {
        "query_id": str(uuid.uuid4()),
        "query": "test query",
        "answer": answer,
        "citations": citations,
        "confidence": confidence,
        "metadata": {
            "query_type": "factual",
            "retrieval_strategy": "vector",
            "num_chunks_retrieved": 3,
            "num_citations_used": len(citations),
            "top_retrieval_score": 0.85,
            "model": "deepseek-reasoner",
            "total_latency": 3.0,
            "routing_latency": 0.3,
            "retrieval_latency": 0.5,
            "generation_latency": 2.0,
            "token_usage": {"prompt_tokens": 500, "completion_tokens": 200},
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLLMMode:

    @patch("app.get_rag_pipeline")
    @patch("app.st")
    def test_returns_formatted_response(self, mock_st, mock_get_pipeline):
        mock_st.session_state = _make_session_state(use_llm=True)

        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = _mock_pipeline_response()
        mock_get_pipeline.return_value = mock_pipeline

        from app import process_query
        result = process_query("What is the CSD register?")

        assert "answer" in result
        assert "citations" in result
        assert "metadata" in result
        assert result["confidence"] == 0.85


class TestSimpleMode:

    @patch("app.st")
    def test_returns_raw_results(self, mock_st):
        state = _make_session_state(use_llm=False)

        # Mock vector store search results
        state["qdrant_client"].search.return_value = [
            {
                "chunk_id": "c1",
                "text": "Sample result text about CSD register.",
                "doc_id": "emmc_51",
                "page_numbers": [45],
                "section_title": "CSD Register",
                "section_path": "7.1 CSD",
                "score": 0.85,
            }
        ]
        mock_st.session_state = state

        from app import process_query
        result = process_query("What is CSD?")

        assert "simple retrieval result" in result["answer"].lower()

    @patch("app.st")
    def test_no_results_message(self, mock_st):
        state = _make_session_state(use_llm=False)
        state["qdrant_client"].search.return_value = []
        mock_st.session_state = state

        from app import process_query
        result = process_query("nonexistent gibberish query")

        assert "couldn't find" in result["answer"].lower()
        assert result["citations"] == []


class TestCitationSourceResolution:

    @patch("app.st")
    def test_resolves_doc_source(self, mock_st):
        from src.models.schemas import DocumentMetadata
        from datetime import datetime

        state = _make_session_state()
        mock_db = MagicMock()
        mock_db.get_document.return_value = DocumentMetadata(
            doc_id="emmc_51", title="eMMC Spec", protocol="eMMC", version="5.1",
            file_path="f.pdf", uploaded_at=datetime.utcnow(),
            total_pages=100, total_chunks=50, is_active=True,
        )
        state["sqlite_client"] = mock_db
        mock_st.session_state = state

        from app import _resolve_doc_source
        source = _resolve_doc_source("emmc_51")
        assert source == "eMMC 5.1"

    @patch("app.st")
    def test_fallback_to_raw_doc_id(self, mock_st):
        state = _make_session_state()
        state["sqlite_client"].get_document.return_value = None
        mock_st.session_state = state

        from app import _resolve_doc_source
        source = _resolve_doc_source("unknown_doc_id")
        assert source == "unknown_doc_id"


class TestStrategyPassthrough:

    @patch("app.get_rag_pipeline")
    @patch("app.st")
    def test_auto_not_passed_as_override(self, mock_st, mock_get_pipeline):
        mock_st.session_state = _make_session_state(strategy="auto")
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = _mock_pipeline_response()
        mock_get_pipeline.return_value = mock_pipeline

        from app import process_query
        process_query("query")

        call_kwargs = mock_pipeline.process.call_args.kwargs
        assert "strategy_override" not in call_kwargs

    @patch("app.get_rag_pipeline")
    @patch("app.st")
    def test_hybrid_passed_as_override(self, mock_st, mock_get_pipeline):
        mock_st.session_state = _make_session_state(strategy="hybrid")
        mock_pipeline = MagicMock()
        mock_pipeline.process.return_value = _mock_pipeline_response()
        mock_get_pipeline.return_value = mock_pipeline

        from app import process_query
        process_query("query")

        call_kwargs = mock_pipeline.process.call_args.kwargs
        assert call_kwargs.get("strategy_override") == "hybrid"


class TestErrorHandling:

    @patch("app.get_rag_pipeline")
    @patch("app.st")
    def test_error_returns_graceful_message(self, mock_st, mock_get_pipeline):
        mock_st.session_state = _make_session_state(use_llm=True)
        mock_pipeline = MagicMock()
        mock_pipeline.process.side_effect = RuntimeError("API failure")
        mock_get_pipeline.return_value = mock_pipeline

        from app import process_query
        result = process_query("query")

        assert "error" in result["answer"].lower()
        assert result["confidence"] == 0.0
