"""White-box tests for QueryRouter routing logic and strategy mapping."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers: create a QueryRouter without hitting DeepSeek
# ---------------------------------------------------------------------------

def _make_router():
    """Instantiate QueryRouter with mocked DeepSeek client."""
    with patch("src.agents.query_router.get_deepseek_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.agents.query_router import QueryRouter
        router = QueryRouter()
    return router, mock_client


# ---------------------------------------------------------------------------
# Strategy map tests
# ---------------------------------------------------------------------------

class TestGetRetrievalStrategy:
    """Verify _get_retrieval_strategy returns the correct strategy per type."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.router, _ = _make_router()

    def test_factual_returns_vector(self):
        assert self.router._get_retrieval_strategy("factual") == "vector"

    def test_comparison_returns_hybrid(self):
        assert self.router._get_retrieval_strategy("comparison") == "hybrid"

    def test_troubleshooting_returns_hybrid(self):
        assert self.router._get_retrieval_strategy("troubleshooting") == "hybrid"

    def test_procedural_returns_vector(self):
        assert self.router._get_retrieval_strategy("procedural") == "vector"

    def test_definition_returns_vector(self):
        assert self.router._get_retrieval_strategy("definition") == "vector"

    def test_specification_returns_hybrid(self):
        assert self.router._get_retrieval_strategy("specification") == "hybrid"

    def test_unknown_returns_vector(self):
        assert self.router._get_retrieval_strategy("unknown_type") == "vector"


# ---------------------------------------------------------------------------
# Search params tests
# ---------------------------------------------------------------------------

class TestGetSearchParams:
    """Verify _get_search_params returns correct top_k and min_score."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.router, _ = _make_router()

    def test_definition_params(self):
        params = self.router._get_search_params("definition")
        assert params["top_k"] == 5
        assert params["min_score"] == 0.6

    def test_comparison_params(self):
        params = self.router._get_search_params("comparison")
        assert params["top_k"] == 15
        assert params["min_score"] == 0.4

    def test_troubleshooting_params(self):
        params = self.router._get_search_params("troubleshooting")
        assert params["top_k"] == 15
        assert params["min_score"] == 0.3

    def test_factual_default_params(self):
        params = self.router._get_search_params("factual")
        assert params["top_k"] == 10
        assert params["min_score"] is None


# ---------------------------------------------------------------------------
# Route integration test
# ---------------------------------------------------------------------------

class TestRouteIntegration:
    """Verify route() wires classify_query -> strategy + params correctly."""

    def test_route_comparison_gives_hybrid_and_correct_params(self, mock_classify_response):
        router, mock_client = _make_router()

        mock_client.classify_query.return_value = mock_classify_response("comparison")

        result = router.route("Compare HS200 and HS400")

        assert result["query_type"] == "comparison"
        assert result["retrieval_strategy"] == "hybrid"
        assert result["search_params"]["top_k"] == 15
        assert result["search_params"]["min_score"] == 0.4
        assert "usage" in result
