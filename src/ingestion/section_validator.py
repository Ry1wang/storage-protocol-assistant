"""Semantic validation of section-content relevance using DeepSeek."""

from typing import Dict, List, Optional, Tuple
import json
from openai import OpenAI

from ..utils.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SectionContentValidator:
    """Validates that chunk content matches its assigned section."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the validator.

        Args:
            api_key: DeepSeek API key
        """
        self.client = OpenAI(
            api_key=api_key or settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = "deepseek-chat"

    def validate_section_relevance(
        self,
        chunk_text: str,
        section_title: str,
        section_path: Optional[str] = None,
        page_numbers: Optional[List[int]] = None,
    ) -> Dict[str, any]:
        """
        Validate that chunk content is relevant to its section.

        Args:
            chunk_text: The text content
            section_title: Assigned section title
            section_path: Full section path
            page_numbers: Page numbers

        Returns:
            Dict with validation results
        """
        prompt = self._build_validation_prompt(
            chunk_text,
            section_title,
            section_path,
            page_numbers,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at validating document structure and semantic relevance. "
                        "Analyze whether text content matches its assigned section. "
                        "Return your response as valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=400,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            logger.info(
                f"Validation: '{section_title}' - "
                f"Relevance: {result.get('relevance_score', 0):.2f}, "
                f"Match: {result.get('is_match', False)}"
            )

            return {
                "is_match": result.get("is_match", False),
                "relevance_score": result.get("relevance_score", 0.0),
                "content_summary": result.get("content_summary", ""),
                "expected_section": result.get("expected_section"),
                "mismatch_reason": result.get("mismatch_reason"),
                "confidence": result.get("confidence", 0.0),
            }

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "is_match": None,
                "relevance_score": 0.0,
                "content_summary": "",
                "expected_section": None,
                "mismatch_reason": f"Error: {e}",
                "confidence": 0.0,
            }

    def _build_validation_prompt(
        self,
        chunk_text: str,
        section_title: str,
        section_path: Optional[str],
        page_numbers: Optional[List[int]],
    ) -> str:
        """Build the validation prompt."""
        # Truncate text if too long
        max_chars = 2500
        if len(chunk_text) > max_chars:
            chunk_text = (
                chunk_text[:max_chars]
                + "\n\n[... content truncated for brevity ...]"
            )

        prompt = f"""Validate whether the text content matches its assigned section title.

**Assigned Section:**
- Section Title: {section_title}
- Section Path: {section_path or "N/A"}
- Pages: {page_numbers or "Unknown"}

**Text Content:**
```
{chunk_text}
```

**Task:**
1. Read and understand the text content
2. Determine what the content is actually about (main topic)
3. Compare with the assigned section title
4. Calculate relevance score (0.0 to 1.0):
   - 1.0 = Perfect match (content perfectly matches section)
   - 0.8-0.9 = Good match (content relates to section)
   - 0.5-0.7 = Partial match (some overlap)
   - 0.3-0.4 = Weak match (tangentially related)
   - 0.0-0.2 = Mismatch (content doesn't match section)

5. If mismatch (score < 0.7), suggest what the correct section should be based on content

**Examples of Judgments:**

Example 1:
Section: "6.6.34.1 Disabling emulation mode"
Content: "To disable the emulation mode for large 4KB sector devices, host may write 0x01..."
→ is_match: true, relevance_score: 0.95

Example 2:
Section: "4KB"
Content: "To disable the emulation mode for large 4KB sector devices..."
→ is_match: false, relevance_score: 0.2, expected_section: "6.6.34 Native 4KB Sector"

Example 3:
Section: "Figure 20 — State diagram"
Content: "6.3.3 Boot operation (cont'd). The boot operation consists of..."
→ is_match: false, relevance_score: 0.1, expected_section: "6.3.3 Boot operation"

**Response Format (JSON only):**
{{
  "is_match": true,
  "relevance_score": 0.95,
  "content_summary": "Describes how to disable emulation mode for 4KB sector devices",
  "expected_section": null,
  "mismatch_reason": null,
  "confidence": 0.95
}}

OR if mismatch:
{{
  "is_match": false,
  "relevance_score": 0.3,
  "content_summary": "Discusses boot operation state transitions",
  "expected_section": "6.3.3 Boot operation",
  "mismatch_reason": "Content is about boot operations, not state diagrams",
  "confidence": 0.90
}}

Provide your response as JSON:"""

        return prompt

    def batch_validate_chunks(
        self,
        chunks: List[Dict],
        threshold: float = 0.7,
    ) -> Tuple[List[Dict], Dict]:
        """
        Validate multiple chunks and identify mismatches.

        Args:
            chunks: List of chunks to validate
            threshold: Relevance score threshold (below = mismatch)

        Returns:
            Tuple of (validated_chunks, statistics)
        """
        stats = {
            "total_chunks": len(chunks),
            "validated": 0,
            "matches": 0,
            "mismatches": 0,
            "low_relevance": 0,
            "errors": 0,
        }

        validated_chunks = []

        for i, chunk in enumerate(chunks):
            logger.info(f"Validating chunk {i+1}/{len(chunks)}")

            result = self.validate_section_relevance(
                chunk_text=chunk.get("text", ""),
                section_title=chunk.get("section_title", ""),
                section_path=chunk.get("section_path"),
                page_numbers=chunk.get("page_numbers"),
            )

            # Update chunk with validation results
            chunk["validation"] = result
            chunk["is_match"] = result["is_match"]
            chunk["relevance_score"] = result["relevance_score"]

            # Update statistics
            stats["validated"] += 1

            if result["is_match"] is None:
                stats["errors"] += 1
            elif result["is_match"]:
                stats["matches"] += 1
            else:
                stats["mismatches"] += 1

            if result["relevance_score"] < threshold:
                stats["low_relevance"] += 1

            validated_chunks.append(chunk)

        logger.info(
            f"Validation complete: {stats['matches']} matches, "
            f"{stats['mismatches']} mismatches, "
            f"{stats['low_relevance']} low relevance"
        )

        return validated_chunks, stats


class SectionCorrector:
    """Combined correction and validation pipeline."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize corrector with validator."""
        from .section_corrector import SectionTitleCorrector

        self.corrector = SectionTitleCorrector(api_key)
        self.validator = SectionContentValidator(api_key)

    def correct_and_validate(
        self,
        chunk_text: str,
        current_section_title: Optional[str] = None,
        current_section_path: Optional[str] = None,
        page_numbers: Optional[List[int]] = None,
    ) -> Dict[str, any]:
        """
        Correct section title and validate relevance.

        Args:
            chunk_text: Text content
            current_section_title: Current section title
            current_section_path: Current section path
            page_numbers: Page numbers

        Returns:
            Dict with correction and validation results
        """
        # Step 1: Correct section if needed
        correction = self.corrector.correct_section_metadata(
            chunk_text=chunk_text,
            current_section_title=current_section_title,
            current_section_path=current_section_path,
            page_numbers=page_numbers,
        )

        # Step 2: Validate the corrected section
        validation = self.validator.validate_section_relevance(
            chunk_text=chunk_text,
            section_title=correction["section_title"],
            section_path=correction["section_path"],
            page_numbers=page_numbers,
        )

        # Combine results
        return {
            "original_section_title": current_section_title,
            "original_section_path": current_section_path,
            "corrected_section_title": correction["section_title"],
            "corrected_section_path": correction["section_path"],
            "correction_confidence": correction["confidence"],
            "is_valid": validation["is_match"],
            "relevance_score": validation["relevance_score"],
            "content_summary": validation["content_summary"],
            "validation_confidence": validation["confidence"],
            "needs_review": (
                validation["relevance_score"] < 0.7
                or not validation["is_match"]
            ),
        }

    def process_chunk_with_quality_assurance(
        self,
        chunk: Dict,
        auto_fix: bool = True,
    ) -> Dict:
        """
        Process chunk with full quality assurance pipeline.

        Args:
            chunk: Chunk dict with text and metadata
            auto_fix: Automatically use LLM suggestion if mismatch

        Returns:
            Processed chunk with QA metadata
        """
        result = self.correct_and_validate(
            chunk_text=chunk.get("text", ""),
            current_section_title=chunk.get("section_title"),
            current_section_path=chunk.get("section_path"),
            page_numbers=chunk.get("page_numbers"),
        )

        # Update chunk
        chunk["qa_result"] = result

        # If mismatch and auto-fix enabled
        if result["needs_review"] and auto_fix:
            validation = result.get("validation", {})
            expected_section = validation.get("expected_section")

            if expected_section:
                logger.warning(
                    f"Auto-fixing: '{result['corrected_section_title']}' → '{expected_section}'"
                )
                chunk["section_title"] = expected_section
                chunk["auto_fixed"] = True
            else:
                chunk["section_title"] = result["corrected_section_title"]
                chunk["needs_manual_review"] = True
        else:
            chunk["section_title"] = result["corrected_section_title"]
            chunk["section_path"] = result["corrected_section_path"]

        return chunk


def generate_quality_report(validated_chunks: List[Dict]) -> str:
    """
    Generate a quality report for validated chunks.

    Args:
        validated_chunks: Chunks with validation results

    Returns:
        Formatted report string
    """
    total = len(validated_chunks)
    matches = sum(1 for c in validated_chunks if c.get("is_match"))
    mismatches = total - matches

    # Calculate average relevance
    scores = [c.get("relevance_score", 0) for c in validated_chunks]
    avg_relevance = sum(scores) / len(scores) if scores else 0

    # Find problematic chunks
    low_relevance = [
        c for c in validated_chunks if c.get("relevance_score", 1.0) < 0.7
    ]

    report = f"""
=== Section-Content Relevance Report ===

**Overall Statistics:**
- Total chunks: {total}
- Matches: {matches} ({matches/total*100:.1f}%)
- Mismatches: {mismatches} ({mismatches/total*100:.1f}%)
- Average relevance: {avg_relevance:.3f}

**Quality Grade:**
"""
    if avg_relevance >= 0.9:
        report += "✅ Excellent (A)\n"
    elif avg_relevance >= 0.8:
        report += "✅ Good (B)\n"
    elif avg_relevance >= 0.7:
        report += "⚠️  Acceptable (C)\n"
    else:
        report += "❌ Needs improvement (D/F)\n"

    if low_relevance:
        report += f"\n**Low Relevance Chunks ({len(low_relevance)}):**\n"
        for chunk in low_relevance[:10]:  # Show top 10
            report += f"\n- Chunk: {chunk.get('chunk_id', 'N/A')[:8]}...\n"
            report += f"  Section: {chunk.get('section_title', 'N/A')}\n"
            report += f"  Relevance: {chunk.get('relevance_score', 0):.2f}\n"
            report += f"  Content: {chunk.get('validation', {}).get('content_summary', 'N/A')}\n"

    return report
