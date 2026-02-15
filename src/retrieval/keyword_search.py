"""BM25 keyword search over document chunks."""

from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi

from ..database.qdrant_client import QdrantVectorStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


def _tokenize(text: str) -> List[str]:
    """Simple whitespace tokenization with lowercasing."""
    return text.lower().split()


class KeywordSearch:
    """BM25-based keyword search built from Qdrant chunk data."""

    def __init__(self, vector_store: Optional[QdrantVectorStore] = None):
        self._vector_store = vector_store or QdrantVectorStore()
        self._chunks: List[Dict[str, Any]] = []
        self._bm25: Optional[BM25Okapi] = None
        self._is_built = False

    def _build_index(self) -> None:
        """Fetch all chunks from Qdrant and build the BM25 index."""
        if self._is_built:
            return

        logger.info("Building BM25 index from Qdrant chunks...")
        self._chunks = self._vector_store.get_all_chunks()

        if not self._chunks:
            logger.warning("No chunks found in Qdrant, BM25 index is empty")
            self._is_built = True
            return

        corpus = [_tokenize(chunk["text"]) for chunk in self._chunks]
        self._bm25 = BM25Okapi(corpus)
        self._is_built = True
        logger.info(f"BM25 index built with {len(self._chunks)} documents")

    def rebuild_index(self) -> None:
        """Force rebuild of the BM25 index."""
        self._is_built = False
        self._build_index()

    def search(
        self,
        query: str,
        top_k: int = 10,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search chunks using BM25 keyword matching.

        Args:
            query: Search query text
            top_k: Number of results to return
            doc_id: Optional filter by document ID

        Returns:
            List of search results with BM25 scores, sorted descending
        """
        self._build_index()

        if not self._chunks or self._bm25 is None:
            return []

        tokenized_query = _tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        # Pair chunks with scores and filter
        scored = []
        for idx, score in enumerate(scores):
            if score <= 0:
                continue
            chunk = self._chunks[idx]
            if doc_id and chunk["doc_id"] != doc_id:
                continue
            scored.append((chunk, float(score)))

        # Sort by score descending and take top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]

        results = []
        for chunk, score in scored:
            results.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "doc_id": chunk["doc_id"],
                "page_numbers": chunk.get("page_numbers", []),
                "section_title": chunk.get("section_title"),
                "section_path": chunk.get("section_path"),
                "score": score,
            })

        logger.debug(f"BM25 search returned {len(results)} results")
        return results
