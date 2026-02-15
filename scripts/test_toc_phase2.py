"""
Test script for TOC-based chunking Phase 2.

Tests:
- BoundedRegexSearcher: Can we find subsections like 6.6.2.3?
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.toc_chunker import (
    TOCExtractor,
    TOCPreprocessor,
    BoundedRegexSearcher
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def test_bounded_regex_searcher():
    """Test bounded regex search for subsections."""
    print("\n" + "="*80)
    print("TEST: BoundedRegexSearcher")
    print("="*80)

    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    # First get preprocessed TOC entries
    print("\nExtracting and preprocessing TOC...")
    extractor = TOCExtractor(str(pdf_path))
    raw_entries = extractor.extract()

    preprocessor = TOCPreprocessor()
    processed_entries = preprocessor.process(raw_entries)

    print(f"✓ Got {len(processed_entries)} preprocessed entries")

    # Create searcher
    searcher = BoundedRegexSearcher(str(pdf_path))

    # Test 1: Search specific section 6.6.2 (parent of our problematic 6.6.2.3)
    print("\n" + "-"*80)
    print("Test 1: Search for subsections of 6.6.2")
    print("-"*80)

    section_6_6_2 = next(
        (e for e in processed_entries if e['section_number'] == '6.6.2'),
        None
    )

    if not section_6_6_2:
        print("❌ Section 6.6.2 not found in TOC")
        return False

    print(f"\nParent section: 6.6.2 '{section_6_6_2['section_title']}'")
    print(f"Page range: {section_6_6_2['page_start']}-{section_6_6_2['page_end']}")

    subsections_6_6_2 = searcher.find_subsections(section_6_6_2)

    print(f"\n✓ Found {len(subsections_6_6_2)} subsections:")
    for sub in subsections_6_6_2:
        print(f"  {sub['section_number']:15} - {sub['section_title'][:60]:60} (p. {sub['page_number']})")

    # Critical check: Did we find 6.6.2.3?
    section_6_6_2_3 = next(
        (s for s in subsections_6_6_2 if s['section_number'] == '6.6.2.3'),
        None
    )

    if section_6_6_2_3:
        print(f"\n✅ SUCCESS! Found our problematic section:")
        print(f"   Section: 6.6.2.3")
        print(f"   Title: {section_6_6_2_3['section_title']}")
        print(f"   Page: {section_6_6_2_3['page_number']}")
        print(f"   This is the section with missing subtitle!")
    else:
        print(f"\n❌ FAILED: Did not find section 6.6.2.3")
        return False

    # Test 2: Search all entries
    print("\n" + "-"*80)
    print("Test 2: Search all TOC entries for subsections")
    print("-"*80)

    all_subsections = searcher.search_all(processed_entries)

    print(f"\n✓ Found {len(all_subsections)} total subsections across all entries")

    # Show samples
    print("\nSample subsections:")
    for sub in all_subsections[:20]:
        print(f"  {sub['section_number']:15} - {sub['section_title'][:60]:60} (p. {sub['page_number']})")

    # Check that 6.6.2.3 is in the full list too
    assert any(
        s['section_number'] == '6.6.2.3' for s in all_subsections
    ), "6.6.2.3 should be in full subsection list"

    # Test 3: Check for other known subsections
    print("\n" + "-"*80)
    print("Test 3: Verify other known subsections")
    print("-"*80)

    known_subsections = ['6.6.2.1', '6.6.2.2', '6.6.2.3', '6.6.5.1', '6.6.7.1']
    found_count = 0

    for known in known_subsections:
        if any(s['section_number'] == known for s in all_subsections):
            found_count += 1
            sub = next(s for s in all_subsections if s['section_number'] == known)
            print(f"  ✓ {known:15} - {sub['section_title'][:50]:50}")
        else:
            print(f"  ⚠ {known:15} - Not found (may not exist in spec)")

    print(f"\n✓ Found {found_count}/{len(known_subsections)} known subsections")

    # Statistics
    print("\n" + "-"*80)
    print("Statistics")
    print("-"*80)

    # Count by parent
    from collections import defaultdict
    by_parent = defaultdict(list)

    for sub in all_subsections:
        by_parent[sub['parent']].append(sub)

    print(f"\nParent sections with subsections: {len(by_parent)}")
    print(f"Total subsections found: {len(all_subsections)}")

    # Show top parents with most subsections
    top_parents = sorted(by_parent.items(), key=lambda x: len(x[1]), reverse=True)[:10]

    print("\nTop 10 parents with most subsections:")
    for parent, subs in top_parents:
        print(f"  {parent:15} has {len(subs):3} subsections")

    print("\n✅ BoundedRegexSearcher test PASSED\n")
    return True


def main():
    """Run Phase 2 tests."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  TOC-Based Chunking - Phase 2 Tests                                       ║
║                                                                            ║
║  Testing: BoundedRegexSearcher                                            ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        result = test_bounded_regex_searcher()

        print("\n" + "="*80)
        if result:
            print("🎉 PHASE 2 TESTS PASSED!")
            print("="*80)
            print("\n✅ Successfully found section 6.6.2.3!")
            print("✅ Bounded regex search working correctly!")
            print("\nNext: Phase 3 - Content extraction and subtitle detection")
        else:
            print("❌ PHASE 2 TESTS FAILED")
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
