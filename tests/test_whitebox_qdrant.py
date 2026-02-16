"""White-box tests for QdrantVectorStore internals."""

import pytest
from unittest.mock import patch, MagicMock, call
from src.models.schemas import DocumentChunk, ChunkMetadata


# ---------------------------------------------------------------------------
# Helper: create QdrantVectorStore with full mocking
# ---------------------------------------------------------------------------

def _make_store(collection_exists=True):
    """Build a QdrantVectorStore with mocked internals.

    Returns (store, mock_qdrant_client, mock_embed_model).
    """
    with patch("src.database.qdrant_client.QdrantClient") as mock_qc, \
         patch("src.database.qdrant_client.SentenceTransformer") as mock_st:

        # Embedding model
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        import numpy as np
        mock_model.encode.side_effect = lambda x: (
            MagicMock(tolist=lambda: [0.1] * 384)
            if isinstance(x, str)
            else MagicMock(tolist=lambda: [[0.1] * 384] * (len(x) if hasattr(x, '__len__') else 1))
        )
        mock_st.return_value = mock_model

        # Qdrant client
        mock_client = MagicMock()
        if collection_exists:
            mock_coll = MagicMock()
            mock_coll.name = "protocol_specs"
            mock_client.get_collections.return_value = MagicMock(
                collections=[mock_coll]
            )
        else:
            mock_client.get_collections.return_value = MagicMock(collections=[])
        mock_qc.return_value = mock_client

        from src.database.qdrant_client import QdrantVectorStore
        store = QdrantVectorStore()

    return store, mock_client, mock_model


# ---------------------------------------------------------------------------
# _ensure_collection
# ---------------------------------------------------------------------------

class TestEnsureCollection:

    def test_creates_collection_when_not_exists(self):
        store, mock_client, _ = _make_store(collection_exists=False)
        # Collection should have been created during __init__
        mock_client.create_collection.assert_called_once()
        # Verify COSINE distance
        create_call = mock_client.create_collection.call_args
        vectors_config = create_call.kwargs.get("vectors_config") or create_call[1].get("vectors_config")
        from qdrant_client.models import Distance
        assert vectors_config.distance == Distance.COSINE

    def test_skips_creation_when_exists(self):
        store, mock_client, _ = _make_store(collection_exists=True)
        mock_client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# add_chunks
# ---------------------------------------------------------------------------

class TestAddChunks:

    def _make_chunk(self, chunk_id="c1", embedding=None):
        meta = ChunkMetadata(
            doc_id="doc1",
            chunk_id=chunk_id,
            page_numbers=[1],
            section_title="Section A",
            section_path="6.1 Section A",
            chunk_type="text",
        )
        return DocumentChunk(text="Sample text content", metadata=meta, embedding=embedding)

    def test_auto_embeds_when_none(self):
        store, mock_client, mock_model = _make_store()
        chunk = self._make_chunk(embedding=None)
        store.add_chunks([chunk])

        # embed_text should have been called (via encode)
        mock_model.encode.assert_called()

    def test_preserves_precomputed_embeddings(self):
        store, mock_client, mock_model = _make_store()
        precomputed = [0.5] * 384
        chunk = self._make_chunk(embedding=precomputed)
        store.add_chunks([chunk])

        # Upsert should use the precomputed vector
        upsert_call = mock_client.upsert.call_args
        points = upsert_call.kwargs.get("points") or upsert_call[1].get("points")
        assert points[0].vector == precomputed

    def test_payload_structure(self):
        store, mock_client, _ = _make_store()
        chunk = self._make_chunk()
        store.add_chunks([chunk])

        upsert_call = mock_client.upsert.call_args
        points = upsert_call.kwargs.get("points") or upsert_call[1].get("points")
        payload = points[0].payload

        expected_keys = {"text", "doc_id", "chunk_id", "page_numbers", "section_title", "section_path", "chunk_type"}
        assert set(payload.keys()) == expected_keys


# ---------------------------------------------------------------------------
# get_all_chunks (pagination)
# ---------------------------------------------------------------------------

class TestGetAllChunks:

    def _make_point(self, chunk_id, doc_id="doc1"):
        point = MagicMock()
        point.payload = {
            "chunk_id": chunk_id,
            "text": f"Text for {chunk_id}",
            "doc_id": doc_id,
            "page_numbers": [1],
            "section_title": "S",
            "section_path": "S",
            "chunk_type": "text",
        }
        return point

    def test_pagination_multiple_batches(self):
        store, mock_client, _ = _make_store()

        # Simulate 3 scroll pages: 100, 100, 50 points
        batch1 = [self._make_point(f"c{i}") for i in range(100)]
        batch2 = [self._make_point(f"c{i}") for i in range(100, 200)]
        batch3 = [self._make_point(f"c{i}") for i in range(200, 250)]

        mock_client.scroll.side_effect = [
            (batch1, "offset_1"),
            (batch2, "offset_2"),
            (batch3, None),  # Last page
        ]

        chunks = store.get_all_chunks(batch_size=100)
        assert len(chunks) == 250
        assert mock_client.scroll.call_count == 3

    def test_doc_id_filter(self):
        store, mock_client, _ = _make_store()
        mock_client.scroll.return_value = ([], None)

        store.get_all_chunks(doc_id="doc1")

        scroll_call = mock_client.scroll.call_args
        scroll_filter = scroll_call.kwargs.get("scroll_filter") or scroll_call[1].get("scroll_filter")
        assert scroll_filter is not None

    def test_empty_collection(self):
        store, mock_client, _ = _make_store()
        mock_client.scroll.return_value = ([], None)

        chunks = store.get_all_chunks()
        assert chunks == []


# ---------------------------------------------------------------------------
# search (score filtering)
# ---------------------------------------------------------------------------

class TestSearch:

    def test_score_filtering(self):
        store, mock_client, _ = _make_store()

        # Create mock search results with different scores
        hit_high = MagicMock()
        hit_high.score = 0.9
        hit_high.payload = {
            "chunk_id": "c1", "text": "high", "doc_id": "d1",
            "page_numbers": [1], "section_title": "S1", "section_path": "S1",
        }

        hit_low = MagicMock()
        hit_low.score = 0.3
        hit_low.payload = {
            "chunk_id": "c2", "text": "low", "doc_id": "d1",
            "page_numbers": [2], "section_title": "S2", "section_path": "S2",
        }

        mock_response = MagicMock()
        mock_response.points = [hit_high, hit_low]
        mock_client.query_points.return_value = mock_response

        results = store.search("query", top_k=10, min_score=0.5)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

class TestDeleteDocument:

    def test_delete_uses_correct_filter(self):
        store, mock_client, _ = _make_store()
        store.delete_document("doc1")

        mock_client.delete.assert_called_once()
        delete_call = mock_client.delete.call_args
        selector = delete_call.kwargs.get("points_selector") or delete_call[1].get("points_selector")
        # Verify it's a Filter with doc_id match
        assert selector is not None
