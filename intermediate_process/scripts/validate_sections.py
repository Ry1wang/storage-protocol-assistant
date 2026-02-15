"""Script to validate section-content relevance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from src.ingestion.section_validator import (
    SectionContentValidator,
    SectionCorrector,
    generate_quality_report,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_validation_on_problematic_chunk():
    """Test validation on the known problematic chunk."""
    print("\n=== Testing Section-Content Validation ===\n")

    validator = SectionContentValidator()
    client = QdrantClient(url="http://qdrant:6333")

    # Get the problematic chunk
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

    # Test with WRONG section
    print("**Test 1: Wrong Section (Current State)**")
    print(f"Section: '4KB'")
    print(f"Pages: {point.payload.get('page_numbers')}\n")

    result1 = validator.validate_section_relevance(
        chunk_text=point.payload.get("text", ""),
        section_title="4KB",
        section_path="4KB",
        page_numbers=point.payload.get("page_numbers"),
    )

    print(f"✅ Is Match: {result1['is_match']}")
    print(f"📊 Relevance Score: {result1['relevance_score']:.2f}")
    print(f"📝 Content Summary: {result1['content_summary']}")
    print(f"💡 Expected Section: {result1['expected_section']}")
    print(f"❓ Mismatch Reason: {result1['mismatch_reason']}\n")

    # Test with CORRECT section
    print("**Test 2: Correct Section**")
    print(f"Section: '6.6.34.1 Disabling emulation mode'\n")

    result2 = validator.validate_section_relevance(
        chunk_text=point.payload.get("text", ""),
        section_title="6.6.34.1 Disabling emulation mode",
        section_path="Chapter 6 > Commands > 6.6.34 Native Sector > 6.6.34.1",
        page_numbers=point.payload.get("page_numbers"),
    )

    print(f"✅ Is Match: {result2['is_match']}")
    print(f"📊 Relevance Score: {result2['relevance_score']:.2f}")
    print(f"📝 Content Summary: {result2['content_summary']}")
    print(f"🎯 Confidence: {result2['confidence']:.2f}\n")

    print("=" * 60)


def test_correction_with_validation():
    """Test combined correction and validation."""
    print("\n=== Testing Correction + Validation Pipeline ===\n")

    corrector = SectionCorrector()
    client = QdrantClient(url="http://qdrant:6333")

    # Get problematic chunk
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

    print("**Original State:**")
    print(f"Section: '{point.payload.get('section_title')}'")
    print(f"Path: '{point.payload.get('section_path')}'\n")

    # Correct and validate
    result = corrector.correct_and_validate(
        chunk_text=point.payload.get("text", ""),
        current_section_title=point.payload.get("section_title"),
        current_section_path=point.payload.get("section_path"),
        page_numbers=point.payload.get("page_numbers"),
    )

    print("**After Correction:**")
    print(f"Section: '{result['corrected_section_title']}'")
    print(f"Path: '{result['corrected_section_path']}'")
    print(f"Correction Confidence: {result['correction_confidence']:.2f}\n")

    print("**Validation Results:**")
    print(f"✅ Is Valid: {result['is_valid']}")
    print(f"📊 Relevance Score: {result['relevance_score']:.2f}")
    print(f"📝 Content: {result['content_summary']}")
    print(f"⚠️  Needs Review: {result['needs_review']}\n")


def validate_sample_chunks():
    """Validate a sample of chunks."""
    print("\n=== Validating Sample Chunks ===\n")

    validator = SectionContentValidator()
    client = QdrantClient(url="http://qdrant:6333")

    # Get a sample of chunks
    points = client.scroll(
        collection_name="protocol_specs",
        limit=20,
        with_payload=True,
        with_vectors=False,
    )

    chunks = [
        {
            "chunk_id": p.id,
            "text": p.payload.get("text", ""),
            "section_title": p.payload.get("section_title"),
            "section_path": p.payload.get("section_path"),
            "page_numbers": p.payload.get("page_numbers"),
        }
        for p in points[0]
    ]

    print(f"Validating {len(chunks)} sample chunks...\n")

    validated, stats = validator.batch_validate_chunks(chunks, threshold=0.7)

    print("\n**Results:**")
    print(f"Total: {stats['total_chunks']}")
    print(f"Matches: {stats['matches']} ({stats['matches']/stats['total_chunks']*100:.1f}%)")
    print(f"Mismatches: {stats['mismatches']}")
    print(f"Low Relevance: {stats['low_relevance']}")
    print(f"Errors: {stats['errors']}\n")

    # Show quality report
    report = generate_quality_report(validated)
    print(report)


def calculate_validation_costs():
    """Calculate costs for validation."""
    print("\n=== Validation Cost Analysis ===\n")

    # DeepSeek pricing
    COST_PER_1M_INPUT = 0.14
    COST_PER_1M_OUTPUT = 0.28

    # Validation token usage (slightly higher than correction)
    AVG_INPUT_TOKENS = 900  # Prompt + chunk + validation logic
    AVG_OUTPUT_TOKENS = 200  # JSON with validation details

    # Document stats
    TOTAL_CHUNKS = 382

    print("**DeepSeek-Chat Pricing:**")
    print(f"Input: ${COST_PER_1M_INPUT} per 1M tokens")
    print(f"Output: ${COST_PER_1M_OUTPUT} per 1M tokens\n")

    # Scenario 1: Validate ALL chunks
    input_cost = (TOTAL_CHUNKS * AVG_INPUT_TOKENS / 1_000_000) * COST_PER_1M_INPUT
    output_cost = (TOTAL_CHUNKS * AVG_OUTPUT_TOKENS / 1_000_000) * COST_PER_1M_OUTPUT
    total_cost = input_cost + output_cost

    print("**Scenario 1: Validate ALL chunks**")
    print(f"Chunks: {TOTAL_CHUNKS}")
    print(f"Input tokens: {TOTAL_CHUNKS * AVG_INPUT_TOKENS:,}")
    print(f"Output tokens: {TOTAL_CHUNKS * AVG_OUTPUT_TOKENS:,}")
    print(f"Cost: ${total_cost:.4f}\n")

    # Scenario 2: Correct + Validate (2 API calls per chunk)
    CORRECTED_CHUNKS = 229  # Only problematic ones
    correction_tokens_in = 800
    correction_tokens_out = 150
    validation_tokens_in = 900
    validation_tokens_out = 200

    correction_cost = (
        CORRECTED_CHUNKS * correction_tokens_in / 1_000_000
    ) * COST_PER_1M_INPUT + (
        CORRECTED_CHUNKS * correction_tokens_out / 1_000_000
    ) * COST_PER_1M_OUTPUT

    validation_cost = (
        CORRECTED_CHUNKS * validation_tokens_in / 1_000_000
    ) * COST_PER_1M_INPUT + (
        CORRECTED_CHUNKS * validation_tokens_out / 1_000_000
    ) * COST_PER_1M_OUTPUT

    total_qa_cost = correction_cost + validation_cost

    print("**Scenario 2: Correct + Validate (Full QA Pipeline)**")
    print(f"Chunks needing correction: {CORRECTED_CHUNKS}")
    print(f"Correction cost: ${correction_cost:.4f}")
    print(f"Validation cost: ${validation_cost:.4f}")
    print(f"Total QA cost: ${total_qa_cost:.4f}\n")

    # Scenario 3: Sample validation (QA check)
    SAMPLE_SIZE = 50  # Validate random sample
    sample_cost = (
        SAMPLE_SIZE * AVG_INPUT_TOKENS / 1_000_000
    ) * COST_PER_1M_INPUT + (
        SAMPLE_SIZE * AVG_OUTPUT_TOKENS / 1_000_000
    ) * COST_PER_1M_OUTPUT

    print("**Scenario 3: Sample Validation (Quality Check)**")
    print(f"Sample size: {SAMPLE_SIZE} chunks")
    print(f"Cost: ${sample_cost:.4f}")
    print(f"Use case: Spot-check quality after correction\n")

    print("**Summary:**")
    print(f"Correction only:     ${0.0353:.4f}")
    print(f"Validation only:     ${total_cost:.4f}")
    print(f"Full QA pipeline:    ${total_qa_cost:.4f}")
    print(f"Sample QA check:     ${sample_cost:.4f}\n")

    print("**Recommendation:**")
    print("1. Correct problematic sections: $0.04")
    print("2. Validate corrected chunks: $0.04")
    print("3. Total with full QA: $0.08\n")
    print("✅ Still extremely affordable!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate section-content relevance")
    parser.add_argument(
        "command",
        choices=["test", "qa", "sample", "cost"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "test":
        test_validation_on_problematic_chunk()
    elif args.command == "qa":
        test_correction_with_validation()
    elif args.command == "sample":
        validate_sample_chunks()
    elif args.command == "cost":
        calculate_validation_costs()
