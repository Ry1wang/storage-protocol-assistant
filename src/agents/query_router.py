"""Query Router Agent - Classifies and routes user queries."""

from typing import Dict, Any, List, Optional
from enum import Enum

from ..utils.deepseek_client import get_deepseek_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QueryType(Enum):
    """Types of queries the system can handle."""

    FACTUAL = "factual"              # "What is the CSD register?"
    COMPARISON = "comparison"        # "What's the difference between eMMC 5.0 and 5.1?"
    TROUBLESHOOTING = "troubleshooting"  # "Why is boot failing?"
    PROCEDURAL = "procedural"        # "How do I configure HS400 mode?"
    DEFINITION = "definition"        # "Define RPMB"
    SPECIFICATION = "specification"  # "What are the timing requirements for..."


class QueryRouter:
    """
    Routes queries to appropriate retrieval strategies based on intent.

    Uses DeepSeek-Chat for fast query classification.
    """

    def __init__(self):
        """Initialize query router."""
        self.client = get_deepseek_client()
        self.query_types = [qt.value for qt in QueryType]

        # Example queries for each type
        self.examples = {
            "factual": [
                "What is the CSD register?",
                "What does the TAAC field contain?",
                "What is the boot partition size?",
            ],
            "comparison": [
                "What's the difference between eMMC 5.0 and 5.1?",
                "Compare HS200 and HS400 modes",
                "How does RPMB differ from regular partitions?",
            ],
            "troubleshooting": [
                "Why is boot failing?",
                "What causes initialization errors?",
                "How to debug command timeout issues?",
            ],
            "procedural": [
                "How do I configure HS400 mode?",
                "How to enable RPMB?",
                "What are the steps for device initialization?",
            ],
            "definition": [
                "Define RPMB",
                "What does CSD mean?",
                "Define packed commands",
            ],
            "specification": [
                "What are the timing requirements for CMD1?",
                "What is the maximum frequency for HS400?",
                "What are the voltage requirements?",
            ],
        }

        logger.info("QueryRouter initialized")

    def route(self, query: str) -> Dict[str, Any]:
        """
        Route a query by classifying its intent.

        Args:
            query: User's query string

        Returns:
            Dict with:
            - query_type: Classified type
            - confidence: Confidence score
            - retrieval_strategy: Recommended strategy
            - search_params: Suggested search parameters
        """
        logger.info(f"Routing query: '{query[:100]}...'")

        # Classify query type
        classification = self.client.classify_query(
            query=query,
            categories=self.query_types,
            examples=self.examples
        )

        query_type = classification['category']
        logger.info(f"Classified as: {query_type}")

        # Determine retrieval strategy based on type
        strategy = self._get_retrieval_strategy(query_type)

        # Determine search parameters
        search_params = self._get_search_params(query_type)

        result = {
            'query': query,
            'query_type': query_type,
            'confidence': classification['confidence'],
            'reasoning': classification['reasoning'],
            'retrieval_strategy': strategy,
            'search_params': search_params,
            'usage': classification['usage'],
        }

        logger.debug(f"Routing result: {result}")
        return result

    def _get_retrieval_strategy(self, query_type: str) -> str:
        """
        Determine retrieval strategy based on query type.

        Args:
            query_type: Classified query type

        Returns:
            Strategy name (vector, hybrid, multi_doc)
        """
        # Map query types to retrieval strategies
        strategy_map = {
            "factual": "vector",           # Dense semantic search works well
            "comparison": "hybrid",        # Need both semantic and keyword
            "troubleshooting": "hybrid",   # Mixed semantic/keyword patterns
            "procedural": "vector",        # Sequential information
            "definition": "vector",        # Precise semantic matching
            "specification": "hybrid",     # Specific values + context
        }

        return strategy_map.get(query_type, "vector")

    def _get_search_params(self, query_type: str) -> Dict[str, Any]:
        """
        Get recommended search parameters based on query type.

        Args:
            query_type: Classified query type

        Returns:
            Dict with top_k, min_score, filters, etc.
        """
        # Base parameters
        params = {
            'top_k': 10,
            'min_score': None,
            'filters': {},
        }

        # Adjust based on query type
        if query_type == "definition":
            # Definitions need high precision
            params['top_k'] = 5
            params['min_score'] = 0.6

        elif query_type == "comparison":
            # Comparisons need more context
            params['top_k'] = 15
            params['min_score'] = 0.4

        elif query_type == "specification":
            # Specifications need exact matches
            params['top_k'] = 8
            params['min_score'] = 0.5

        elif query_type == "procedural":
            # Procedures need sequential context
            params['top_k'] = 12
            params['min_score'] = 0.45

        elif query_type == "troubleshooting":
            # Troubleshooting needs broad context
            params['top_k'] = 15
            params['min_score'] = 0.3

        return params

    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract named entities from query (registers, commands, modes, etc.).

        Args:
            query: User query

        Returns:
            Dict mapping entity types to lists of entities
        """
        prompt = f"""Extract technical entities from this storage protocol query.

Query: "{query}"

Identify:
- registers: Register names (CSD, EXT_CSD, etc.)
- commands: Command names (CMD1, CMD8, etc.)
- modes: Operating modes (HS400, HS200, DDR52, etc.)
- fields: Field names (TAAC, TRAN_SPEED, etc.)
- features: Feature names (RPMB, Boot, Packed Commands, etc.)

Respond with JSON only:
{{
  "registers": [...],
  "commands": [...],
  "modes": [...],
  "fields": [...],
  "features": [...]
}}"""

        try:
            entities = self.client.extract_json(prompt)
            logger.debug(f"Extracted entities: {entities}")
            return entities
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {
                "registers": [],
                "commands": [],
                "modes": [],
                "fields": [],
                "features": [],
            }

    def expand_query(self, query: str, query_type: str) -> List[str]:
        """
        Generate query expansions for better retrieval.

        Args:
            query: Original query
            query_type: Classified query type

        Returns:
            List of expanded/reformulated queries
        """
        # For now, return just the original query
        # TODO: Implement query expansion using LLM
        return [query]


# Singleton instance
_query_router = None

def get_query_router() -> QueryRouter:
    """Get or create singleton QueryRouter instance."""
    global _query_router
    if _query_router is None:
        _query_router = QueryRouter()
    return _query_router
