"""Section-aware chunking that respects document structure boundaries."""

import re
from typing import List, Dict, Any, Optional, Tuple
import uuid

from .chunker import SemanticChunker
from ..models.schemas import DocumentChunk, ChunkMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SectionAwareChunker(SemanticChunker):
    """
    Chunk documents with section boundary awareness.

    Prevents chunks from spanning major section boundaries, ensuring
    each chunk contains semantically cohesive content from a single section.
    """

    # Patterns for detecting section headings
    MAJOR_SECTION_PATTERN = re.compile(
        r'^\s*(\d+(?:\.\d+)*)\s+([A-Z][^\n]*)',  # e.g., "6.6.34 Native Sector"
        re.MULTILINE
    )

    # Pattern for extracting section numbers
    SECTION_NUMBER_PATTERN = re.compile(r'^[\d\.]+')

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base",
        min_chunk_size: int = 100,  # Minimum tokens for a chunk
        max_chunk_size: int = 800,  # Maximum tokens for a chunk
        section_boundary_levels: int = 3,  # How many levels deep to split (e.g., 3 = 6.6.34)
    ):
        """
        Initialize section-aware chunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            encoding_name: Tiktoken encoding name
            min_chunk_size: Minimum chunk size (avoid tiny chunks)
            max_chunk_size: Maximum chunk size (hard limit)
            section_boundary_levels: Number of section levels to respect (default 3)
        """
        super().__init__(chunk_size, chunk_overlap, encoding_name)
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.section_boundary_levels = section_boundary_levels

        logger.info(
            f"Initialized SectionAwareChunker: "
            f"chunk_size={self.chunk_size}, "
            f"min={min_chunk_size}, "
            f"max={max_chunk_size}, "
            f"boundary_levels={section_boundary_levels}"
        )

    def chunk_elements(
        self,
        elements: List[Dict[str, Any]],
        doc_id: str,
    ) -> List[DocumentChunk]:
        """
        Chunk parsed PDF elements with section boundary awareness.

        Args:
            elements: List of parsed PDF elements
            doc_id: Document ID

        Returns:
            List of document chunks with metadata
        """
        logger.info(f"Section-aware chunking {len(elements)} elements for doc {doc_id}")

        chunks = []
        current_chunk_text = []
        current_chunk_tokens = 0
        current_section = None
        current_metadata = {
            "page_numbers": set(),
            "section_title": None,
            "section_path": None,
            "types": set(),
        }

        for i, element in enumerate(elements):
            element_text = element["text"]
            element_tokens = self._count_tokens(element_text)
            element_type = element["type"]
            element_section = element.get("section_title")

            # Handle large tables separately (don't split them)
            if element_type == "table" and element_tokens > self.chunk_size:
                # Flush current chunk if exists
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            doc_id,
                            current_chunk_text,
                            current_metadata,
                        )
                    )
                    current_chunk_text = []
                    current_chunk_tokens = 0
                    current_metadata = self._reset_metadata()

                # Add table as its own chunk
                chunks.append(
                    self._create_chunk(
                        doc_id,
                        [element_text],
                        {
                            "page_numbers": set(element["page_numbers"]),
                            "section_title": element_section,
                            "section_path": element.get("section_path"),
                            "types": {"table"},
                        },
                        chunk_type="table",
                    )
                )
                current_section = element_section
                continue

            # Detect major section transition
            is_major_section_change = (
                element_section
                and current_section
                and self._is_major_section_change(current_section, element_section)
            )

            # Force chunk split at major section boundaries
            if is_major_section_change and current_chunk_text:
                # Check if current chunk meets minimum size
                if current_chunk_tokens >= self.min_chunk_size:
                    # Save current chunk
                    chunks.append(
                        self._create_chunk(
                            doc_id,
                            current_chunk_text,
                            current_metadata,
                        )
                    )

                    # Start new chunk (no overlap at section boundaries)
                    current_chunk_text = []
                    current_chunk_tokens = 0
                    current_metadata = self._reset_metadata()

                    logger.debug(
                        f"Section boundary split: '{current_section}' → '{element_section}'"
                    )
                else:
                    # Chunk too small, keep adding to it despite section change
                    logger.debug(
                        f"Skipping section split (chunk too small: {current_chunk_tokens} tokens)"
                    )

            # Check if adding this element would exceed maximum chunk size
            if current_chunk_tokens + element_tokens > self.max_chunk_size:
                # Must split, even if within same section
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            doc_id,
                            current_chunk_text,
                            current_metadata,
                        )
                    )

                    # Start new chunk with overlap (within same section)
                    overlap_text = self._get_overlap_text(
                        current_chunk_text,
                        current_chunk_tokens,
                    )
                    current_chunk_text = overlap_text
                    current_chunk_tokens = self._count_tokens(" ".join(overlap_text))
                    current_metadata = self._reset_metadata()

                    logger.debug(
                        f"Token-based split within section '{current_section}'"
                    )

            # Check if adding element would exceed target size (but not max)
            elif (
                current_chunk_tokens + element_tokens > self.chunk_size
                and current_chunk_tokens >= self.min_chunk_size
            ):
                # Split here if we have enough content
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            doc_id,
                            current_chunk_text,
                            current_metadata,
                        )
                    )

                    # Start new chunk with overlap (within same section)
                    overlap_text = self._get_overlap_text(
                        current_chunk_text,
                        current_chunk_tokens,
                    )
                    current_chunk_text = overlap_text
                    current_chunk_tokens = self._count_tokens(" ".join(overlap_text))
                    current_metadata = self._reset_metadata()

            # Add element to current chunk
            current_chunk_text.append(element_text)
            current_chunk_tokens += element_tokens
            current_metadata["page_numbers"].update(element["page_numbers"])
            current_metadata["types"].add(element_type)

            # Update section metadata (use most recent within chunk)
            if element_section:
                current_metadata["section_title"] = element_section
                current_section = element_section
            if element.get("section_path"):
                current_metadata["section_path"] = element["section_path"]

        # Add final chunk
        if current_chunk_text:
            chunks.append(
                self._create_chunk(
                    doc_id,
                    current_chunk_text,
                    current_metadata,
                )
            )

        logger.info(
            f"Created {len(chunks)} section-aware chunks for doc {doc_id} "
            f"(avg tokens: {sum(self._count_tokens(c.text) for c in chunks) / len(chunks):.0f})"
        )
        return chunks

    def _is_major_section_change(self, old_section: str, new_section: str) -> bool:
        """
        Detect if section change crosses a major boundary.

        Major boundaries are defined by self.section_boundary_levels.
        For example, with levels=3:
        - "6.6.34.1" → "6.6.34.2" is NOT major (same parent 6.6.34)
        - "6.6.34" → "6.6.35" IS major (different at level 3)
        - "6.6" → "6.7" IS major (different at level 2)
        - "B.2.5" → "B.2.6" is NOT major (same parent B.2, only 2 levels)

        Args:
            old_section: Previous section title
            new_section: New section title

        Returns:
            True if this is a major section change requiring chunk split
        """
        old_nums = self._extract_section_numbers(old_section)
        new_nums = self._extract_section_numbers(new_section)

        # If we can't extract numbers, consider it a change
        if not old_nums or not new_nums:
            return old_section != new_section

        min_len = min(len(old_nums), len(new_nums))
        max_len = max(len(old_nums), len(new_nums))

        # If one section is shorter, it's a major change (different hierarchy)
        if len(old_nums) != len(new_nums):
            return True

        # Determine how many levels to compare based on section depth
        # Rules:
        # - If len > boundary_levels: compare first boundary_levels (e.g., 6.6.34.1→6.6.34.2, compare first 3)
        # - If len <= boundary_levels AND len > 2: compare all levels (e.g., 6.6.34→6.6.35 or 6.6→6.7)
        # - If len <= 2 AND has 3+ levels total: compare all but last (e.g., B.2.5→B.2.6, subsections)

        if min_len > self.section_boundary_levels:
            # Deeper than boundary: compare first N levels
            # E.g., with boundary=3: [6,6,34,1] → [6,6,34,2], compare [6,6,34]
            levels_to_check = self.section_boundary_levels
        elif min_len >= 2:
            # 2+ levels, at or below boundary: compare all levels
            # E.g., [6,6,34] → [6,6,35], compare all 3
            # E.g., [6,6] → [6,7], compare all 2
            levels_to_check = min(min_len, self.section_boundary_levels)
        else:
            # Only 1 level: compare that level
            levels_to_check = 1

        if levels_to_check == 0:
            return False

        # If different at any of the checked levels, it's a major change
        return old_nums[:levels_to_check] != new_nums[:levels_to_check]

    def _extract_section_numbers(self, section_title: str) -> List[int]:
        """
        Extract section numbers from title.

        Examples:
            "6.6.34.1 Disabling emulation mode" → [6, 6, 34, 1]
            "B.2.6 Queue Tasks" → [2, 6] (skip letter prefix)
            "Introduction" → []

        Args:
            section_title: Section title string

        Returns:
            List of section numbers
        """
        if not section_title:
            return []

        stripped = section_title.strip()

        # First try to match numbers at start
        match = self.SECTION_NUMBER_PATTERN.match(stripped)
        if match:
            number_str = match.group(0)
            try:
                return [int(n) for n in number_str.split('.') if n]
            except ValueError:
                return []

        # Try to match with letter prefix (e.g., "B.2.6" or "Appendix B.2.6")
        # Match pattern: optional "Appendix" + letter + dot + numbers
        letter_prefix_pattern = re.compile(r'(?:Appendix\s+)?[A-Z]\.?([\d\.]+)')
        match = letter_prefix_pattern.match(stripped)
        if match:
            number_str = match.group(1)
            try:
                return [int(n) for n in number_str.split('.') if n]
            except ValueError:
                return []

        return []

    def _reset_metadata(self) -> Dict[str, Any]:
        """Create a fresh metadata dict."""
        return {
            "page_numbers": set(),
            "section_title": None,
            "section_path": None,
            "types": set(),
        }

    def _create_chunk(
        self,
        doc_id: str,
        text_parts: List[str],
        metadata: Dict[str, Any],
        chunk_type: str = "text",
    ) -> DocumentChunk:
        """
        Create a document chunk with metadata.

        Overrides parent to add section validation logging.
        """
        chunk = super()._create_chunk(doc_id, text_parts, metadata, chunk_type)

        # Log chunk creation with section info
        token_count = self._count_tokens(chunk.text)
        logger.debug(
            f"Created chunk: section='{metadata.get('section_title', 'N/A')}', "
            f"tokens={token_count}, pages={metadata.get('page_numbers', set())}"
        )

        return chunk


class HybridChunker(SectionAwareChunker):
    """
    Hybrid chunker that combines section awareness with compound titles.

    For chunks that genuinely need to span sections (e.g., small subsections),
    creates compound section titles to accurately reflect mixed content.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base",
        min_chunk_size: int = 100,
        max_chunk_size: int = 800,
        section_boundary_levels: int = 3,
        allow_compound_titles: bool = True,
    ):
        """Initialize hybrid chunker."""
        super().__init__(
            chunk_size,
            chunk_overlap,
            encoding_name,
            min_chunk_size,
            max_chunk_size,
            section_boundary_levels,
        )
        self.allow_compound_titles = allow_compound_titles

    def _create_chunk(
        self,
        doc_id: str,
        text_parts: List[str],
        metadata: Dict[str, Any],
        chunk_type: str = "text",
    ) -> DocumentChunk:
        """
        Create chunk with compound section title if spans multiple sections.
        """
        if self.allow_compound_titles and chunk_type != "table":
            # Detect all sections in chunk text
            full_text = " ".join(text_parts)
            sections_found = self._find_sections_in_text(full_text)

            if len(sections_found) > 1:
                # Create compound title
                parent_section = self._get_common_parent_section(sections_found)
                if parent_section:
                    metadata["section_title"] = f"{parent_section} (Multiple subsections)"
                    logger.debug(
                        f"Created compound title: '{metadata['section_title']}' "
                        f"from {len(sections_found)} sections"
                    )

        return super()._create_chunk(doc_id, text_parts, metadata, chunk_type)

    def _find_sections_in_text(self, text: str) -> List[str]:
        """
        Find all section headings in text.

        Returns:
            List of section titles found
        """
        sections = []
        for match in self.MAJOR_SECTION_PATTERN.finditer(text):
            section_num = match.group(1)
            section_title = match.group(2).strip()
            sections.append(f"{section_num} {section_title}")
        return sections

    def _get_common_parent_section(self, sections: List[str]) -> Optional[str]:
        """
        Get common parent section from list of sections.

        Example:
            ["6.6.34.1 Foo", "6.6.34.2 Bar"] → "6.6.34"

        Returns:
            Common parent section number, or None
        """
        if not sections:
            return None

        # Extract section numbers
        all_nums = [self._extract_section_numbers(s) for s in sections]
        all_nums = [nums for nums in all_nums if nums]  # Filter empty

        if not all_nums:
            return None

        # Find common prefix
        min_length = min(len(nums) for nums in all_nums)
        common_prefix = []

        for i in range(min_length):
            values = [nums[i] for nums in all_nums]
            if len(set(values)) == 1:  # All same at this level
                common_prefix.append(values[0])
            else:
                break

        if common_prefix:
            return ".".join(str(n) for n in common_prefix)

        return None
