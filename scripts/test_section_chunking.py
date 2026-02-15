"""Test script for section-aware chunking."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.section_aware_chunker import SectionAwareChunker
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_section_detection():
    """Test section number extraction and boundary detection."""
    print("\n=== Testing Section Detection ===\n")

    chunker = SectionAwareChunker(
        chunk_size=350,
        chunk_overlap=30,
        section_boundary_levels=3,
    )

    # Test cases
    test_cases = [
        # (old_section, new_section, expected_is_major_change)
        ("6.6.34.1 Disabling emulation", "6.6.34.2 Native behavior", False),  # Same parent (4 levels)
        ("6.6.34 Native Sector", "6.6.35 Sleep Mode", True),  # Different at level 3
        ("6.6 Commands", "6.7 Bus Protocol", True),  # Different at level 2
        ("Chapter 6", "Chapter 7", True),  # Different top level
        ("B.2.5 Task A", "B.2.6 Task B", True),  # Different at level 2 (2 levels same as 6.6→6.7)
        ("Introduction", "6.1 Overview", True),  # No numbers to match
    ]

    print("Testing Section Boundary Detection:")
    print("-" * 80)

    for old_sec, new_sec, expected in test_cases:
        old_nums = chunker._extract_section_numbers(old_sec)
        new_nums = chunker._extract_section_numbers(new_sec)
        is_major = chunker._is_major_section_change(old_sec, new_sec)

        status = "✅" if is_major == expected else "❌"

        print(f"{status} '{old_sec}' → '{new_sec}'")
        print(f"   Old numbers: {old_nums}, New numbers: {new_nums}")
        print(f"   Is major change: {is_major} (expected: {expected})")
        print()

    print("-" * 80)


def test_chunking_behavior():
    """Test chunking with section boundaries."""
    print("\n=== Testing Chunking Behavior ===\n")

    # Create test elements simulating a document
    test_elements = [
        {
            "text": "This is content from section 6.6.34. It contains information about native sectors.",
            "type": "paragraph",
            "page_numbers": [129],
            "section_title": "6.6.34 Native Sector",
            "section_path": "Chapter 6 > Commands > 6.6.34",
        },
        {
            "text": "6.6.34.1 Disabling emulation mode. To disable emulation mode, write 0x01 to USE_NATIVE_SECTOR field.",
            "type": "paragraph",
            "page_numbers": [129],
            "section_title": "6.6.34.1 Disabling emulation mode",
            "section_path": "Chapter 6 > Commands > 6.6.34 > 6.6.34.1",
        },
        {
            "text": "The device shall change DATA_SECTOR_SIZE after power cycle.",
            "type": "paragraph",
            "page_numbers": [129],
            "section_title": "6.6.34.1 Disabling emulation mode",
            "section_path": "Chapter 6 > Commands > 6.6.34 > 6.6.34.1",
        },
        {
            "text": "6.6.34.2 Native 4KB sector behavior. When operating in native mode, sector addressing is aligned to 8.",
            "type": "paragraph",
            "page_numbers": [130],
            "section_title": "6.6.34.2 Native 4KB sector behavior",
            "section_path": "Chapter 6 > Commands > 6.6.34 > 6.6.34.2",
        },
        {
            "text": "Single block commands CMD17 and CMD24 are not supported in native mode.",
            "type": "paragraph",
            "page_numbers": [130],
            "section_title": "6.6.34.2 Native 4KB sector behavior",
            "section_path": "Chapter 6 > Commands > 6.6.34 > 6.6.34.2",
        },
        {
            "text": "6.6.35 Sleep Mode. The device can enter sleep mode to reduce power consumption.",
            "type": "paragraph",
            "page_numbers": [131],
            "section_title": "6.6.35 Sleep Mode",
            "section_path": "Chapter 6 > Commands > 6.6.35",
        },
    ]

    chunker = SectionAwareChunker(
        chunk_size=100,  # Small size to force splits
        chunk_overlap=10,
        min_chunk_size=30,
        max_chunk_size=200,
        section_boundary_levels=3,  # Split at 6.6.34 → 6.6.35
    )

    chunks = chunker.chunk_elements(test_elements, doc_id="test-doc")

    print(f"Created {len(chunks)} chunks from {len(test_elements)} elements\n")
    print("=" * 80)

    for i, chunk in enumerate(chunks, 1):
        print(f"\n**Chunk {i}:**")
        print(f"Section: {chunk.metadata.section_title}")
        print(f"Pages: {chunk.metadata.page_numbers}")
        print(f"Tokens: {chunker._count_tokens(chunk.text)}")
        print(f"Text preview: {chunk.text[:100]}...")
        print("-" * 80)

    # Validate expectations
    print("\n=== Validation ===\n")

    # Check that no chunk spans 6.6.34 → 6.6.35 boundary
    has_cross_section_chunks = False
    for chunk in chunks:
        text = chunk.text
        has_6_6_34 = "6.6.34" in text
        has_6_6_35 = "6.6.35" in text

        if has_6_6_34 and has_6_6_35:
            print(f"❌ Found chunk spanning 6.6.34 → 6.6.35 boundary!")
            has_cross_section_chunks = True

    if not has_cross_section_chunks:
        print("✅ No chunks span major section boundaries (6.6.34 → 6.6.35)")

    # Check chunk sizes
    for i, chunk in enumerate(chunks, 1):
        tokens = chunker._count_tokens(chunk.text)
        if tokens < chunker.min_chunk_size:
            print(f"⚠️  Chunk {i} below minimum size: {tokens} tokens")
        elif tokens > chunker.max_chunk_size:
            print(f"❌ Chunk {i} exceeds maximum size: {tokens} tokens")

    print("\n✅ Section-aware chunking test complete!")


def test_section_number_extraction():
    """Test section number extraction."""
    print("\n=== Testing Section Number Extraction ===\n")

    chunker = SectionAwareChunker()

    test_sections = [
        "6.6.34.1 Disabling emulation mode",
        "6.6.34 Native Sector",
        "6.6 Commands",
        "B.2.6 Queue Tasks",
        "Introduction",
        "7.4.51 SLEEP_NOTIFICATION_TIME [216]",
        "1.2.3.4.5 Deep nesting",
    ]

    print("Section Number Extraction:")
    print("-" * 80)

    for section in test_sections:
        numbers = chunker._extract_section_numbers(section)
        print(f"'{section}' → {numbers}")

    print("-" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test section-aware chunking")
    parser.add_argument(
        "test",
        nargs="?",
        choices=["detection", "chunking", "extraction", "all"],
        default="all",
        help="Which test to run",
    )

    args = parser.parse_args()

    if args.test in ["detection", "all"]:
        test_section_detection()

    if args.test in ["extraction", "all"]:
        test_section_number_extraction()

    if args.test in ["chunking", "all"]:
        test_chunking_behavior()

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)
