"""White-box tests for SectionAwareChunker section boundary detection."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helper: create SectionAwareChunker with default settings
# ---------------------------------------------------------------------------

def _make_chunker(section_boundary_levels=3, min_chunk_size=100, max_chunk_size=800,
                  chunk_size=350, chunk_overlap=30):
    with patch("src.ingestion.chunker.settings") as mock_s:
        mock_s.chunk_size = chunk_size
        mock_s.chunk_overlap = chunk_overlap
        from src.ingestion.section_aware_chunker import SectionAwareChunker
        chunker = SectionAwareChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            section_boundary_levels=section_boundary_levels,
        )
    return chunker


# ---------------------------------------------------------------------------
# _is_major_section_change
# ---------------------------------------------------------------------------

class TestIsMajorSectionChange:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.chunker = _make_chunker(section_boundary_levels=3)

    def test_major_change_6_6_to_6_7(self):
        """6.6 -> 6.7 differs at level 2 => major."""
        assert self.chunker._is_major_section_change(
            "6.6 Bus Modes", "6.7 Timing"
        ) is True

    def test_minor_change_subsection(self):
        """6.6.34.1 -> 6.6.34.2 with levels=3: first 3 levels [6,6,34] match."""
        assert self.chunker._is_major_section_change(
            "6.6.34.1 Disabling emulation mode",
            "6.6.34.2 Enabling emulation mode",
        ) is False

    def test_different_depth_is_major(self):
        """6.6 -> 6.6.1: different depths => major."""
        assert self.chunker._is_major_section_change(
            "6.6 Bus Modes", "6.6.1 HS200"
        ) is True

    def test_same_section_no_change(self):
        """Identical sections are not a major change."""
        assert self.chunker._is_major_section_change(
            "6.6.34 Section A", "6.6.34 Section A"
        ) is False


# ---------------------------------------------------------------------------
# _extract_section_numbers
# ---------------------------------------------------------------------------

class TestExtractSectionNumbers:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.chunker = _make_chunker()

    def test_standard_section_number(self):
        result = self.chunker._extract_section_numbers("6.6.34.1 Title")
        assert result == [6, 6, 34, 1]

    def test_appendix_section_numbers(self):
        result = self.chunker._extract_section_numbers("B.2.6 Title")
        assert result == [2, 6]

    def test_no_section_number(self):
        result = self.chunker._extract_section_numbers("Introduction")
        assert result == []


# ---------------------------------------------------------------------------
# Chunking behaviour tests
# ---------------------------------------------------------------------------

class TestChunkingBehavior:

    def _make_element(self, text, section_title, section_path=None, etype="text", page=1):
        return {
            "text": text,
            "type": etype,
            "page_numbers": [page],
            "section_title": section_title,
            "section_path": section_path or section_title,
        }

    def test_no_split_below_min_chunk_size(self):
        """If section change happens but chunk is below min, don't split."""
        chunker = _make_chunker(min_chunk_size=200, chunk_size=350, max_chunk_size=800)

        # A single short element (< 200 tokens) then a section change
        elements = [
            self._make_element("short text", "6.6 Section A"),
            self._make_element("another section", "6.7 Section B"),
        ]
        chunks = chunker.chunk_elements(elements, "doc1")
        # Both elements fit in one chunk because first is below min_chunk_size
        assert len(chunks) == 1

    def test_force_split_at_max_chunk_size(self):
        """Content exceeding max_chunk_size should be split into multiple chunks."""
        chunker = _make_chunker(min_chunk_size=10, chunk_size=50, max_chunk_size=100)

        # Create many small elements in the same section that together exceed max
        elements = [
            self._make_element(" ".join(["word"] * 40), "6.6 Long Section")
            for _ in range(5)
        ]
        chunks = chunker.chunk_elements(elements, "doc1")
        assert len(chunks) >= 2

    def test_table_preserved_as_standalone(self):
        """A large table should be kept as a standalone chunk."""
        chunker = _make_chunker(chunk_size=50, max_chunk_size=100)

        large_table_text = " ".join(["cell"] * 200)
        elements = [
            self._make_element("intro text", "6.6 Section"),
            self._make_element(large_table_text, "6.6 Section", etype="table"),
            self._make_element("more text", "6.6 Section"),
        ]
        chunks = chunker.chunk_elements(elements, "doc1")

        # Find the table chunk
        table_chunks = [c for c in chunks if c.metadata.chunk_type == "table"]
        assert len(table_chunks) == 1
        assert "cell" in table_chunks[0].text
