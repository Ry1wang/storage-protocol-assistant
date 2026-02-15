"""Test script for RAG system with sample queries."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.qdrant_client import QdrantVectorStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_query(vector_store, query_text, top_k=3):
    """Test a single query and display results."""
    print(f"\n{'=' * 100}")
    print(f"QUERY: \"{query_text}\"")
    print(f"{'=' * 100}\n")

    # Search for relevant chunks
    results = vector_store.search(
        query=query_text,
        top_k=top_k,
        filters={"protocol": "eMMC"},
        min_score=0.5  # Lower threshold to get more results
    )

    if not results:
        print("❌ No results found!")
        return

    print(f"Found {len(results)} relevant chunks:\n")

    for i, result in enumerate(results, 1):
        score = result.get('score', 0.0)
        text = result.get('text', '')
        section_title = result.get('section_title', 'N/A')
        section_path = result.get('section_path', 'N/A')
        pages = result.get('page_numbers', [])
        doc_id = result.get('doc_id', 'N/A')

        # Extract protocol and version from doc_id (e.g., "eMMC_5_1_...")
        protocol = "eMMC"
        version = "5.1"

        # Format citation
        citation = f"{protocol} {version}, Section: \"{section_title}\", Pages: {pages}"

        print(f"**Result {i}:** (Similarity: {score:.4f})")
        print(f"  📍 Citation: {citation}")
        print(f"  📂 Section Path: {section_path}")
        print(f"  📄 Preview: {text[:200].replace(chr(10), ' ')}...")
        print()

    print("-" * 100)


def run_test_suite():
    """Run a comprehensive test suite."""
    print("\n" + "=" * 100)
    print("RAG SYSTEM TEST SUITE")
    print("=" * 100)

    # Initialize vector store
    print("\nInitializing vector store...")
    vector_store = QdrantVectorStore()

    # Get collection info
    try:
        collection_info = vector_store.client.get_collection('protocol_specs')
        print(f"✅ Collection 'protocol_specs' found")
        print(f"   Total chunks: {collection_info.points_count}")
        print(f"   Vector size: {collection_info.config.params.vectors.size}")
    except Exception as e:
        print(f"❌ Error accessing collection: {e}")
        return

    # Test queries
    test_queries = [
        # Query 1: Our previously problematic chunk
        "How do I disable emulation mode?",

        # Query 2: Timing modes
        "What is HS400 timing mode?",

        # Query 3: RPMB access
        "Explain RPMB partition access",

        # Query 4: Power management
        "How does sleep mode work in eMMC?",

        # Query 5: Sector size
        "What is native 4KB sector size?",
    ]

    for query in test_queries:
        test_query(vector_store, query, top_k=3)

    print("\n" + "=" * 100)
    print("TEST SUITE COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    run_test_suite()
