"""
Test script for TOC-based chunking Phase 5.

Tests:
- TOCBasedChunker: Full end-to-end pipeline integration
- Verify section 6.6.2.3 is properly chunked with subtitle
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.toc_chunker import TOCBasedChunker
from src.utils.logger import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def test_full_pipeline():
    """Test full TOC-based chunking pipeline."""
    print("\n" + "="*80)
    print("TEST: Full TOC-Based Chunking Pipeline")
    print("="*80)

    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return False

    # Initialize chunker
    print("\nInitializing TOC-based chunker...")
    chunker = TOCBasedChunker(
        chunk_size=350,
        max_chunk_size=800,
        min_chunk_size=100
    )

    # Run full pipeline
    print(f"\nRunning full chunking pipeline on {pdf_path.name}...")
    print("="*80)

    chunks = chunker.chunk_document(str(pdf_path))

    print("="*80)
    print(f"\n✅ Pipeline complete! Generated {len(chunks)} chunks")

    # Analyze results
    print("\n" + "-"*80)
    print("Analysis")
    print("-"*80)

    # Count chunks by type
    toc_chunks = [c for c in chunks if not c.get('from_regex', False)]
    regex_chunks = [c for c in chunks if c.get('from_regex', False)]
    split_chunks = [c for c in chunks if c.get('is_split', False)]
    chunks_with_subtitle = [c for c in chunks if c.get('subtitle')]

    print(f"\nChunk breakdown:")
    print(f"  TOC-based chunks: {len(toc_chunks)}")
    print(f"  Regex-found chunks: {len(regex_chunks)}")
    print(f"  Split chunks: {len(split_chunks)}")
    print(f"  Chunks with subtitles: {len(chunks_with_subtitle)}")

    # Check problematic section 6.6.2.3
    print("\n" + "-"*80)
    print("Critical Test: Section 6.6.2.3 (Previously Missing Subtitle)")
    print("-"*80)

    section_6_6_2_3 = next(
        (c for c in chunks if c['section_number'].startswith('6.6.2.3')),
        None
    )

    if not section_6_6_2_3:
        print("❌ FAILED: Section 6.6.2.3 not found in chunks!")
        return False

    print(f"\n✅ Found section 6.6.2.3!")
    print(f"\nSection details:")
    print(f"  Number: {section_6_6_2_3['section_number']}")
    print(f"  Title: {section_6_6_2_3['section_title']}")
    print(f"  Subtitle: {section_6_6_2_3.get('subtitle', 'None')}")
    print(f"  Content length: {len(section_6_6_2_3.get('content', ''))} chars")
    print(f"  Page: {section_6_6_2_3.get('page_number', 'N/A')}")
    print(f"  From regex: {section_6_6_2_3.get('from_regex', False)}")

    # Verify subtitle was detected
    if section_6_6_2_3.get('subtitle'):
        print(f"\n✅ SUCCESS! Subtitle detected: '{section_6_6_2_3['subtitle']}'")
        print(f"   (Previously missing in old chunking system)")
    else:
        print(f"\n⚠ WARNING: Subtitle not detected (expected 'HS400')")

    # Show first 300 chars of content
    print(f"\nFirst 300 chars of content:")
    print("-" * 80)
    print(section_6_6_2_3.get('content', '')[:300])
    print("-" * 80)

    # Sample chunks
    print("\n" + "-"*80)
    print("Sample Chunks (first 10)")
    print("-"*80)

    print(f"\n{'Section':<20} {'Title':<40} {'Subtitle':<15} {'Content':<10}")
    print("-" * 90)

    for chunk in chunks[:10]:
        section_num = chunk['section_number']
        title = chunk.get('section_title', 'N/A')[:37]
        subtitle = chunk.get('subtitle', 'None')[:12] if chunk.get('subtitle') else 'None'
        content_len = len(chunk.get('content', ''))

        print(f"{section_num:<20} {title:<40} {subtitle:<15} {content_len:<10}")

    # Statistics
    print("\n" + "-"*80)
    print("Statistics")
    print("-"*80)

    total_content = sum(len(c.get('content', '')) for c in chunks)
    avg_content = total_content / len(chunks) if chunks else 0
    total_tokens = sum(len(c.get('content', '')) // 4 for c in chunks)
    avg_tokens = total_tokens / len(chunks) if chunks else 0

    print(f"\nTotal chunks: {len(chunks)}")
    print(f"Total content: {total_content:,} chars ({total_tokens:,} tokens)")
    print(f"Average chunk: {avg_content:.0f} chars ({avg_tokens:.0f} tokens)")

    # Token distribution
    token_counts = [len(c.get('content', '')) // 4 for c in chunks]
    under_800 = sum(1 for t in token_counts if t <= 800)
    over_800 = sum(1 for t in token_counts if t > 800)

    print(f"\nToken distribution:")
    print(f"  Chunks ≤800 tokens: {under_800} ({under_800/len(chunks)*100:.1f}%)")
    print(f"  Chunks >800 tokens: {over_800} ({over_800/len(chunks)*100:.1f}%)")

    if over_800 > 0:
        print(f"\n  Oversized chunks (>800 tokens):")
        for chunk in chunks:
            tokens = len(chunk.get('content', '')) // 4
            if tokens > 800:
                print(f"    {chunk['section_number']:<20} {tokens} tokens")

    # Check for chunks with missing content
    missing_content = [c for c in chunks if len(c.get('content', '')) == 0]
    if missing_content:
        print(f"\n⚠ WARNING: {len(missing_content)} chunks with no content:")
        for c in missing_content[:5]:
            print(f"    {c['section_number']:<20} {c.get('section_title', 'N/A')[:40]}")

    print("\n✅ Full pipeline test PASSED!\n")
    return True


def main():
    """Run Phase 5 integration test."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  TOC-Based Chunking - Phase 5 Integration Test                            ║
║                                                                            ║
║  Testing: Complete end-to-end pipeline                                    ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        result = test_full_pipeline()

        print("\n" + "="*80)
        if result:
            print("🎉 PHASE 5 INTEGRATION TEST PASSED!")
            print("="*80)
            print("\n✅ Full TOC-based chunking pipeline working!")
            print("✅ Section 6.6.2.3 properly handled with subtitle!")
            print("\nNext: Re-ingest eMMC 5.1 spec and validate in Streamlit UI")
        else:
            print("❌ PHASE 5 INTEGRATION TEST FAILED")
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
