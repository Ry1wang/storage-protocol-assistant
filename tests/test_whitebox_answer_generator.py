"""White-box tests for AnswerGenerator citation extraction, confidence, and instructions."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helper: create AnswerGenerator without DeepSeek
# ---------------------------------------------------------------------------

def _make_generator():
    with patch("src.agents.answer_generator.get_deepseek_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.agents.answer_generator import AnswerGenerator
        gen = AnswerGenerator()
    return gen


# ---------------------------------------------------------------------------
# _extract_citations
# ---------------------------------------------------------------------------

class TestExtractCitations:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.gen = _make_generator()

    def test_single_citation(self):
        result = self.gen._extract_citations("According to [1], the value is 3.3V")
        assert result == [1]

    def test_multiple_citations(self):
        result = self.gen._extract_citations("See [1] and [3] for details")
        assert result == [1, 3]

    def test_duplicate_citations_deduplicated(self):
        result = self.gen._extract_citations("[1] shows X. As noted in [1]")
        assert result == [1]

    def test_no_citations(self):
        result = self.gen._extract_citations("The answer is unknown")
        assert result == []

    def test_preserves_order(self):
        result = self.gen._extract_citations("[3] then [1] then [2]")
        assert result == [3, 1, 2]


# ---------------------------------------------------------------------------
# _build_citations
# ---------------------------------------------------------------------------

class TestBuildCitations:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.gen = _make_generator()

    def _sample_results(self, n=5):
        return [
            {
                "chunk_id": f"c{i}",
                "text": f"Sample text for result {i}" * 5,
                "doc_id": "emmc_51",
                "page_numbers": [i * 10],
                "section_title": f"Section {i}",
                "section_path": f"6.{i} Section {i}",
                "score": 0.9 - i * 0.1,
            }
            for i in range(n)
        ]

    def test_valid_range(self):
        results = self._sample_results(5)
        citations = self.gen._build_citations([1, 2], results)
        assert len(citations) == 2
        assert citations[0]["number"] == 1
        assert citations[0]["section_title"] == "Section 0"
        assert citations[1]["number"] == 2
        assert citations[1]["section_title"] == "Section 1"

    def test_out_of_range(self):
        results = self._sample_results(3)
        citations = self.gen._build_citations([10], results)
        assert citations == []

    def test_zero_index_out_of_range(self):
        results = self._sample_results(3)
        # Citation [0] maps to idx -1, which is out of range
        citations = self.gen._build_citations([0], results)
        assert citations == []

    def test_citation_contains_expected_fields(self):
        results = self._sample_results(3)
        citations = self.gen._build_citations([1], results)
        cit = citations[0]
        assert "number" in cit
        assert "section_title" in cit
        assert "section_path" in cit
        assert "page_numbers" in cit
        assert "text_preview" in cit
        assert "score" in cit
        assert "doc_id" in cit


# ---------------------------------------------------------------------------
# _calculate_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.gen = _make_generator()

    def _results_with_score(self, top_score):
        return [{"score": top_score, "text": "sample"}]

    def test_high_score_with_citations(self):
        answer = "The value is 3.3V [1]."
        results = self._results_with_score(0.85)
        conf = self.gen._calculate_confidence(answer, results)
        # 0.85 * 1.1 = 0.935
        assert abs(conf - 0.935) < 0.01

    def test_no_citations_penalty(self):
        answer = "The value is 3.3V with no references."
        results = self._results_with_score(0.8)
        conf = self.gen._calculate_confidence(answer, results)
        # 0.8 * 0.6 = 0.48
        assert abs(conf - 0.48) < 0.01

    def test_low_confidence_phrase(self):
        answer = "I cannot answer this based on the provided context."
        results = self._results_with_score(0.7)
        conf = self.gen._calculate_confidence(answer, results)
        # 0.7 * 0.5 = 0.35
        assert abs(conf - 0.35) < 0.01

    def test_empty_results(self):
        conf = self.gen._calculate_confidence("Any answer", [])
        assert conf == 0.0

    def test_confidence_capped_at_one(self):
        answer = "The value [1] is confirmed."
        results = self._results_with_score(0.99)
        conf = self.gen._calculate_confidence(answer, results)
        # 0.99 * 1.1 = 1.089, capped to 1.0
        assert conf == 1.0


# ---------------------------------------------------------------------------
# _get_instructions
# ---------------------------------------------------------------------------

class TestGetInstructions:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.gen = _make_generator()

    def test_definition_contains_concise(self):
        instr = self.gen._get_instructions("definition")
        assert "concise definition" in instr.lower()

    def test_comparison_contains_comparison(self):
        instr = self.gen._get_instructions("comparison")
        assert "comparison" in instr.lower()

    def test_unknown_type_returns_generic(self):
        instr = self.gen._get_instructions("xyz")
        assert "detailed" in instr.lower() or "technical" in instr.lower()

    def test_none_type_returns_generic(self):
        instr = self.gen._get_instructions(None)
        assert "detailed" in instr.lower() or "technical" in instr.lower()
