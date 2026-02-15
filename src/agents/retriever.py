"""Retriever Agent - Orchestrates hybrid search and result ranking."""

from typing import List, Dict, Any, Optional
import time

from ..database.qdrant_client import QdrantVectorStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RetrieverAgent:
    """
    Orchestrates retrieval from vector store and ranks results.

    Supports:
    - Vector search (semantic similarity)
    - Hybrid search (vector + keyword, TODO)
    - Result re-ranking
    - Context assembly
    """

    def __init__(self, vector_store: Optional[QdrantVectorStore] = None):
        """
        Initialize retriever agent.

        Args:
            vector_store: QdrantVectorStore instance (creates new if None)
        """
        self.vector_store = vector_store or QdrantVectorStore()
        logger.info("RetrieverAgent initialized")

    def retrieve(
        self,
        query: str,
        strategy: str = "vector",
        top_k: int = 10,
        min_score: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        rerank: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Search query
            strategy: Retrieval strategy (vector, hybrid)
            top_k: Number of results to return
            min_score: Minimum similarity score
            filters: Optional metadata filters
            rerank: Whether to re-rank results

        Returns:
            Dict with:
            - results: List of retrieved chunks
            - context: Assembled context string
            - metadata: Retrieval metadata
        """
        start_time = time.time()
        logger.info(f"Retrieving with strategy='{strategy}', top_k={top_k}")

        # Execute retrieval based on strategy
        if strategy == "vector":
            results = self._vector_search(query, top_k, min_score, filters)
        elif strategy == "hybrid":
            results = self._hybrid_search(query, top_k, min_score, filters)
        else:
            logger.warning(f"Unknown strategy '{strategy}', falling back to vector")
            results = self._vector_search(query, top_k, min_score, filters)

        # Re-rank if requested
        if rerank and len(results) > 1:
            results = self._rerank_results(query, results)

        # Assemble context
        context = self._assemble_context(results, max_chunks=5)

        # Build response
        elapsed = time.time() - start_time
        response = {
            'results': results,
            'context': context,
            'metadata': {
                'strategy': strategy,
                'num_results': len(results),
                'top_score': results[0]['score'] if results else 0.0,
                'latency': elapsed,
            }
        }

        logger.info(f"Retrieved {len(results)} results in {elapsed:.2f}s")
        return response

    def _vector_search(
        self,
        query: str,
        top_k: int,
        min_score: Optional[float],
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.

        Args:
            query: Search query
            top_k: Number of results
            min_score: Minimum score threshold
            filters: Metadata filters

        Returns:
            List of search results
        """
        results = self.vector_store.search(
            query=query,
            top_k=top_k,
            min_score=min_score,
            filters=filters
        )

        logger.debug(f"Vector search returned {len(results)} results")
        return results

    def _hybrid_search(
        self,
        query: str,
        top_k: int,
        min_score: Optional[float],
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (vector + keyword).

        Args:
            query: Search query
            top_k: Number of results
            min_score: Minimum score threshold
            filters: Metadata filters

        Returns:
            Fused search results
        """
        # TODO: Implement BM25 keyword search
        # For now, fall back to vector search
        logger.warning("Hybrid search not yet implemented, using vector search")
        return self._vector_search(query, top_k, min_score, filters)

    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Re-rank results using additional signals.

        Args:
            query: Original query
            results: Initial search results

        Returns:
            Re-ranked results
        """
        # TODO: Implement cross-encoder re-ranking or LLM-based re-ranking
        # For now, return results as-is (already sorted by vector similarity)
        logger.debug("Re-ranking not yet implemented, keeping original order")
        return results

    def _assemble_context(
        self,
        results: List[Dict[str, Any]],
        max_chunks: int = 5,
        max_chars: int = 4000
    ) -> str:
        """
        Assemble context string from search results.

        Args:
            results: Search results
            max_chunks: Maximum number of chunks to include
            max_chars: Maximum total characters

        Returns:
            Formatted context string with citations
        """
        if not results:
            return "No relevant context found."

        context_parts = []
        total_chars = 0

        for i, result in enumerate(results[:max_chunks], 1):
            # Extract metadata
            section_title = result.get('section_title', 'Unknown Section')
            section_path = result.get('section_path', section_title)
            pages = result.get('page_numbers', [])
            text = result.get('text', '')
            score = result.get('score', 0.0)

            # Format page numbers
            page_str = ', '.join(map(str, pages)) if pages else 'N/A'

            # Build citation
            citation_header = f"[{i}] {section_path} (Page {page_str}, Relevance: {score:.1%})"

            # Truncate text if needed
            remaining_chars = max_chars - total_chars
            if len(text) > remaining_chars:
                text = text[:remaining_chars] + "..."

            chunk_text = f"{citation_header}\n{text}\n"
            context_parts.append(chunk_text)

            total_chars += len(chunk_text)

            # Stop if we've hit character limit
            if total_chars >= max_chars:
                break

        context = "\n---\n\n".join(context_parts)

        logger.debug(f"Assembled context: {len(context)} chars from {len(context_parts)} chunks")
        return context

    def get_related_sections(
        self,
        section_path: str,
        num_neighbors: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get sections related to a given section (e.g., sibling sections).

        Args:
            section_path: Section path to find neighbors for
            num_neighbors: Number of related sections to return

        Returns:
            List of related sections
        """
        # TODO: Implement section relationship graph
        # For now, search for sections with similar paths
        logger.debug(f"Getting related sections for: {section_path}")

        # Extract parent path
        parts = section_path.split('→')
        if len(parts) > 1:
            parent = '→'.join(parts[:-1])
            # Search for sections under same parent
            # This would require metadata filtering by section_path prefix
            # For now, return empty list
            return []

        return []


# Singleton instance
_retriever_agent = None

def get_retriever_agent() -> RetrieverAgent:
    """Get or create singleton RetrieverAgent instance."""
    global _retriever_agent
    if _retriever_agent is None:
        _retriever_agent = RetrieverAgent()
    return _retriever_agent
