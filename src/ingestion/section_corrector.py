"""LLM-based section title and path correction using DeepSeek."""

from typing import Dict, List, Optional, Tuple
import json
from openai import OpenAI

from ..utils.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SectionTitleCorrector:
    """Uses DeepSeek LLM to correct section titles and paths."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the section corrector.

        Args:
            api_key: DeepSeek API key (defaults to settings)
        """
        self.client = OpenAI(
            api_key=api_key or settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = "deepseek-chat"  # Fast and cheap model

    def correct_section_metadata(
        self,
        chunk_text: str,
        current_section_title: Optional[str] = None,
        current_section_path: Optional[str] = None,
        page_numbers: Optional[List[int]] = None,
    ) -> Dict[str, str]:
        """
        Use LLM to correct section title and path.

        Args:
            chunk_text: The text content of the chunk
            current_section_title: Current (possibly incorrect) section title
            current_section_path: Current section path
            page_numbers: Page numbers for context

        Returns:
            Dict with corrected 'section_title', 'section_path', 'confidence'
        """
        # Build prompt
        prompt = self._build_correction_prompt(
            chunk_text,
            current_section_title,
            current_section_path,
            page_numbers,
        )

        try:
            # Call DeepSeek API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting section information from technical documentation. "
                        "Analyze the text and extract the correct section title and hierarchical path. "
                        "Return your response as valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            # Parse response
            result = json.loads(response.choices[0].message.content)

            logger.info(
                f"Corrected section: '{current_section_title}' → '{result.get('section_title')}'"
            )

            return {
                "section_title": result.get("section_title", current_section_title),
                "section_path": result.get("section_path", current_section_path),
                "confidence": result.get("confidence", 0.5),
                "reasoning": result.get("reasoning", ""),
            }

        except Exception as e:
            logger.error(f"Failed to correct section metadata: {e}")
            return {
                "section_title": current_section_title,
                "section_path": current_section_path,
                "confidence": 0.0,
                "reasoning": f"Error: {e}",
            }

    def _build_correction_prompt(
        self,
        chunk_text: str,
        current_section_title: Optional[str],
        current_section_path: Optional[str],
        page_numbers: Optional[List[int]],
    ) -> str:
        """Build the prompt for LLM correction."""
        # Truncate text if too long (keep first and last parts)
        max_chars = 2000
        if len(chunk_text) > max_chars:
            middle = len(chunk_text) // 2
            chunk_text = (
                chunk_text[: max_chars // 2]
                + "\n\n[... middle content truncated ...]\n\n"
                + chunk_text[-max_chars // 2 :]
            )

        prompt = f"""Analyze this text from a technical specification document and extract the correct section information.

**Current (possibly incorrect) metadata:**
- Section Title: {current_section_title or "None"}
- Section Path: {current_section_path or "None"}
- Pages: {page_numbers or "Unknown"}

**Text Content:**
```
{chunk_text}
```

**Task:**
1. Identify the actual section number and title from the text (e.g., "6.6.34.1 Disabling emulation mode")
2. Build a proper hierarchical path (e.g., "Chapter 6 > Commands > 6.6.34 Native Sector > 6.6.34.1 Disabling emulation mode")
3. If no clear section is found, extract a meaningful topic-based title from the content

**Important:**
- Look for section numbers like "6.6.34.1", "B.2.6", "Chapter 4"
- Ignore figure captions ("Figure 20"), table captions ("Table 76"), and noise ("4KB", "1b")
- If the current title is obviously wrong (e.g., "4KB", "Figure X"), replace it
- Build hierarchical paths showing: Chapter > Section > Subsection

**Response Format (JSON only):**
{{
  "section_title": "6.6.34.1 Disabling emulation mode",
  "section_path": "Chapter 6 > Commands > 6.6.34 Native Sector > 6.6.34.1 Disabling emulation mode",
  "confidence": 0.95,
  "reasoning": "Found explicit section number 6.6.34.1 in text"
}}

Provide your response as JSON:"""

        return prompt

    def batch_correct_chunks(
        self,
        chunks: List[Dict],
        batch_size: int = 10,
    ) -> List[Dict]:
        """
        Correct section metadata for multiple chunks.

        Args:
            chunks: List of chunk dicts with 'text', 'section_title', etc.
            batch_size: Number of chunks to process concurrently

        Returns:
            List of chunks with corrected metadata
        """
        corrected_chunks = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            logger.info(f"Processing batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size}")

            for chunk in batch:
                corrected = self.correct_section_metadata(
                    chunk_text=chunk.get("text", ""),
                    current_section_title=chunk.get("section_title"),
                    current_section_path=chunk.get("section_path"),
                    page_numbers=chunk.get("page_numbers"),
                )

                # Update chunk with corrections
                chunk["section_title"] = corrected["section_title"]
                chunk["section_path"] = corrected["section_path"]
                chunk["correction_confidence"] = corrected["confidence"]

                corrected_chunks.append(chunk)

        return corrected_chunks


class SelectiveCorrector:
    """Selectively correct only problematic sections to reduce cost."""

    def __init__(self, corrector: SectionTitleCorrector):
        """Initialize with a SectionTitleCorrector instance."""
        self.corrector = corrector

    def needs_correction(self, chunk: Dict) -> bool:
        """
        Determine if a chunk needs section correction.

        Args:
            chunk: Chunk dict with metadata

        Returns:
            True if chunk likely has incorrect section metadata
        """
        section_title = chunk.get("section_title", "")

        if not section_title:
            return True

        # Check for known problematic patterns
        problematic_patterns = [
            lambda s: s.startswith("Figure"),
            lambda s: s.startswith("Table"),
            lambda s: s in ["Tables", "Figures", "Contents"],
            lambda s: len(s) < 4,  # Very short
            lambda s: not any(c.isalpha() for c in s),  # No letters
            lambda s: len(s.split()) > 15,  # Too long
        ]

        for pattern in problematic_patterns:
            if pattern(section_title):
                logger.debug(f"Needs correction: '{section_title}'")
                return True

        return False

    def correct_problematic_chunks(
        self,
        chunks: List[Dict],
    ) -> Tuple[List[Dict], Dict]:
        """
        Correct only chunks with problematic section metadata.

        Args:
            chunks: List of all chunks

        Returns:
            Tuple of (corrected_chunks, statistics)
        """
        stats = {
            "total_chunks": len(chunks),
            "corrected_chunks": 0,
            "skipped_chunks": 0,
            "failed_corrections": 0,
        }

        corrected_chunks = []

        for chunk in chunks:
            if self.needs_correction(chunk):
                try:
                    corrected = self.corrector.correct_section_metadata(
                        chunk_text=chunk.get("text", ""),
                        current_section_title=chunk.get("section_title"),
                        current_section_path=chunk.get("section_path"),
                        page_numbers=chunk.get("page_numbers"),
                    )

                    chunk["section_title"] = corrected["section_title"]
                    chunk["section_path"] = corrected["section_path"]
                    chunk["correction_confidence"] = corrected["confidence"]

                    stats["corrected_chunks"] += 1

                except Exception as e:
                    logger.error(f"Failed to correct chunk: {e}")
                    stats["failed_corrections"] += 1

            else:
                stats["skipped_chunks"] += 1

            corrected_chunks.append(chunk)

        logger.info(
            f"Correction complete: {stats['corrected_chunks']} corrected, "
            f"{stats['skipped_chunks']} skipped, "
            f"{stats['failed_corrections']} failed"
        )

        return corrected_chunks, stats
