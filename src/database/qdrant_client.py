"""Qdrant vector database client."""

from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    SearchParams,
)
from sentence_transformers import SentenceTransformer

from ..utils.config import settings
from ..utils.logger import get_logger
from ..models.schemas import DocumentChunk, ChunkMetadata

logger = get_logger(__name__)


class QdrantVectorStore:
    """Manages interactions with Qdrant vector database."""

    def __init__(
        self,
        collection_name: str = "protocol_specs",
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize Qdrant client.

        Args:
            collection_name: Name of the Qdrant collection
            embedding_model: Name of the embedding model to use
        """
        self.collection_name = collection_name
        self.client = QdrantClient(url=settings.qdrant_url)

        # Initialize embedding model
        model_name = embedding_model or settings.embedding_model
        logger.info(f"Loading embedding model: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        self.vector_size = self.embedding_model.get_sentence_embedding_dimension()

        # Create collection if it doesn't exist
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name not in collection_names:
            logger.info(f"Creating collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        return self.embedding_model.encode(text).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        return self.embedding_model.encode(texts).tolist()

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Add document chunks to the vector store.

        Args:
            chunks: List of document chunks with embeddings
        """
        points = []
        for chunk in chunks:
            if chunk.embedding is None:
                chunk.embedding = self.embed_text(chunk.text)

            points.append(
                PointStruct(
                    id=chunk.metadata.chunk_id,
                    vector=chunk.embedding,
                    payload={
                        "text": chunk.text,
                        "doc_id": chunk.metadata.doc_id,
                        "chunk_id": chunk.metadata.chunk_id,
                        "page_numbers": chunk.metadata.page_numbers,
                        "section_title": chunk.metadata.section_title,
                        "section_path": chunk.metadata.section_path,
                        "chunk_type": chunk.metadata.chunk_type,
                    },
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info(f"Added {len(points)} chunks to Qdrant")

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            min_score: Minimum similarity score

        Returns:
            List of search results with scores
        """
        query_vector = self.embed_text(query)

        logger.debug(f"Searching with vector of length {len(query_vector)}")

        query_response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        logger.debug(f"Query response type: {type(query_response)}")
        search_result = query_response.points
        logger.debug(f"Points in response: {len(search_result)}")

        # Apply score threshold filter if specified
        if min_score is not None:
            search_result = [hit for hit in search_result if hit.score >= min_score]
            logger.debug(f"After score threshold: {len(search_result)}")

        results = []
        for hit in search_result:
            results.append({
                "chunk_id": hit.payload["chunk_id"],
                "text": hit.payload["text"],
                "doc_id": hit.payload["doc_id"],
                "page_numbers": hit.payload["page_numbers"],
                "section_title": hit.payload.get("section_title"),
                "section_path": hit.payload.get("section_path"),
                "score": hit.score,
            })

        logger.info(f"Found {len(results)} results for query")
        return results

    def get_all_chunks(
        self,
        doc_id: Optional[str] = None,
        batch_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all chunks from the collection using scroll API.

        Args:
            doc_id: Optional filter to only return chunks for a specific document
            batch_size: Number of points per scroll request

        Returns:
            List of chunk dicts with text and metadata (no vectors)
        """
        scroll_filter = None
        if doc_id:
            scroll_filter = Filter(
                must=[{"key": "doc_id", "match": {"value": doc_id}}]
            )

        all_chunks = []
        offset = None

        while True:
            results, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in results:
                all_chunks.append({
                    "chunk_id": point.payload["chunk_id"],
                    "text": point.payload["text"],
                    "doc_id": point.payload["doc_id"],
                    "page_numbers": point.payload.get("page_numbers", []),
                    "section_title": point.payload.get("section_title"),
                    "section_path": point.payload.get("section_path"),
                    "chunk_type": point.payload.get("chunk_type", "text"),
                })

            if next_offset is None:
                break
            offset = next_offset

        logger.info(f"Fetched {len(all_chunks)} chunks from Qdrant")
        return all_chunks

    def delete_document(self, doc_id: str) -> None:
        """
        Delete all chunks for a document.

        Args:
            doc_id: Document ID
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    {"key": "doc_id", "match": {"value": doc_id}}
                ]
            ),
        )
        logger.info(f"Deleted chunks for document: {doc_id}")
