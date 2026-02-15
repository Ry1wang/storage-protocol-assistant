"""Example script demonstrating document ingestion."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.ingest_spec import SpecificationIngester
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Example ingestion workflow."""

    # Initialize ingester
    logger.info("Initializing ingester...")
    ingester = SpecificationIngester()

    # Example 1: Ingest a document
    logger.info("\n=== Example 1: Ingest a Document ===")
    try:
        doc_id = ingester.ingest_document(
            file_path="specs/example_spec.pdf",  # Replace with your PDF
            protocol="eMMC",
            version="5.1",
            title="eMMC Specification v5.1",
            strategy="fast",  # Use "hi_res" for OCR
        )
        print(f"✓ Document ingested successfully!")
        print(f"  Doc ID: {doc_id}")
    except FileNotFoundError:
        print("⚠ Example PDF not found. Please add a PDF to specs/ directory")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Example 2: List all documents
    logger.info("\n=== Example 2: List Documents ===")
    ingester.list_documents()

    # Example 3: Query the vector store
    logger.info("\n=== Example 3: Search for Similar Chunks ===")
    try:
        results = ingester.vector_store.search(
            query="What is the maximum data transfer rate?",
            top_k=5,
        )

        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Score: {result['score']:.3f}")
            print(f"   Pages: {result['page_numbers']}")
            print(f"   Section: {result.get('section_title', 'N/A')}")
            print(f"   Text: {result['text'][:150]}...")

    except Exception as e:
        print(f"Search failed: {e}")

    # Example 4: Programmatic chunking
    logger.info("\n=== Example 4: Programmatic Chunking ===")
    from src.ingestion.chunker import SimpleChunker

    chunker = SimpleChunker(chunk_size=200, chunk_overlap=20)
    sample_text = """
    eMMC (embedded MultiMediaCard) is an embedded non-volatile memory system,
    which comprises flash memory and a flash memory controller, integrated on
    the same silicon die. The eMMC standard defines the interface between the
    host and the eMMC device.
    """

    chunks = chunker.chunk_text(
        text=sample_text,
        doc_id="example_doc",
        page_number=1,
        section_title="Introduction",
    )

    print(f"\nCreated {len(chunks)} chunk(s) from sample text:")
    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}:")
        print(f"  Tokens: ~{len(chunk.text.split())}")
        print(f"  Text: {chunk.text[:100]}...")


if __name__ == "__main__":
    main()
