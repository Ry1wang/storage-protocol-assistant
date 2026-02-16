"""Black-box tests for the document ingestion lifecycle."""

import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
from datetime import datetime

# Mock unstructured module before importing ingestion code
if "unstructured" not in sys.modules:
    sys.modules["unstructured"] = MagicMock()
    sys.modules["unstructured.partition"] = MagicMock()
    sys.modules["unstructured.partition.pdf"] = MagicMock()
    sys.modules["unstructured.documents"] = MagicMock()
    sys.modules["unstructured.documents.elements"] = MagicMock()
if "pdfplumber" not in sys.modules:
    sys.modules["pdfplumber"] = MagicMock()

from src.models.schemas import DocumentMetadata


# ---------------------------------------------------------------------------
# Helper: create SpecificationIngester with all mocks
# ---------------------------------------------------------------------------

def _make_ingester(mock_vector_store=None, mock_sqlite_client=None,
                   mock_parser=None, mock_chunker=None):
    """Build ingester with mocked dependencies."""
    vs = mock_vector_store or MagicMock()
    db = mock_sqlite_client or MagicMock()
    parser = mock_parser or MagicMock()
    chunker = mock_chunker or MagicMock()

    from src.ingestion.ingest_spec import SpecificationIngester
    ingester = SpecificationIngester(
        vector_store=vs,
        metadata_db=db,
        parser=parser,
        chunker=chunker,
    )
    return ingester, vs, db, parser, chunker


def _make_fake_chunks(n=3):
    """Return a list of mock DocumentChunk objects."""
    from src.models.schemas import DocumentChunk, ChunkMetadata
    chunks = []
    for i in range(n):
        meta = ChunkMetadata(
            doc_id="test_doc",
            chunk_id=f"chunk_{i}",
            page_numbers=[i + 1],
            section_title=f"Section {i}",
        )
        chunks.append(DocumentChunk(text=f"Chunk text {i}", metadata=meta))
    return chunks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestValidPDF:

    def test_ingest_returns_doc_id_with_pattern(self, tmp_path):
        pdf_file = tmp_path / "emmc_5.1.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        parser = MagicMock()
        parser.parse_pdf.return_value = [
            {"text": "Hello", "type": "text", "page_numbers": [1],
             "section_title": "Intro", "section_path": "1 Intro", "metadata": {}},
        ]
        parser.get_total_pages.return_value = 10

        chunker = MagicMock()
        chunker.chunk_elements.return_value = _make_fake_chunks(3)

        db = MagicMock()
        db.get_document.return_value = None  # No existing doc

        ingester, vs, db, _, _ = _make_ingester(
            mock_parser=parser, mock_chunker=chunker, mock_sqlite_client=db,
        )

        doc_id = ingester.ingest_document(
            file_path=str(pdf_file), protocol="eMMC", version="5.1",
        )
        assert doc_id.startswith("eMMC_5_1_")
        vs.add_chunks.assert_called_once()
        db.add_document.assert_called_once()

    def test_ingest_with_custom_title(self, tmp_path):
        pdf_file = tmp_path / "emmc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        parser = MagicMock()
        parser.parse_pdf.return_value = [
            {"text": "Data", "type": "text", "page_numbers": [1],
             "section_title": None, "section_path": None, "metadata": {}},
        ]
        parser.get_total_pages.return_value = 5

        chunker = MagicMock()
        chunker.chunk_elements.return_value = _make_fake_chunks(1)

        db = MagicMock()
        db.get_document.return_value = None

        ingester, _, db, _, _ = _make_ingester(
            mock_parser=parser, mock_chunker=chunker, mock_sqlite_client=db,
        )

        ingester.ingest_document(
            file_path=str(pdf_file), protocol="eMMC", version="5.1",
            title="My Custom Title",
        )

        add_call = db.add_document.call_args
        doc_meta = add_call[0][0]
        assert doc_meta.title == "My Custom Title"

    def test_ingest_without_title_uses_filename(self, tmp_path):
        pdf_file = tmp_path / "my_spec.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        parser = MagicMock()
        parser.parse_pdf.return_value = [
            {"text": "Data", "type": "text", "page_numbers": [1],
             "section_title": None, "section_path": None, "metadata": {}},
        ]
        parser.get_total_pages.return_value = 1

        chunker = MagicMock()
        chunker.chunk_elements.return_value = _make_fake_chunks(1)

        db = MagicMock()
        db.get_document.return_value = None

        ingester, _, db, _, _ = _make_ingester(
            mock_parser=parser, mock_chunker=chunker, mock_sqlite_client=db,
        )

        ingester.ingest_document(
            file_path=str(pdf_file), protocol="UFS", version="3.1",
        )

        doc_meta = db.add_document.call_args[0][0]
        assert doc_meta.title == "my_spec"


class TestReIngest:

    def test_reingest_deletes_old_chunks(self, tmp_path):
        pdf_file = tmp_path / "spec.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 data")

        parser = MagicMock()
        parser.parse_pdf.return_value = [
            {"text": "Data", "type": "text", "page_numbers": [1],
             "section_title": None, "section_path": None, "metadata": {}},
        ]
        parser.get_total_pages.return_value = 2

        chunker = MagicMock()
        chunker.chunk_elements.return_value = _make_fake_chunks(2)

        db = MagicMock()
        # Simulate existing doc
        db.get_document.return_value = DocumentMetadata(
            doc_id="existing",
            title="Old",
            protocol="eMMC",
            version="5.1",
            file_path="old.pdf",
            uploaded_at=datetime.utcnow(),
            total_pages=10,
            total_chunks=5,
            is_active=True,
        )

        ingester, vs, _, _, _ = _make_ingester(
            mock_parser=parser, mock_chunker=chunker, mock_sqlite_client=db,
        )

        ingester.ingest_document(
            file_path=str(pdf_file), protocol="eMMC", version="5.1",
        )

        # delete_document should be called to remove old chunks
        vs.delete_document.assert_called()


class TestFileNotFound:

    def test_raises_file_not_found(self):
        ingester, _, _, _, _ = _make_ingester()

        with pytest.raises(FileNotFoundError):
            ingester.ingest_document(
                file_path="/nonexistent/path.pdf",
                protocol="eMMC",
                version="5.1",
            )


class TestEmptyPDF:

    def test_raises_value_error_for_empty(self, tmp_path):
        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 empty")

        parser = MagicMock()
        parser.parse_pdf.return_value = []  # No elements

        db = MagicMock()
        db.get_document.return_value = None

        ingester, _, _, _, _ = _make_ingester(mock_parser=parser, mock_sqlite_client=db)

        with pytest.raises(ValueError, match="No elements extracted"):
            ingester.ingest_document(
                file_path=str(pdf_file), protocol="eMMC", version="5.1",
            )


class TestDeleteDocument:

    def test_delete_existing_document(self):
        db = MagicMock()
        db.get_document.return_value = DocumentMetadata(
            doc_id="doc1", title="T", protocol="eMMC", version="5.1",
            file_path="f.pdf", uploaded_at=datetime.utcnow(),
            total_pages=10, total_chunks=5, is_active=True,
        )

        ingester, vs, _, _, _ = _make_ingester(mock_sqlite_client=db)
        ingester.delete_document("doc1")

        vs.delete_document.assert_called_once_with("doc1")
        # Verify metadata updated (is_active=False)
        updated_doc = db.add_document.call_args[0][0]
        assert updated_doc.is_active is False

    def test_delete_nonexistent_raises(self):
        db = MagicMock()
        db.get_document.return_value = None

        ingester, _, _, _, _ = _make_ingester(mock_sqlite_client=db)

        with pytest.raises(ValueError, match="not found"):
            ingester.delete_document("nonexistent_id")


class TestListDocuments:

    def test_list_empty(self):
        db = MagicMock()
        db.list_documents.return_value = []

        ingester, _, _, _, _ = _make_ingester(mock_sqlite_client=db)
        # list_documents prints to stdout, just verify no error
        ingester.list_documents()

    def test_list_with_data(self):
        docs = [
            DocumentMetadata(
                doc_id=f"doc{i}", title=f"Title {i}", protocol="eMMC",
                version="5.1", file_path="f.pdf", uploaded_at=datetime.utcnow(),
                total_pages=10, total_chunks=5, is_active=True,
            )
            for i in range(2)
        ]
        db = MagicMock()
        db.list_documents.return_value = docs

        ingester, _, _, _, _ = _make_ingester(mock_sqlite_client=db)
        ingester.list_documents()  # Should print without error
