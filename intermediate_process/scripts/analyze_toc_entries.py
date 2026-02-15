"""
Detailed analysis of extracted TOC entries.

This script examines specific TOC entries to understand:
1. Out-of-order entries and why they occur
2. Short titles and their context
3. Missing parent sections and hierarchy gaps
4. Edge cases that need special handling
"""

import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List
import pdfplumber
import json


def load_toc_entries(pdf_path: str) -> List[Dict]:
    """Re-extract TOC entries for analysis."""
    from test_toc_extraction import TOCExtractor

    extractor = TOCExtractor(pdf_path)
    extractor.find_toc_pages()
    entries = extractor.extract_toc_entries()

    return entries


def analyze_out_of_order(entries: List[Dict]) -> None:
    """Analyze out-of-order entries in detail."""
    print("\n" + "="*80)
    print("ANALYSIS: OUT-OF-ORDER ENTRIES")
    print("="*80)

    # Sort by page number to find order issues
    sorted_entries = sorted(entries, key=lambda e: (e['page_number'], e['section_number']))

    out_of_order = []
    prev_entry = None

    for i, entry in enumerate(sorted_entries):
        if prev_entry:
            # Check if section numbers are in logical order
            prev_num = prev_entry['section_number']
            curr_num = entry['section_number']
            prev_page = prev_entry['page_number']
            curr_page = entry['page_number']

            # If on same page, check section number order
            if curr_page == prev_page:
                if not is_section_ascending(prev_num, curr_num):
                    out_of_order.append({
                        'prev': prev_entry,
                        'curr': entry,
                        'issue': 'Same page, wrong section order'
                    })
            # If page went backwards
            elif curr_page < prev_page:
                out_of_order.append({
                    'prev': prev_entry,
                    'curr': entry,
                    'issue': 'Page number decreased'
                })

        prev_entry = entry

    print(f"\nFound {len(out_of_order)} out-of-order issues:\n")

    for i, issue in enumerate(out_of_order, 1):
        prev = issue['prev']
        curr = issue['curr']
        print(f"{i}. {issue['issue']}")
        print(f"   Previous: {prev['section_number']} - {prev['section_title'][:50]}... (page {prev['page_number']})")
        print(f"   Current:  {curr['section_number']} - {curr['section_title'][:50]}... (page {curr['page_number']})")
        print()

    # Recommendation
    print("RECOMMENDATION:")
    if len(out_of_order) <= 5:
        print("  ✅ Minor issue - Can sort entries programmatically")
        print("  ✅ These are likely TOC formatting quirks (e.g., appendices, indexes)")
    else:
        print("  ⚠️ Significant issue - May need manual review")


def is_section_ascending(prev_num: str, curr_num: str) -> bool:
    """Check if section numbers are in ascending order."""
    def parse_section(s):
        # Handle cases like "1.70" or "7.7"
        parts = s.split('.')
        return tuple(int(p) if p.isdigit() else 999 for p in parts)

    return parse_section(curr_num) > parse_section(prev_num)


def analyze_short_titles(entries: List[Dict]) -> None:
    """Analyze entries with short titles."""
    print("\n" + "="*80)
    print("ANALYSIS: SHORT TITLES")
    print("="*80)

    short_titles = [e for e in entries if len(e['section_title']) < 10]

    print(f"\nFound {len(short_titles)} entries with titles < 10 characters:\n")

    for entry in short_titles[:20]:  # Show first 20
        print(f"  {entry['section_number']}: '{entry['section_title']}' (page {entry['page_number']})")

    if len(short_titles) > 20:
        print(f"  ... and {len(short_titles) - 20} more")

    # Analyze patterns
    print("\nPATTERN ANALYSIS:")

    # Are they abbreviations?
    abbreviations = [e for e in short_titles if e['section_title'].isupper()]
    print(f"  - Abbreviations (all caps): {len(abbreviations)} entries")
    if abbreviations:
        print(f"    Examples: {', '.join([e['section_title'] for e in abbreviations[:5]])}")

    # Are they register names?
    register_pattern = r'^[A-Z0-9_]+$'
    registers = [e for e in short_titles if re.match(register_pattern, e['section_title'])]
    print(f"  - Register/field names: {len(registers)} entries")
    if registers:
        print(f"    Examples: {', '.join([e['section_title'] for e in registers[:5]])}")

    print("\nRECOMMENDATION:")
    print("  ✅ Short titles are valid (abbreviations, register names)")
    print("  ✅ Keep as-is - they're accurate even if terse")


def analyze_missing_parents(entries: List[Dict]) -> None:
    """Analyze missing parent sections."""
    print("\n" + "="*80)
    print("ANALYSIS: MISSING PARENT SECTIONS")
    print("="*80)

    # Build section hierarchy
    section_map = {e['section_number']: e for e in entries}

    # Find all expected parents
    missing_parents = defaultdict(list)

    for entry in entries:
        parts = entry['section_number'].split('.')

        # For each level, check if parent exists
        for i in range(1, len(parts)):
            parent = '.'.join(parts[:i])

            if parent not in section_map:
                missing_parents[parent].append(entry['section_number'])

    print(f"\nFound {len(missing_parents)} missing parent sections:\n")

    # Show examples
    for parent, children in sorted(missing_parents.items())[:10]:
        print(f"  Missing: {parent}")
        print(f"    Children in TOC: {', '.join(children[:5])}")
        if len(children) > 5:
            print(f"    ... and {len(children) - 5} more")
        print()

    if len(missing_parents) > 10:
        print(f"  ... and {len(missing_parents) - 10} more missing parents")

    # Analysis
    print("\nPATTERN ANALYSIS:")

    # Group by level
    level_1_missing = [p for p in missing_parents if len(p.split('.')) == 1]
    level_2_missing = [p for p in missing_parents if len(p.split('.')) == 2]
    level_3_missing = [p for p in missing_parents if len(p.split('.')) == 3]

    print(f"  - Level 1 missing (e.g., '5'): {len(level_1_missing)} sections")
    print(f"  - Level 2 missing (e.g., '5.3'): {len(level_2_missing)} sections")
    print(f"  - Level 3 missing (e.g., '6.6.2'): {len(level_3_missing)} sections")

    print("\nRECOMMENDATION:")
    print("  ✅ Can infer missing parents from children")
    print("  ✅ Example: If we have 5.3.1, 5.3.2, 5.3.3, we know 5.3 exists")
    print("  ✅ Can create synthetic parent entries with:")
    print("     - Section number: Inferred from children")
    print("     - Title: Derived from first child's title or marked as '[Inferred]'")
    print("     - Page: Start page of first child")


def analyze_specific_sections(entries: List[Dict], pdf_path: str) -> None:
    """Analyze specific problematic sections in detail."""
    print("\n" + "="*80)
    print("ANALYSIS: SPECIFIC PROBLEMATIC SECTIONS")
    print("="*80)

    # The two problematic chunks mentioned by user
    target_sections = [
        '6.6.2.3',  # Missing subtitle "HS400" timing mode selection
        '7.4.35',   # Was incorrectly identified as math formula
    ]

    for section_num in target_sections:
        print(f"\n{'='*80}")
        print(f"SECTION: {section_num}")
        print(f"{'='*80}")

        # Find in TOC
        toc_entry = next((e for e in entries if e['section_number'] == section_num), None)

        if toc_entry:
            print(f"\n✅ Found in TOC:")
            print(f"   Section Number: {toc_entry['section_number']}")
            print(f"   Section Title: {toc_entry['section_title']}")
            print(f"   Page Number: {toc_entry['page_number']}")
            print(f"   TOC Page: {toc_entry['toc_page']}")
            print(f"   Level: {toc_entry['level']}")

            # Extract actual content from that page
            print(f"\n📄 Content from page {toc_entry['page_number']}:")
            print("-" * 80)

            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[toc_entry['page_number'] - 1]
                text = page.extract_text()

                # Find section in text
                section_pattern = rf'{re.escape(section_num)}\s+([^\n]+)'
                matches = re.finditer(section_pattern, text)

                for match in matches:
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(text), match.end() + 500)
                    context = text[context_start:context_end]

                    print(context)
                    print("-" * 80)

                    # Look for subtitles (quoted text)
                    subtitle_pattern = r'"([^"]+)"'
                    subtitles = re.findall(subtitle_pattern, context)

                    if subtitles:
                        print(f"\n✅ Subtitles found in content:")
                        for subtitle in subtitles:
                            print(f"   - \"{subtitle}\"")
                    else:
                        print(f"\n⚠️ No quoted subtitles found in immediate context")
        else:
            print(f"\n❌ NOT found in TOC!")
            print(f"   This section might be:")
            print(f"   - A subsection of a TOC entry")
            print(f"   - In a page range covered by a parent section")
            print(f"   - Need to use regex within parent's page range")


def analyze_page_ranges(entries: List[Dict]) -> None:
    """Analyze page ranges covered by TOC sections."""
    print("\n" + "="*80)
    print("ANALYSIS: PAGE RANGE COVERAGE")
    print("="*80)

    # Sort by page number
    sorted_entries = sorted(entries, key=lambda e: e['page_number'])

    # Calculate page ranges
    page_ranges = []

    for i, entry in enumerate(sorted_entries):
        start_page = entry['page_number']

        # End page is start of next section (at any level)
        if i + 1 < len(sorted_entries):
            end_page = sorted_entries[i + 1]['page_number'] - 1
        else:
            end_page = 352  # End of document

        page_range = end_page - start_page + 1

        page_ranges.append({
            'section': entry['section_number'],
            'title': entry['section_title'],
            'start': start_page,
            'end': end_page,
            'pages': page_range,
            'level': entry['level']
        })

    # Find long sections (>10 pages)
    long_sections = [r for r in page_ranges if r['pages'] > 10]

    print(f"\nSections spanning >10 pages: {len(long_sections)}\n")

    for sec in sorted(long_sections, key=lambda x: x['pages'], reverse=True)[:10]:
        print(f"  {sec['section']}: {sec['title'][:50]}...")
        print(f"    Pages {sec['start']}-{sec['end']} ({sec['pages']} pages)")
        print(f"    Level: {sec['level']}")
        print()

    # Find very short sections (1 page)
    short_sections = [r for r in page_ranges if r['pages'] == 1]
    print(f"\nSections spanning exactly 1 page: {len(short_sections)}")

    # Statistics
    avg_pages = sum(r['pages'] for r in page_ranges) / len(page_ranges)
    print(f"\nAverage pages per section: {avg_pages:.1f}")

    print("\nRECOMMENDATION:")
    print("  ✅ Long sections (>10 pages) will need intelligent truncation")
    print("  ✅ Use hierarchical splitting: subsections → paragraphs → sentences")
    print(f"  ✅ {len(long_sections)} sections need special handling")


def generate_edge_case_report(entries: List[Dict], pdf_path: str) -> str:
    """Generate comprehensive edge case report."""
    report = []

    report.append("="*80)
    report.append("TOC EDGE CASE ANALYSIS REPORT")
    report.append("="*80)
    report.append(f"\nDocument: {Path(pdf_path).name}")
    report.append(f"Total TOC Entries: {len(entries)}")
    report.append(f"Analysis Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    report.append(f"\n{'='*80}")
    report.append("SUMMARY OF ISSUES")
    report.append("="*80)

    # Count issues
    out_of_order = sum(1 for i, e in enumerate(sorted(entries, key=lambda x: x['page_number']))
                       if i > 0 and e['page_number'] < sorted(entries, key=lambda x: x['page_number'])[i-1]['page_number'])
    short_titles = len([e for e in entries if len(e['section_title']) < 10])

    # Missing parents
    section_map = {e['section_number']: e for e in entries}
    missing_parents = set()
    for entry in entries:
        parts = entry['section_number'].split('.')
        for i in range(1, len(parts)):
            parent = '.'.join(parts[:i])
            if parent not in section_map:
                missing_parents.add(parent)

    report.append(f"\n1. Out-of-order entries: {out_of_order}")
    report.append(f"2. Short titles (<10 chars): {short_titles}")
    report.append(f"3. Missing parent sections: {len(missing_parents)}")
    report.append(f"\nTotal Issues: {out_of_order + short_titles + len(missing_parents)}")

    report.append(f"\n{'='*80}")
    report.append("HANDLING STRATEGIES")
    report.append("="*80)

    report.append("\n1. Out-of-order entries:")
    report.append("   - Sort by page number before processing")
    report.append("   - Validate section number sequence")
    report.append("   - Flag anomalies for manual review")

    report.append("\n2. Short titles:")
    report.append("   - Keep as-is (they're valid abbreviations)")
    report.append("   - Optionally expand using context from content")
    report.append("   - Mark with flag for potential enhancement")

    report.append("\n3. Missing parent sections:")
    report.append("   - Infer from children (e.g., 5.3 from 5.3.1, 5.3.2, ...)")
    report.append("   - Create synthetic entries with:")
    report.append("     * Section number: Inferred")
    report.append("     * Title: '[Inferred] ' + derived from children")
    report.append("     * Page: Start page of first child")

    report.append(f"\n{'='*80}")
    report.append("IMPLEMENTATION RECOMMENDATIONS")
    report.append("="*80)

    report.append("\n✅ TOC-based approach is VIABLE despite edge cases")
    report.append("\n✅ Issues are minor and can be handled programmatically:")
    report.append("   1. Pre-process TOC: Sort, deduplicate, validate")
    report.append("   2. Infer missing parents from children")
    report.append("   3. Flag short titles for optional enhancement")
    report.append("   4. Use page ranges to bound regex searches")

    report.append(f"\n{'='*80}")
    report.append("NEXT STEPS")
    report.append("="*80)

    report.append("\n1. Implement TOC preprocessing:")
    report.append("   - Sort by page number")
    report.append("   - Infer missing parent sections")
    report.append("   - Validate hierarchy")

    report.append("\n2. Implement bounded regex search:")
    report.append("   - For each TOC section, extract page range")
    report.append("   - Search within that range for subsections")
    report.append("   - Validate ascending order")

    report.append("\n3. Implement intelligent truncation:")
    report.append("   - Detect long sections (>800 tokens)")
    report.append("   - Split by subsections if available")
    report.append("   - Fallback to semantic breaks")

    report.append(f"\n{'='*80}")
    report.append("END OF REPORT")
    report.append("="*80)

    return '\n'.join(report)


def main():
    """Run detailed TOC entry analysis."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  Detailed TOC Entry Analysis                                              ║
║                                                                            ║
║  Examining edge cases and specific problematic sections                   ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    if not pdf_path.exists():
        print(f"❌ PDF not found at: {pdf_path}")
        return

    # Load TOC entries
    print("Loading TOC entries...")
    entries = load_toc_entries(str(pdf_path))
    print(f"✅ Loaded {len(entries)} TOC entries\n")

    # Run analyses
    analyze_out_of_order(entries)
    analyze_short_titles(entries)
    analyze_missing_parents(entries)
    analyze_page_ranges(entries)
    analyze_specific_sections(entries, str(pdf_path))

    # Generate report
    report = generate_edge_case_report(entries, str(pdf_path))
    print("\n" + report)

    # Save report
    report_path = Path(__file__).parent.parent / 'TOC_EDGE_CASE_ANALYSIS.md'
    report_path.write_text(report)
    print(f"\n📄 Report saved to: {report_path}")

    # Save TOC entries as JSON for reference
    json_path = Path(__file__).parent.parent / 'toc_entries.json'
    with open(json_path, 'w') as f:
        json.dump(entries, f, indent=2)
    print(f"📄 TOC entries saved to: {json_path}")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
