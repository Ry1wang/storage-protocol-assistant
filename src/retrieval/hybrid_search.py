"""Hybrid search combining vector and BM25 with Reciprocal Rank Fusion."""

from typing import List, Dict, Any, Optional

from ..database.qdrant_client import QdrantVectorStore
from ..utils.logger import get_logger
from .vector_search import VectorSearch
from .keyword_search import KeywordSearch

logger = get_logger(__name__)


class HybridSearch:
    """Combines vector similarity and BM25 keyword search using RRF."""

    def __init__(
        self,
        vector_store: Optional[QdrantVectorStore] = None,
        rrf_k: int = 60,
    ):
        """
        Args:
            vector_store: Shared QdrantVectorStore instance
            rrf_k: RRF constant (default 60, standard value)
        """
        store = vector_store or QdrantVectorStore()
        self.vector_search = VectorSearch(vector_store=store)
        self.keyword_search = KeywordSearch(vector_store=store)
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: Optional[float] = None,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search with RRF fusion.

        Retrieves 2x top_k from each source, then fuses with RRF.

        Args:
            query: Search query
            top_k: Number of final results to return
            min_score: Minimum vector similarity score
            doc_id: Optional document ID filter

        Returns:
            Fused results sorted by RRF score
        """
        fetch_k = top_k * 2

        # Retrieve from both sources
        vector_results = self.vector_search.search(
            query=query, top_k=fetch_k, min_score=min_score, doc_id=doc_id
        )
        keyword_results = self.keyword_search.search(
            query=query, top_k=fetch_k, doc_id=doc_id
        )

        logger.info(
            f"Hybrid search: {len(vector_results)} vector, "
            f"{len(keyword_results)} keyword results"
        )

        # Fuse with RRF
        fused = self._reciprocal_rank_fusion(
            vector_results, keyword_results, top_k
        )

        return fused

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        Merge two ranked lists using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) across all lists where the item appears.

        Args:
            vector_results: Results from vector search (rank-ordered)
            keyword_results: Results from BM25 search (rank-ordered)
            top_k: Number of results to return

        Returns:
            Merged results sorted by RRF score
        """
        k = self.rrf_k
        # Map chunk_id -> (rrf_score, chunk_data)
        scores: Dict[str, float] = {}
        chunks: Dict[str, Dict[str, Any]] = {}

        for rank, result in enumerate(vector_results, start=1):
            cid = result["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            chunks[cid] = result

        for rank, result in enumerate(keyword_results, start=1):
            cid = result["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in chunks:
                chunks[cid] = result

        # Sort by RRF score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for cid, rrf_score in ranked[:top_k]:
            entry = dict(chunks[cid])
            entry["score"] = rrf_score
            results.append(entry)

        logger.debug(
            f"RRF fusion: {len(scores)} unique chunks -> top {len(results)}"
        )
        return results
