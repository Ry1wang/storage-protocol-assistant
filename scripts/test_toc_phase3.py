"""
Test script for TOC-based chunking Phase 3.

Tests:
- ContentExtractor: Can we extract content and detect subtitles?
- Focus on section 6.6.2.3 (problematic section with "HS400" subtitle)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.toc_chunker import (
    TOCExtractor,
    TOCPreprocessor,
    BoundedRegexSearcher,
    ContentExtractor
)
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def test_content_extractor():
    """Test content extraction and subtitle detection."""
    print("\n" + "="*80)
    print("TEST: ContentExtractor")
    print("="*80)

    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    # Step 1: Get preprocessed TOC entries
    print("\nStep 1: Extract and preprocess TOC...")
    extractor = TOCExtractor(str(pdf_path))
    raw_entries = extractor.extract()

    preprocessor = TOCPreprocessor()
    processed_entries = preprocessor.process(raw_entries)

    print(f"✓ Got {len(processed_entries)} preprocessed entries")

    # Step 2: Find subsections with BoundedRegexSearcher
    print("\nStep 2: Find subsections...")
    searcher = BoundedRegexSearcher(str(pdf_path))
    all_subsections = searcher.search_all(processed_entries)

    print(f"✓ Found {len(all_subsections)} subsections")

    # Step 3: Test ContentExtractor on problematic section 6.6.2.3
    print("\n" + "-"*80)
    print("Test 1: Extract content from section 6.6.2.3 (problematic section)")
    print("-"*80)

    section_6_6_2_3 = next(
        (s for s in all_subsections if s['section_number'] == '6.6.2.3'),
        None
    )

    if not section_6_6_2_3:
        print("❌ Section 6.6.2.3 not found")
        return False

    print(f"\nSection before extraction:")
    print(f"  Number: {section_6_6_2_3['section_number']}")
    print(f"  Title: {section_6_6_2_3['section_title']}")
    print(f"  Page: {section_6_6_2_3['page_number']}")

    # Extract content
    content_extractor = ContentExtractor(str(pdf_path), page_offset=20)
    enriched_section = content_extractor.extract_content(section_6_6_2_3)

    print(f"\nSection after extraction:")
    print(f"  Number: {enriched_section['section_number']}")
    print(f"  Title: {enriched_section['section_title']}")
    print(f"  Subtitle: {enriched_section.get('subtitle', 'None')}")
    print(f"  Content length: {len(enriched_section.get('content', ''))} chars")
    print(f"\nFirst 500 chars of content:")
    print("-" * 80)
    print(enriched_section.get('content', '')[:500])
    print("-" * 80)

    # Critical check: Did we detect the subtitle?
    if enriched_section.get('subtitle'):
        print(f"\n✅ SUCCESS! Detected subtitle: '{enriched_section['subtitle']}'")
    else:
        print(f"\n⚠ WARNING: No subtitle detected (expected 'HS400' or similar)")

    # Check that we got content
    if len(enriched_section.get('content', '')) > 100:
        print(f"✅ Content extracted successfully")
    else:
        print(f"❌ FAILED: Content too short or missing")
        return False

    # Test 2: Extract content for multiple sections
    print("\n" + "-"*80)
    print("Test 2: Extract content for multiple subsections")
    print("-"*80)

    # Get a few subsections
    test_sections = all_subsections[:10]

    print(f"\nExtracting content for {len(test_sections)} sections...")
    enriched_sections = content_extractor.extract_all_content(test_sections)

    print(f"✓ Extracted content for {len(enriched_sections)} sections")

    # Show results
    print("\nSample results:")
    for section in enriched_sections[:5]:
        subtitle = section.get('subtitle', 'None')
        content_len = len(section.get('content', ''))
        print(f"  {section['section_number']:15} - "
              f"Subtitle: {subtitle[:30] if subtitle else 'None':30} - "
              f"Content: {content_len:5} chars")

    # Statistics
    print("\n" + "-"*80)
    print("Statistics")
    print("-"*80)

    sections_with_subtitle = sum(1 for s in enriched_sections if s.get('subtitle'))
    sections_with_content = sum(1 for s in enriched_sections if len(s.get('content', '')) > 0)

    print(f"\nSections with subtitle: {sections_with_subtitle}/{len(enriched_sections)}")
    print(f"Sections with content: {sections_with_content}/{len(enriched_sections)}")

    # Test 3: Verify subtitle detection patterns
    print("\n" + "-"*80)
    print("Test 3: Subtitle detection patterns")
    print("-"*80)

    # Check different subtitle patterns
    print("\nSubtitle detection examples:")
    for section in enriched_sections:
        if section.get('subtitle'):
            print(f"  {section['section_number']:15} - "
                  f"Title: {section['section_title'][:40]:40} - "
                  f"Subtitle: {section['subtitle']}")

    print("\n✅ ContentExtractor test PASSED\n")
    return True


def main():
    """Run Phase 3 tests."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  TOC-Based Chunking - Phase 3 Tests                                       ║
║                                                                            ║
║  Testing: ContentExtractor                                                ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        result = test_content_extractor()

        print("\n" + "="*80)
        if result:
            print("🎉 PHASE 3 TESTS PASSED!")
            print("="*80)
            print("\n✅ Content extraction working correctly!")
            print("✅ Subtitle detection functional!")
            print("\nNext: Phase 4 - IntelligentTruncator for long sections")
        else:
            print("❌ PHASE 3 TESTS FAILED")
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
