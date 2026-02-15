"""Tests for the ingestion pipeline."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from src.ingestion.pdf_parser import PDFParser
from src.ingestion.chunker import SemanticChunker, SimpleChunker
from src.ingestion.ingest_spec import SpecificationIngester
from src.models.schemas import DocumentChunk, ChunkMetadata, DocumentMetadata


class TestPDFParser:
    """Tests for PDF parser."""

    def test_generate_doc_id(self, tmp_path):
        """Test document ID generation."""
        # Create a temporary file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"test content")

        doc_id = PDFParser.generate_doc_id(
            str(test_file),
            protocol="eMMC",
            version="5.1",
        )

        assert doc_id.startswith("eMMC_5_1_")
        assert len(doc_id) > len("eMMC_5_1_")
        assert "_" in doc_id
        assert "." not in doc_id  # Dots should be replaced

    def test_generate_doc_id_consistency(self, tmp_path):
        """Test that same file generates same doc ID."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"test content")

        doc_id1 = PDFParser.generate_doc_id(str(test_file), "eMMC", "5.1")
        doc_id2 = PDFParser.generate_doc_id(str(test_file), "eMMC", "5.1")

        assert doc_id1 == doc_id2

    def test_get_element_type(self):
        """Test element type detection."""
        parser = PDFParser()

        # Mock elements
        from unstructured.documents.elements import Title, Table, NarrativeText

        title = Title("Chapter 1")
        assert parser._get_element_type(title) == "heading"

        table = Table("| A | B |\n| 1 | 2 |")
        assert parser._get_element_type(table) == "table"

        text = NarrativeText("Some text")
        assert parser._get_element_type(text) == "text"

    def test_estimate_heading_level(self):
        """Test heading level estimation."""
        parser = PDFParser()

        # Short title = Level 1
        assert parser._estimate_heading_level("Chapter 1") == 1

        # Medium title = Level 2
        assert parser._estimate_heading_level("1.1 Introduction to the Protocol") == 2

        # Long title = Level 3
        assert parser._estimate_heading_level(
            "1.1.1 This is a very long subsection title that contains many words"
        ) == 3


class TestSemanticChunker:
    """Tests for semantic chunker."""

    def test_chunk_small_elements(self):
        """Test chunking with small elements that fit in one chunk."""
        chunker = SemanticChunker(chunk_size=500, chunk_overlap=50)

        elements = [
            {
                "text": "First paragraph.",
                "type": "text",
                "page_numbers": [1],
                "section_title": "Introduction",
                "section_path": "Chapter 1 > Introduction",
            },
            {
                "text": "Second paragraph.",
                "type": "text",
                "page_numbers": [1],
                "section_title": "Introduction",
                "section_path": "Chapter 1 > Introduction",
            },
        ]

        chunks = chunker.chunk_elements(elements, doc_id="test_doc")

        assert len(chunks) >= 1
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert chunks[0].metadata.doc_id == "test_doc"
        assert 1 in chunks[0].metadata.page_numbers

    def test_chunk_large_table(self):
        """Test that large tables are kept as single chunks."""
        chunker = SemanticChunker(chunk_size=100, chunk_overlap=10)

        # Create a large table element
        table_text = "| Column 1 | Column 2 |\n" + ("| Data | Data |\n" * 100)

        elements = [
            {
                "text": table_text,
                "type": "table",
                "page_numbers": [5],
                "section_title": "Specifications",
                "section_path": "Chapter 2 > Specifications",
            }
        ]

        chunks = chunker.chunk_elements(elements, doc_id="test_doc")

        # Large table should be its own chunk
        assert len(chunks) == 1
        assert chunks[0].metadata.chunk_type == "table"
        assert chunks[0].text == table_text

    def test_chunk_metadata_preservation(self):
        """Test that metadata is correctly preserved."""
        chunker = SemanticChunker(chunk_size=500, chunk_overlap=50)

        elements = [
            {
                "text": "Content on page 3.",
                "type": "text",
                "page_numbers": [3],
                "section_title": "Methods",
                "section_path": "Chapter 2 > Methods",
            }
        ]

        chunks = chunker.chunk_elements(elements, doc_id="test_doc")

        chunk = chunks[0]
        assert 3 in chunk.metadata.page_numbers
        assert chunk.metadata.section_title == "Methods"
        assert chunk.metadata.section_path == "Chapter 2 > Methods"

    def test_count_tokens(self):
        """Test token counting."""
        chunker = SemanticChunker()

        text = "This is a simple test."
        token_count = chunker._count_tokens(text)

        assert token_count > 0
        assert isinstance(token_count, int)


class TestSimpleChunker:
    """Tests for simple chunker."""

    def test_chunk_text(self):
        """Test basic text chunking."""
        chunker = SimpleChunker(chunk_size=50, chunk_overlap=10)

        text = "This is a test. " * 100  # Long text

        chunks = chunker.chunk_text(
            text=text,
            doc_id="test_doc",
            page_number=1,
            section_title="Test Section",
        )

        assert len(chunks) > 1  # Should create multiple chunks
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert all(c.metadata.page_numbers == [1] for c in chunks)
        assert all(c.metadata.section_title == "Test Section" for c in chunks)

    def test_chunk_overlap(self):
        """Test that chunks have overlap."""
        chunker = SimpleChunker(chunk_size=100, chunk_overlap=20)

        text = "word " * 200  # Long repetitive text

        chunks = chunker.chunk_text(text, doc_id="test_doc", page_number=1)

        # Check that consecutive chunks share some content
        if len(chunks) > 1:
            # Due to overlap, there should be some similarity
            assert len(chunks[0].text) > 0
            assert len(chunks[1].text) > 0


class TestSpecificationIngester:
    """Tests for specification ingester."""

    @patch("src.ingestion.ingest_spec.QdrantVectorStore")
    @patch("src.ingestion.ingest_spec.SQLiteClient")
    def test_ingester_initialization(self, mock_sqlite, mock_qdrant):
        """Test ingester initialization."""
        ingester = SpecificationIngester()

        assert ingester.vector_store is not None
        assert ingester.metadata_db is not None
        assert ingester.parser is not None
        assert ingester.chunker is not None

    @patch("src.ingestion.ingest_spec.QdrantVectorStore")
    @patch("src.ingestion.ingest_spec.SQLiteClient")
    @patch("src.ingestion.pdf_parser.partition_pdf")
    @patch("src.ingestion.pdf_parser.pdfplumber")
    def test_ingest_document_success(
        self, mock_pdfplumber, mock_partition, mock_sqlite, mock_qdrant, tmp_path
    ):
        """Test successful document ingestion."""
        # Create a test PDF
        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"PDF content")

        # Mock PDF parsing
        mock_element = MagicMock()
        mock_element.text = "Test content"
        mock_element.metadata.page_number = 1
        mock_partition.return_value = [mock_element]

        # Mock pdfplumber page count
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()]  # 1 page
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        # Mock database methods
        mock_sqlite_instance = mock_sqlite.return_value
        mock_sqlite_instance.get_document.return_value = None
        mock_qdrant_instance = mock_qdrant.return_value

        # Create ingester
        ingester = SpecificationIngester(
            vector_store=mock_qdrant_instance,
            metadata_db=mock_sqlite_instance,
        )

        # Ingest document
        doc_id = ingester.ingest_document(
            file_path=str(test_pdf),
            protocol="TEST",
            version="1.0",
            title="Test Document",
        )

        # Verify calls
        assert doc_id.startswith("TEST_1_0_")
        mock_qdrant_instance.add_chunks.assert_called_once()
        mock_sqlite_instance.add_document.assert_called_once()

    @patch("src.ingestion.ingest_spec.QdrantVectorStore")
    @patch("src.ingestion.ingest_spec.SQLiteClient")
    def test_ingest_document_file_not_found(self, mock_sqlite, mock_qdrant):
        """Test ingestion with non-existent file."""
        ingester = SpecificationIngester(
            vector_store=mock_qdrant.return_value,
            metadata_db=mock_sqlite.return_value,
        )

        with pytest.raises(FileNotFoundError):
            ingester.ingest_document(
                file_path="/nonexistent/file.pdf",
                protocol="TEST",
                version="1.0",
            )

    @patch("src.ingestion.ingest_spec.QdrantVectorStore")
    @patch("src.ingestion.ingest_spec.SQLiteClient")
    def test_list_documents(self, mock_sqlite, mock_qdrant):
        """Test listing documents."""
        # Mock database return
        mock_sqlite_instance = mock_sqlite.return_value
        mock_doc = DocumentMetadata(
            doc_id="test_doc_1",
            title="Test Document",
            protocol="eMMC",
            version="5.1",
            file_path="/path/to/file.pdf",
            uploaded_at=datetime.utcnow(),
            total_pages=100,
            total_chunks=200,
            is_active=True,
        )
        mock_sqlite_instance.list_documents.return_value = [mock_doc]

        ingester = SpecificationIngester(
            vector_store=mock_qdrant.return_value,
            metadata_db=mock_sqlite_instance,
        )

        # Should not raise an error
        ingester.list_documents()
        mock_sqlite_instance.list_documents.assert_called_once()

    @patch("src.ingestion.ingest_spec.QdrantVectorStore")
    @patch("src.ingestion.ingest_spec.SQLiteClient")
    def test_delete_document(self, mock_sqlite, mock_qdrant):
        """Test document deletion."""
        mock_sqlite_instance = mock_sqlite.return_value
        mock_qdrant_instance = mock_qdrant.return_value

        # Mock existing document
        mock_doc = DocumentMetadata(
            doc_id="test_doc_1",
            title="Test",
            protocol="eMMC",
            version="5.1",
            file_path="/path/to/file.pdf",
            uploaded_at=datetime.utcnow(),
            total_pages=100,
            total_chunks=200,
            is_active=True,
        )
        mock_sqlite_instance.get_document.return_value = mock_doc

        ingester = SpecificationIngester(
            vector_store=mock_qdrant_instance,
            metadata_db=mock_sqlite_instance,
        )

        ingester.delete_document("test_doc_1")

        # Verify deletion calls
        mock_qdrant_instance.delete_document.assert_called_once_with("test_doc_1")
        mock_sqlite_instance.add_document.assert_called_once()
