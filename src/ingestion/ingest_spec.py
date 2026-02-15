"""Document ingestion pipeline for protocol specifications."""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from .pdf_parser import PDFParser
from .chunker import SemanticChunker
from .chunker_factory import get_default_chunker
from ..database.qdrant_client import QdrantVectorStore
from ..database.sqlite_client import SQLiteClient
from ..models.schemas import DocumentMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SpecificationIngester:
    """Orchestrates the ingestion of protocol specification documents."""

    def __init__(
        self,
        vector_store: Optional[QdrantVectorStore] = None,
        metadata_db: Optional[SQLiteClient] = None,
        parser: Optional[PDFParser] = None,
        chunker: Optional[SemanticChunker] = None,
    ):
        """
        Initialize the ingester.

        Args:
            vector_store: Qdrant vector store
            metadata_db: SQLite metadata database
            parser: PDF parser
            chunker: Text chunker (defaults to configured chunker from factory)
        """
        self.vector_store = vector_store or QdrantVectorStore()
        self.metadata_db = metadata_db or SQLiteClient()
        self.parser = parser or PDFParser()
        self.chunker = chunker or get_default_chunker()

    def ingest_document(
        self,
        file_path: str,
        protocol: str,
        version: str,
        title: Optional[str] = None,
        strategy: str = "fast",
    ) -> str:
        """
        Ingest a protocol specification document.

        Args:
            file_path: Path to PDF file
            protocol: Protocol name (e.g., "eMMC", "UFS")
            version: Protocol version (e.g., "5.1")
            title: Document title (optional, will use filename if not provided)
            strategy: Parsing strategy - 'fast' or 'hi_res'

        Returns:
            Document ID of the ingested document
        """
        logger.info(f"Starting ingestion of {file_path}")

        # Validate file exists
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Generate document ID
        doc_id = PDFParser.generate_doc_id(file_path, protocol, version)
        logger.info(f"Generated doc_id: {doc_id}")

        # Check if document already exists
        existing_doc = self.metadata_db.get_document(doc_id)
        if existing_doc:
            logger.warning(f"Document {doc_id} already exists. Replacing...")
            self.vector_store.delete_document(doc_id)

        try:
            # Step 1: Parse PDF
            logger.info("Step 1/4: Parsing PDF...")
            elements = self.parser.parse_pdf(file_path, strategy=strategy)

            if not elements:
                raise ValueError("No elements extracted from PDF")

            # Step 2: Chunk elements
            logger.info("Step 2/4: Chunking elements...")
            chunks = self.chunker.chunk_elements(elements, doc_id)

            if not chunks:
                raise ValueError("No chunks created from elements")

            # Step 3: Generate embeddings and store in Qdrant
            logger.info("Step 3/4: Generating embeddings and storing in vector DB...")
            self.vector_store.add_chunks(chunks)

            # Step 4: Store metadata in SQLite
            logger.info("Step 4/4: Storing metadata...")
            total_pages = self.parser.get_total_pages(file_path)

            doc_title = title or pdf_path.stem
            doc_metadata = DocumentMetadata(
                doc_id=doc_id,
                title=doc_title,
                protocol=protocol,
                version=version,
                file_path=str(pdf_path.absolute()),
                uploaded_at=datetime.utcnow(),
                total_pages=total_pages,
                total_chunks=len(chunks),
                is_active=True,
            )
            self.metadata_db.add_document(doc_metadata)

            logger.info(
                f"✓ Successfully ingested document {doc_id} "
                f"({len(chunks)} chunks, {total_pages} pages)"
            )
            return doc_id

        except Exception as e:
            logger.error(f"Failed to ingest document: {e}")
            # Cleanup on failure
            try:
                self.vector_store.delete_document(doc_id)
            except Exception:
                pass
            raise

    def list_documents(self) -> None:
        """List all ingested documents."""
        docs = self.metadata_db.list_documents(active_only=True)

        if not docs:
            print("No documents found.")
            return

        print(f"\nFound {len(docs)} document(s):")
        print("-" * 100)
        print(
            f"{'Protocol':<15} {'Version':<10} {'Title':<30} {'Pages':<8} {'Chunks':<8} {'Uploaded':<20}"
        )
        print("-" * 100)

        for doc in docs:
            uploaded = doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"{doc.protocol:<15} {doc.version:<10} {doc.title[:28]:<30} "
                f"{doc.total_pages:<8} {doc.total_chunks:<8} {uploaded:<20}"
            )

        print("-" * 100)

    def delete_document(self, doc_id: str) -> None:
        """
        Delete a document from the system.

        Args:
            doc_id: Document ID to delete
        """
        logger.info(f"Deleting document {doc_id}")

        # Check if document exists
        doc = self.metadata_db.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        # Delete from vector store
        self.vector_store.delete_document(doc_id)

        # Mark as inactive in metadata DB
        doc.is_active = False
        self.metadata_db.add_document(doc)

        logger.info(f"✓ Successfully deleted document {doc_id}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest protocol specification documents"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a new document")
    ingest_parser.add_argument(
        "--file",
        "-f",
        required=True,
        help="Path to PDF file",
    )
    ingest_parser.add_argument(
        "--protocol",
        "-p",
        required=True,
        help="Protocol name (e.g., eMMC, UFS)",
    )
    ingest_parser.add_argument(
        "--version",
        "-v",
        required=True,
        help="Protocol version (e.g., 5.1)",
    )
    ingest_parser.add_argument(
        "--title",
        "-t",
        help="Document title (optional)",
    )
    ingest_parser.add_argument(
        "--strategy",
        "-s",
        choices=["fast", "hi_res"],
        default="fast",
        help="Parsing strategy (default: fast)",
    )

    # List command
    subparsers.add_parser("list", help="List all ingested documents")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a document")
    delete_parser.add_argument(
        "--doc-id",
        "-d",
        required=True,
        help="Document ID to delete",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize ingester
    ingester = SpecificationIngester()

    try:
        if args.command == "ingest":
            doc_id = ingester.ingest_document(
                file_path=args.file,
                protocol=args.protocol,
                version=args.version,
                title=args.title,
                strategy=args.strategy,
            )
            print(f"\n✓ Document ingested successfully!")
            print(f"  Document ID: {doc_id}")
            print(f"  Protocol: {args.protocol} v{args.version}")

        elif args.command == "list":
            ingester.list_documents()

        elif args.command == "delete":
            ingester.delete_document(args.doc_id)
            print(f"\n✓ Document {args.doc_id} deleted successfully!")

    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
