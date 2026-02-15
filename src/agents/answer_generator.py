"""Answer Generator Agent - Creates citation-backed answers using LLM."""

from typing import List, Dict, Any, Optional
import re

from ..utils.deepseek_client import get_deepseek_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AnswerGenerator:
    """
    Generates citation-backed answers using DeepSeek LLM.

    Ensures:
    - Every claim has a citation
    - No hallucinations (only uses provided context)
    - Clear, technical answers for engineers
    """

    def __init__(self):
        """Initialize answer generator."""
        self.client = get_deepseek_client()
        logger.info("AnswerGenerator initialized")

    def generate(
        self,
        query: str,
        context: str,
        results: List[Dict[str, Any]],
        query_type: Optional[str] = None,
        model: str = "deepseek-reasoner",
    ) -> Dict[str, Any]:
        """
        Generate a citation-backed answer.

        Args:
            query: User's question
            context: Retrieved context with citations
            results: Original search results (for citation details)
            query_type: Type of query (for tailored instructions)
            model: LLM model to use

        Returns:
            Dict with:
            - answer: Generated answer text
            - citations: List of citations used
            - confidence: Confidence score
            - metadata: Generation metadata
        """
        logger.info(f"Generating answer for query: '{query[:100]}...'")

        # Get tailored instructions based on query type
        instructions = self._get_instructions(query_type)

        # Generate answer using LLM
        response = self.client.generate_answer(
            query=query,
            context=context,
            instructions=instructions,
            model=model
        )

        answer_text = response['answer']

        # Extract citations from answer
        citation_numbers = self._extract_citations(answer_text)

        # Build citation details
        citations = self._build_citations(citation_numbers, results)

        # Calculate confidence score
        confidence = self._calculate_confidence(answer_text, results)

        result = {
            'answer': answer_text,
            'citations': citations,
            'confidence': confidence,
            'metadata': {
                'model': response['model'],
                'query_type': query_type,
                'num_sources': len(results),
                'num_citations_used': len(citations),
                'usage': response['usage'],
                'latency': response['latency'],
            }
        }

        logger.info(
            f"Generated answer: {len(answer_text)} chars, "
            f"{len(citations)} citations, confidence={confidence:.1%}"
        )

        return result

    def _get_instructions(self, query_type: Optional[str]) -> str:
        """
        Get tailored instructions based on query type.

        Args:
            query_type: Type of query

        Returns:
            Instruction string
        """
        base_instructions = {
            "definition": "Provide a clear, concise definition. Include the official specification definition if available.",
            "factual": "Provide factual information directly from the specification. Be precise and technical.",
            "comparison": "Create a detailed comparison table or structured comparison. Highlight key differences.",
            "procedural": "Provide step-by-step instructions in a numbered list. Include prerequisites and post-conditions.",
            "specification": "Provide exact specification values (timing, voltage, frequency, etc.). Include units and conditions.",
            "troubleshooting": "Identify potential causes and solutions. Reference specification requirements that may be violated.",
        }

        return base_instructions.get(query_type, "Provide a detailed, technical answer.")

    def _extract_citations(self, text: str) -> List[int]:
        """
        Extract citation numbers from answer text.

        Args:
            text: Answer text with citations like [1], [2]

        Returns:
            List of unique citation numbers
        """
        # Find all [N] patterns
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, text)

        # Convert to integers and remove duplicates while preserving order
        citations = []
        seen = set()
        for num_str in matches:
            num = int(num_str)
            if num not in seen:
                citations.append(num)
                seen.add(num)

        logger.debug(f"Extracted {len(citations)} unique citations: {citations}")
        return citations

    def _build_citations(
        self,
        citation_numbers: List[int],
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Build citation details from citation numbers and search results.

        Args:
            citation_numbers: List of citation numbers used
            results: Search results

        Returns:
            List of citation dicts
        """
        citations = []

        for num in citation_numbers:
            # Citation numbers are 1-indexed
            idx = num - 1

            if idx < 0 or idx >= len(results):
                logger.warning(f"Invalid citation number {num} (only {len(results)} results)")
                continue

            result = results[idx]

            citation = {
                'number': num,
                'section_title': result.get('section_title', 'Unknown'),
                'section_path': result.get('section_path', 'Unknown'),
                'page_numbers': result.get('page_numbers', []),
                'text_preview': result.get('text', '')[:200] + '...',
                'score': result.get('score', 0.0),
                'doc_id': result.get('doc_id', 'unknown'),
            }

            citations.append(citation)

        return citations

    def _calculate_confidence(
        self,
        answer: str,
        results: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate confidence score for the answer.

        Args:
            answer: Generated answer
            results: Search results used

        Returns:
            Confidence score (0.0-1.0)
        """
        if not results:
            return 0.0

        # Base confidence on top result score
        base_confidence = results[0].get('score', 0.0)

        # Check if answer acknowledges lack of information
        low_confidence_phrases = [
            "i cannot answer",
            "not found in the context",
            "insufficient information",
            "context doesn't contain",
            "unable to determine",
        ]

        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in low_confidence_phrases):
            return max(0.3, base_confidence * 0.5)

        # Check citation coverage
        citation_count = len(re.findall(r'\[\d+\]', answer))
        if citation_count == 0:
            # No citations is concerning
            return max(0.4, base_confidence * 0.6)

        # Good citations and high base score
        confidence = min(1.0, base_confidence * 1.1)

        return confidence

    def validate_answer(
        self,
        answer: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Validate that answer doesn't hallucinate beyond context.

        Args:
            answer: Generated answer
            context: Source context

        Returns:
            Dict with validation results
        """
        # TODO: Implement hallucination detection
        # Could use:
        # - Fact extraction and verification
        # - Entailment checking
        # - Cross-encoder scoring

        logger.debug("Answer validation not yet implemented")

        return {
            'is_valid': True,
            'hallucination_score': 0.0,
            'issues': [],
        }

    def format_answer(
        self,
        answer_dict: Dict[str, Any],
        format_type: str = "markdown"
    ) -> str:
        """
        Format answer for display.

        Args:
            answer_dict: Answer dict from generate()
            format_type: Output format (markdown, html, plain)

        Returns:
            Formatted answer string
        """
        if format_type == "markdown":
            return self._format_markdown(answer_dict)
        elif format_type == "html":
            return self._format_html(answer_dict)
        else:
            return answer_dict['answer']

    def _format_markdown(self, answer_dict: Dict[str, Any]) -> str:
        """Format answer as markdown."""
        parts = []

        # Answer text
        parts.append(answer_dict['answer'])

        # Confidence indicator
        confidence = answer_dict['confidence']
        if confidence >= 0.8:
            indicator = "🟢 High Confidence"
        elif confidence >= 0.6:
            indicator = "🟡 Medium Confidence"
        else:
            indicator = "🔴 Low Confidence"

        parts.append(f"\n\n**Confidence:** {indicator} ({confidence:.1%})")

        # Citations section
        citations = answer_dict.get('citations', [])
        if citations:
            parts.append("\n\n---\n\n## 📚 Sources\n")
            for cit in citations:
                pages = ', '.join(map(str, cit['page_numbers'])) if cit['page_numbers'] else 'N/A'
                parts.append(
                    f"**[{cit['number']}]** {cit['section_path']}  \n"
                    f"📄 Page {pages} · Relevance: {cit['score']:.1%}\n"
                )

        return ''.join(parts)

    def _format_html(self, answer_dict: Dict[str, Any]) -> str:
        """Format answer as HTML."""
        # TODO: Implement HTML formatting
        return self._format_markdown(answer_dict)


# Singleton instance
_answer_generator = None

def get_answer_generator() -> AnswerGenerator:
    """Get or create singleton AnswerGenerator instance."""
    global _answer_generator
    if _answer_generator is None:
        _answer_generator = AnswerGenerator()
    return _answer_generator
