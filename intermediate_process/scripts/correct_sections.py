"""Script to correct section titles using DeepSeek LLM."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from src.ingestion.section_corrector import SectionTitleCorrector, SelectiveCorrector
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_single_chunk():
    """Test correction on a single problematic chunk."""
    print("\n=== Testing Single Chunk Correction ===\n")

    # Initialize corrector
    corrector = SectionTitleCorrector()

    # Get the problematic chunk
    client = QdrantClient(url="http://qdrant:6333")
    points = client.retrieve(
        collection_name="protocol_specs",
        ids=["08393725-75a5-407e-9bdd-dfe9bfce07d4"],
        with_payload=True,
        with_vectors=False,
    )

    if not points:
        print("❌ Chunk not found")
        return

    point = points[0]
    chunk = {
        "text": point.payload.get("text", ""),
        "section_title": point.payload.get("section_title"),
        "section_path": point.payload.get("section_path"),
        "page_numbers": point.payload.get("page_numbers"),
    }

    print(f"**BEFORE:**")
    print(f"  Section Title: '{chunk['section_title']}'")
    print(f"  Section Path: '{chunk['section_path']}'")
    print(f"  Pages: {chunk['page_numbers']}")

    # Correct
    result = corrector.correct_section_metadata(
        chunk_text=chunk["text"],
        current_section_title=chunk["section_title"],
        current_section_path=chunk["section_path"],
        page_numbers=chunk["page_numbers"],
    )

    print(f"\n**AFTER:**")
    print(f"  Section Title: '{result['section_title']}'")
    print(f"  Section Path: '{result['section_path']}'")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Reasoning: {result['reasoning']}")

    print("\n✅ Single chunk test complete")


def correct_all_problematic():
    """Correct all problematic chunks in the database."""
    print("\n=== Correcting All Problematic Chunks ===\n")

    # Initialize
    corrector = SectionTitleCorrector()
    selective = SelectiveCorrector(corrector)
    client = QdrantClient(url="http://qdrant:6333")

    # Get all chunks
    print("Fetching chunks from Qdrant...")
    all_points = []
    offset = None

    while True:
        result = client.scroll(
            collection_name="protocol_specs",
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        points, offset = result
        all_points.extend(points)

        if offset is None:
            break

    print(f"Retrieved {len(all_points)} chunks")

    # Convert to chunk format
    chunks = [
        {
            "id": point.id,
            "text": point.payload.get("text", ""),
            "section_title": point.payload.get("section_title"),
            "section_path": point.payload.get("section_path"),
            "page_numbers": point.payload.get("page_numbers"),
        }
        for point in all_points
    ]

    # Correct problematic ones
    print("\nAnalyzing and correcting problematic chunks...")
    corrected_chunks, stats = selective.correct_problematic_chunks(chunks)

    print("\n**Statistics:**")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Corrected: {stats['corrected_chunks']}")
    print(f"  Skipped (already good): {stats['skipped_chunks']}")
    print(f"  Failed: {stats['failed_corrections']}")

    # Update Qdrant
    if stats["corrected_chunks"] > 0:
        response = input(f"\nUpdate {stats['corrected_chunks']} chunks in Qdrant? (yes/no): ")

        if response.lower() == "yes":
            print("Updating Qdrant...")

            for chunk in corrected_chunks:
                if "correction_confidence" in chunk:
                    # This chunk was corrected
                    client.set_payload(
                        collection_name="protocol_specs",
                        payload={
                            "section_title": chunk["section_title"],
                            "section_path": chunk["section_path"],
                        },
                        points=[chunk["id"]],
                    )

            print("✅ Qdrant updated successfully")
        else:
            print("❌ Skipped Qdrant update")


def calculate_costs():
    """Calculate cost estimates for different scenarios."""
    print("\n=== Cost Calculation ===\n")

    # DeepSeek pricing (as of 2024)
    # https://platform.deepseek.com/api-docs/pricing
    COST_PER_1M_INPUT_TOKENS = 0.14  # $0.14 per 1M input tokens
    COST_PER_1M_OUTPUT_TOKENS = 0.28  # $0.28 per 1M output tokens

    # Average token counts
    AVG_INPUT_TOKENS = 800  # Prompt + chunk text (truncated to ~2000 chars)
    AVG_OUTPUT_TOKENS = 150  # JSON response with title and path

    # Document stats
    TOTAL_CHUNKS = 382
    PROBLEMATIC_CHUNKS = int(TOTAL_CHUNKS * 0.6)  # ~60% need correction

    print("**DeepSeek Pricing:**")
    print(f"  Input: ${COST_PER_1M_INPUT_TOKENS} per 1M tokens")
    print(f"  Output: ${COST_PER_1M_OUTPUT_TOKENS} per 1M tokens")

    print(f"\n**Your eMMC Document:**")
    print(f"  Total chunks: {TOTAL_CHUNKS}")
    print(f"  Problematic chunks (est.): {PROBLEMATIC_CHUNKS}")

    # Scenario 1: Correct all chunks
    input_cost_all = (TOTAL_CHUNKS * AVG_INPUT_TOKENS / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost_all = (TOTAL_CHUNKS * AVG_OUTPUT_TOKENS / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    total_cost_all = input_cost_all + output_cost_all

    print(f"\n**Scenario 1: Correct ALL chunks**")
    print(f"  Chunks: {TOTAL_CHUNKS}")
    print(f"  Input tokens: {TOTAL_CHUNKS * AVG_INPUT_TOKENS:,}")
    print(f"  Output tokens: {TOTAL_CHUNKS * AVG_OUTPUT_TOKENS:,}")
    print(f"  Input cost: ${input_cost_all:.4f}")
    print(f"  Output cost: ${output_cost_all:.4f}")
    print(f"  Total cost: ${total_cost_all:.4f}")

    # Scenario 2: Correct only problematic chunks
    input_cost_selective = (PROBLEMATIC_CHUNKS * AVG_INPUT_TOKENS / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost_selective = (PROBLEMATIC_CHUNKS * AVG_OUTPUT_TOKENS / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    total_cost_selective = input_cost_selective + output_cost_selective

    print(f"\n**Scenario 2: Correct ONLY problematic chunks (Recommended)**")
    print(f"  Chunks: {PROBLEMATIC_CHUNKS}")
    print(f"  Input tokens: {PROBLEMATIC_CHUNKS * AVG_INPUT_TOKENS:,}")
    print(f"  Output tokens: {PROBLEMATIC_CHUNKS * AVG_OUTPUT_TOKENS:,}")
    print(f"  Input cost: ${input_cost_selective:.4f}")
    print(f"  Output cost: ${output_cost_selective:.4f}")
    print(f"  Total cost: ${total_cost_selective:.4f}")
    print(f"  Savings vs. Scenario 1: ${total_cost_all - total_cost_selective:.4f}")

    # Scenario 3: Multiple documents
    NUM_DOCS = 10
    total_cost_multi = total_cost_selective * NUM_DOCS

    print(f"\n**Scenario 3: {NUM_DOCS} documents (selective correction)**")
    print(f"  Total chunks: {TOTAL_CHUNKS * NUM_DOCS:,}")
    print(f"  Corrected chunks: {PROBLEMATIC_CHUNKS * NUM_DOCS:,}")
    print(f"  Total cost: ${total_cost_multi:.2f}")

    print(f"\n**Summary:**")
    print(f"  ✅ Single document (selective): ${total_cost_selective:.4f}")
    print(f"  ✅ Very affordable for high-quality citations!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Correct section titles using LLM")
    parser.add_argument(
        "command",
        choices=["test", "correct", "cost"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "test":
        test_single_chunk()
    elif args.command == "correct":
        correct_all_problematic()
    elif args.command == "cost":
        calculate_costs()
