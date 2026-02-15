"""Vector search wrapper with metadata filtering."""

from typing import List, Dict, Any, Optional

from ..database.qdrant_client import QdrantVectorStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VectorSearch:
    """Wrapper around QdrantVectorStore with metadata filtering support."""

    def __init__(self, vector_store: Optional[QdrantVectorStore] = None):
        self.vector_store = vector_store or QdrantVectorStore()

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: Optional[float] = None,
        doc_id: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search with optional metadata filters.

        Args:
            query: Search query text
            top_k: Number of results to return
            min_score: Minimum similarity score threshold
            doc_id: Filter by document ID
            protocol: Filter by protocol name (not yet implemented in Qdrant payload)

        Returns:
            List of search results sorted by similarity score
        """
        # Build Qdrant filter conditions
        filters = None
        if doc_id or protocol:
            must_conditions = []
            if doc_id:
                must_conditions.append(
                    {"key": "doc_id", "match": {"value": doc_id}}
                )
            if protocol:
                must_conditions.append(
                    {"key": "protocol", "match": {"value": protocol}}
                )
            filters = {"must": must_conditions}

        results = self.vector_store.search(
            query=query,
            top_k=top_k,
            min_score=min_score,
            filters=filters,
        )

        logger.debug(f"Vector search returned {len(results)} results")
        return results
