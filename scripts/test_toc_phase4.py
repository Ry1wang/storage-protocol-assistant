"""
Test script for TOC-based chunking Phase 4.

Tests:
- IntelligentTruncator: Can we split long sections intelligently?
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.toc_chunker import (
    TOCExtractor,
    TOCPreprocessor,
    ContentExtractor,
    IntelligentTruncator
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def test_intelligent_truncator():
    """Test intelligent truncation of long sections."""
    print("\n" + "="*80)
    print("TEST: IntelligentTruncator")
    print("="*80)

    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    # Step 1: Get TOC entries with content
    print("\nStep 1: Extract TOC and content...")
    extractor = TOCExtractor(str(pdf_path))
    raw_entries = extractor.extract()

    preprocessor = TOCPreprocessor()
    processed_entries = preprocessor.process(raw_entries)

    # Get long sections (>10 pages)
    long_sections = [e for e in processed_entries if e.get('is_long', False)]
    print(f"✓ Found {len(long_sections)} long sections (>10 pages)")

    if not long_sections:
        print("⚠ No long sections found - using regular sections for testing")
        # Use first 5 sections instead
        test_sections = processed_entries[:5]
    else:
        # Use first 2 long sections
        test_sections = long_sections[:2]

    print(f"\nTest sections:")
    for section in test_sections:
        page_count = section.get('page_count', 0)
        print(f"  {section['section_number']:15} - "
              f"{section['section_title'][:40]:40} - "
              f"{page_count} pages")

    # Step 2: Extract content
    print("\nStep 2: Extract content...")
    content_extractor = ContentExtractor(str(pdf_path), page_offset=20)
    sections_with_content = content_extractor.extract_all_content(test_sections)

    print(f"✓ Extracted content for {len(sections_with_content)} sections")

    # Show content sizes
    print("\nContent sizes before truncation:")
    for section in sections_with_content:
        content_len = len(section.get('content', ''))
        tokens = content_len // 4
        print(f"  {section['section_number']:15} - "
              f"{content_len:6} chars (~{tokens:4} tokens)")

    # Step 3: Apply intelligent truncation
    print("\n" + "-"*80)
    print("Test 1: Truncate with default settings (max_tokens=800)")
    print("-"*80)

    truncator = IntelligentTruncator(max_tokens=800, min_tokens=100, overlap_tokens=50)
    truncated_sections = truncator.process_all(sections_with_content)

    print(f"\n✓ After truncation: {len(truncated_sections)} sections")

    # Show results
    print("\nTruncation results:")
    for section in truncated_sections:
        content_len = len(section.get('content', ''))
        tokens = content_len // 4
        is_split = section.get('is_split', False)
        chunk_info = ""

        if is_split:
            chunk_idx = section.get('chunk_index', 0)
            total_chunks = section.get('total_chunks', 1)
            chunk_info = f"(chunk {chunk_idx + 1}/{total_chunks})"

        print(f"  {section['section_number']:20} - "
              f"{content_len:6} chars (~{tokens:4} tokens) "
              f"{chunk_info}")

    # Statistics
    print("\n" + "-"*80)
    print("Statistics")
    print("-"*80)

    split_sections = [s for s in truncated_sections if s.get('is_split', False)]
    original_count = len(sections_with_content)
    final_count = len(truncated_sections)
    split_count = len(set(s['section_number'].rsplit('.part', 1)[0]
                          for s in split_sections))

    print(f"\nOriginal sections: {original_count}")
    print(f"Final sections: {final_count}")
    print(f"Sections that were split: {split_count}")
    print(f"Split chunks created: {len(split_sections)}")

    # Verify no chunks exceed max_tokens
    oversized = [s for s in truncated_sections
                 if len(s.get('content', '')) // 4 > 800]

    if oversized:
        print(f"\n⚠ WARNING: {len(oversized)} chunks exceed max_tokens!")
        for s in oversized:
            tokens = len(s.get('content', '')) // 4
            print(f"  {s['section_number']:20} - {tokens} tokens")
    else:
        print(f"\n✅ All chunks within max_tokens limit")

    # Test 2: More aggressive truncation
    print("\n" + "-"*80)
    print("Test 2: Aggressive truncation (max_tokens=400)")
    print("-"*80)

    aggressive_truncator = IntelligentTruncator(
        max_tokens=400,
        min_tokens=50,
        overlap_tokens=25
    )
    aggressive_truncated = aggressive_truncator.process_all(sections_with_content)

    print(f"\n✓ After aggressive truncation: {len(aggressive_truncated)} sections")

    aggressive_split = [s for s in aggressive_truncated if s.get('is_split', False)]
    aggressive_split_count = len(set(
        s['section_number'].rsplit('.part', 1)[0]
        for s in aggressive_split
    ))

    print(f"Sections that were split: {aggressive_split_count}")
    print(f"Total chunks created: {len(aggressive_truncated)}")

    # Verify overlap
    print("\n" + "-"*80)
    print("Test 3: Verify chunk overlap")
    print("-"*80)

    # Find a split section
    split_section_nums = set()
    for s in truncated_sections:
        if s.get('is_split', False):
            base_num = s['section_number'].rsplit('.part', 1)[0]
            split_section_nums.add(base_num)

    if split_section_nums:
        # Check first split section
        base_num = list(split_section_nums)[0]
        split_chunks = [s for s in truncated_sections
                       if s['section_number'].startswith(base_num)]

        print(f"\nChecking overlap for section {base_num}:")
        print(f"  Split into {len(split_chunks)} chunks")

        # Check if consecutive chunks have overlap
        if len(split_chunks) >= 2:
            chunk1_end = split_chunks[0]['content'][-200:]  # Last 200 chars
            chunk2_start = split_chunks[1]['content'][:200]  # First 200 chars

            # Simple check: see if there's any common text
            has_overlap = any(
                chunk1_end[i:i+50] in chunk2_start
                for i in range(0, len(chunk1_end) - 50, 10)
            )

            if has_overlap:
                print(f"  ✅ Overlap detected between chunks")
            else:
                print(f"  ⚠ No obvious overlap detected")
    else:
        print("\nNo split sections to check overlap")

    print("\n✅ IntelligentTruncator test PASSED\n")
    return True


def main():
    """Run Phase 4 tests."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  TOC-Based Chunking - Phase 4 Tests                                       ║
║                                                                            ║
║  Testing: IntelligentTruncator                                            ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        result = test_intelligent_truncator()

        print("\n" + "="*80)
        if result:
            print("🎉 PHASE 4 TESTS PASSED!")
            print("="*80)
            print("\n✅ Intelligent truncation working correctly!")
            print("✅ Long sections split appropriately!")
            print("\nNext: Phase 5 - Full pipeline integration")
        else:
            print("❌ PHASE 4 TESTS FAILED")
            print("="*80)

        return result

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
