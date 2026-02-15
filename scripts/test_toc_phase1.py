"""
Test script for TOC-based chunking Phase 1.

Tests:
- TOCExtractor: Can we extract 351 TOC entries?
- TOCPreprocessor: Can we sort, infer parents, calculate ranges?
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.toc_chunker import TOCExtractor, TOCPreprocessor
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def test_toc_extractor():
    """Test TOC extraction."""
    print("\n" + "="*80)
    print("TEST: TOCExtractor")
    print("="*80)

    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    if not pdf_path.exists():
        print(f"❌ PDF not found at: {pdf_path}")
        return False

    # Extract TOC
    extractor = TOCExtractor(str(pdf_path))
    entries = extractor.extract()

    # Assertions
    print(f"\n✓ Extracted {len(entries)} TOC entries")

    assert len(entries) > 0, "Should extract some entries"
    assert len(entries) >= 340, f"Should extract ~351 entries, got {len(entries)}"

    # Check structure
    first_entry = entries[0]
    required_keys = ['section_number', 'section_title', 'page_number', 'level']

    for key in required_keys:
        assert key in first_entry, f"Entry should have '{key}' field"

    print(f"✓ All entries have required fields: {required_keys}")

    # Show samples
    print("\nSample TOC entries:")
    for entry in entries[:10]:
        print(f"  {entry['section_number']:10} - {entry['section_title'][:50]:50} (p. {entry['page_number']})")

    # Check specific sections
    section_numbers = [e['section_number'] for e in entries]

    # Should have 7.4.35 (the problematic chunk)
    assert '7.4.35' in section_numbers, "Should find section 7.4.35"
    entry_7_4_35 = next(e for e in entries if e['section_number'] == '7.4.35')
    print(f"\n✓ Found section 7.4.35: '{entry_7_4_35['section_title']}'")
    assert 'INI_TIMEOUT_AP' in entry_7_4_35['section_title'], "Should have correct title"

    print("\n✅ TOCExtractor test PASSED\n")
    return True


def test_toc_preprocessor():
    """Test TOC preprocessing."""
    print("\n" + "="*80)
    print("TEST: TOCPreprocessor")
    print("="*80)

    # First extract TOC
    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'
    extractor = TOCExtractor(str(pdf_path))
    raw_entries = extractor.extract()

    print(f"\nRaw entries: {len(raw_entries)}")

    # Preprocess
    preprocessor = TOCPreprocessor()
    processed = preprocessor.process(raw_entries)

    print(f"Processed entries: {len(processed)}")

    # Assertions
    assert len(processed) > len(raw_entries), "Should have inferred parents"

    inferred_count = len(processed) - len(raw_entries)
    print(f"✓ Inferred {inferred_count} missing parent sections")

    # Check fields added
    first_entry = processed[0]
    required_fields = ['page_start', 'page_end', 'page_count', 'is_long']

    for field in required_fields:
        assert field in first_entry, f"Should have '{field}' field after preprocessing"

    print(f"✓ All entries have required fields: {required_fields}")

    # Check sorting
    section_numbers = [e['section_number'] for e in processed]
    print(f"\nFirst 10 section numbers (should be sorted):")
    for num in section_numbers[:10]:
        print(f"  {num}")

    # Check page ranges
    print(f"\nSample page ranges:")
    for entry in processed[:10]:
        print(f"  {entry['section_number']:10} pages {entry['page_start']:3}-{entry['page_end']:3} ({entry['page_count']:2} pages)")

    # Check long sections
    long_sections = [e for e in processed if e.get('is_long', False)]
    print(f"\n✓ Found {len(long_sections)} long sections (>10 pages):")
    for entry in long_sections[:10]:
        print(f"  {entry['section_number']:10} - {entry['section_title'][:40]:40} ({entry['page_count']} pages)")

    # Check inferred sections
    inferred_sections = [e for e in processed if e.get('inferred', False)]
    print(f"\n✓ Inferred sections ({len(inferred_sections)} total):")
    for entry in inferred_sections[:10]:
        print(f"  {entry['section_number']:10} (inferred, page {entry['page_number']})")

    print("\n✅ TOCPreprocessor test PASSED\n")
    return True


def main():
    """Run all Phase 1 tests."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  TOC-Based Chunking - Phase 1 Tests                                       ║
║                                                                            ║
║  Testing: TOCExtractor + TOCPreprocessor                                  ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    results = []

    # Test 1: TOCExtractor
    try:
        result = test_toc_extractor()
        results.append(("TOCExtractor", result))
    except Exception as e:
        print(f"❌ TOCExtractor test FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("TOCExtractor", False))

    # Test 2: TOCPreprocessor
    try:
        result = test_toc_preprocessor()
        results.append(("TOCPreprocessor", result))
    except Exception as e:
        print(f"❌ TOCPreprocessor test FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("TOCPreprocessor", False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name:30} {status}")

    all_passed = all(r[1] for r in results)

    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Phase 1 Complete!")
    else:
        print("❌ SOME TESTS FAILED - Please review errors above")
    print("="*80)

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
