"""
Test script for Table of Contents (TOC) extraction from eMMC 5.1 PDF.

This script tests if we can reliably extract:
1. Section numbers (e.g., 6.6.2)
2. Section titles (e.g., "HS400 Configuration")
3. Page numbers (start page for each section)

Goal: Determine if TOC-based approach can improve coverage from 71.9% to 95%+
"""

import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import pdfplumber


class TOCExtractor:
    """Extract and analyze Table of Contents from PDF."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.toc_entries: List[Dict] = []
        self.toc_pages: List[int] = []

    def find_toc_pages(self) -> List[int]:
        """
        Find which pages contain the Table of Contents.

        Based on validation, pages 11-21 are likely TOC (gaps without section numbers).
        """
        print("\n" + "="*80)
        print("FINDING TABLE OF CONTENTS PAGES")
        print("="*80)

        # Heuristic: Look for pages with "Contents" or dense lists of page numbers
        toc_pages = []

        with pdfplumber.open(self.pdf_path) as pdf:
            # Check pages 1-30 (front matter)
            for page_num in range(1, min(31, len(pdf.pages) + 1)):
                page = pdf.pages[page_num - 1]
                text = page.extract_text()

                if not text:
                    continue

                # Look for TOC indicators
                text_lower = text.lower()

                # Indicator 1: "contents" or "table of contents"
                has_contents_header = 'contents' in text_lower or 'table of contents' in text_lower

                # Indicator 2: Many page numbers (e.g., "........ 45")
                page_num_pattern = r'\.{3,}\s*\d+'
                page_num_matches = len(re.findall(page_num_pattern, text))

                # Indicator 3: Section number patterns at start of lines
                section_pattern = r'^\s*\d+\.\d+(?:\.\d+)?\s+[A-Z]'
                section_matches = len(re.findall(section_pattern, text, re.MULTILINE))

                if has_contents_header or page_num_matches > 10 or section_matches > 5:
                    toc_pages.append(page_num)
                    print(f"  Page {page_num}: TOC candidate")
                    print(f"    - Contents header: {has_contents_header}")
                    print(f"    - Page number refs: {page_num_matches}")
                    print(f"    - Section patterns: {section_matches}")

        self.toc_pages = toc_pages
        print(f"\nFound {len(toc_pages)} TOC pages: {toc_pages}")

        return toc_pages

    def extract_toc_entries(self) -> List[Dict]:
        """
        Extract TOC entries from identified TOC pages.

        Expected format (examples):
        - "6.6.2 HS400 Configuration ...................... 65"
        - "7.4.35 INI_TIMEOUT_AP [241] .................... 206"
        - "10.10.3 HS400 Device Command Output Timing ..... 180"
        """
        print("\n" + "="*80)
        print("EXTRACTING TOC ENTRIES")
        print("="*80)

        if not self.toc_pages:
            print("❌ No TOC pages found. Run find_toc_pages() first.")
            return []

        toc_entries = []

        # Pattern variations to try
        patterns = [
            # Pattern 1: "6.6.2 Title ........ 65"
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\.\n]{5,100}?)\s*\.{3,}\s*(\d+)\s*$',

            # Pattern 2: "6.6.2 Title  65" (minimal dots)
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\n]{5,100}?)\s+(\d+)\s*$',

            # Pattern 3: With brackets like "7.4.35 INI_TIMEOUT_AP [241] ... 206"
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\n]{5,100}?)\[[\d]+\]\s*\.{0,}\s*(\d+)\s*$',

            # Pattern 4: More flexible
            r'(\d+\.[\d\.]+)\s+([A-Z].*?)\s+\.{2,}\s*(\d+)',
        ]

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in self.toc_pages:
                page = pdf.pages[page_num - 1]
                text = page.extract_text()

                if not text:
                    continue

                print(f"\n--- Page {page_num} ---")

                # Try each pattern
                for pattern_idx, pattern in enumerate(patterns):
                    matches = re.finditer(pattern, text, re.MULTILINE)

                    for match in matches:
                        section_num = match.group(1)
                        section_title = match.group(2).strip()
                        page_number = int(match.group(3))

                        # Clean up title (remove excessive dots/spaces)
                        section_title = re.sub(r'\s*\.{2,}\s*', ' ', section_title).strip()
                        section_title = re.sub(r'\s{2,}', ' ', section_title)

                        entry = {
                            'section_number': section_num,
                            'section_title': section_title,
                            'page_number': page_number,
                            'toc_page': page_num,
                            'pattern_used': pattern_idx,
                            'level': len(section_num.split('.'))
                        }

                        toc_entries.append(entry)

                        # Show first few entries as examples
                        if len(toc_entries) <= 10:
                            print(f"  ✓ {section_num} - {section_title} (p. {page_number})")

        # Remove duplicates (same section number)
        seen = set()
        unique_entries = []
        for entry in toc_entries:
            if entry['section_number'] not in seen:
                seen.add(entry['section_number'])
                unique_entries.append(entry)

        self.toc_entries = unique_entries

        print(f"\n{'='*80}")
        print(f"Total TOC entries extracted: {len(unique_entries)}")
        print(f"{'='*80}")

        return unique_entries

    def analyze_toc_structure(self) -> Dict:
        """Analyze the structure of extracted TOC."""
        print("\n" + "="*80)
        print("TOC STRUCTURE ANALYSIS")
        print("="*80)

        if not self.toc_entries:
            print("❌ No TOC entries found. Run extract_toc_entries() first.")
            return {}

        # Count by level
        level_counts = defaultdict(int)
        for entry in self.toc_entries:
            level_counts[entry['level']] += 1

        print("\nEntries by Level:")
        print("-" * 60)
        for level in sorted(level_counts.keys()):
            count = level_counts[level]
            examples = [e['section_number'] for e in self.toc_entries if e['level'] == level][:3]
            print(f"  Level {level}: {count:4} entries  (e.g., {', '.join(examples)})")

        # Find page range coverage
        page_numbers = [e['page_number'] for e in self.toc_entries]
        if page_numbers:
            min_page = min(page_numbers)
            max_page = max(page_numbers)
            print(f"\nPage Range Covered: {min_page} - {max_page}")

        # Sample entries at different levels
        print("\n" + "="*80)
        print("SAMPLE TOC ENTRIES")
        print("="*80)

        for level in sorted(level_counts.keys()):
            examples = [e for e in self.toc_entries if e['level'] == level][:5]
            print(f"\nLevel {level} examples:")
            for ex in examples:
                print(f"  {ex['section_number']} - {ex['section_title'][:60]}... (p. {ex['page_number']})")

        return {
            'total_entries': len(self.toc_entries),
            'level_counts': dict(level_counts),
            'page_range': (min(page_numbers), max(page_numbers)) if page_numbers else (0, 0),
        }

    def estimate_coverage(self, total_pages: int = 352) -> Dict:
        """
        Estimate coverage improvement if we use TOC-based approach.

        Compare:
        - Current: 71.9% coverage (253/352 pages)
        - TOC-based: How many pages would TOC cover?
        """
        print("\n" + "="*80)
        print("COVERAGE ESTIMATION")
        print("="*80)

        if not self.toc_entries:
            print("❌ No TOC entries found.")
            return {}

        # Build section page ranges
        # Each section starts at its page and ends at the next section's page
        sorted_entries = sorted(self.toc_entries, key=lambda e: e['page_number'])

        covered_pages = set()

        for i, entry in enumerate(sorted_entries):
            start_page = entry['page_number']

            # Find end page (next section at same or higher level)
            end_page = total_pages  # Default to end of document

            # Find next section (at any level)
            if i + 1 < len(sorted_entries):
                end_page = sorted_entries[i + 1]['page_number'] - 1

            # Add all pages in this section's range
            for page in range(start_page, end_page + 1):
                if page <= total_pages:
                    covered_pages.add(page)

        coverage_count = len(covered_pages)
        coverage_pct = (coverage_count / total_pages * 100) if total_pages > 0 else 0

        print(f"\nCurrent Approach (Regex only):")
        print(f"  Coverage: 71.9% (253/352 pages)")

        print(f"\nTOC-Based Approach:")
        print(f"  TOC entries: {len(self.toc_entries)}")
        print(f"  Pages covered: {coverage_count}/{total_pages}")
        print(f"  Coverage: {coverage_pct:.1f}%")

        improvement = coverage_pct - 71.9
        print(f"\n{'✅' if improvement > 0 else '❌'} Improvement: {improvement:+.1f}%")

        # Identify gaps (pages not covered by TOC)
        all_pages = set(range(1, total_pages + 1))
        gap_pages = sorted(all_pages - covered_pages)

        if gap_pages:
            print(f"\nPages NOT covered by TOC: {len(gap_pages)}")

            # Group consecutive gaps
            gaps = []
            if gap_pages:
                start = gap_pages[0]
                end = gap_pages[0]

                for page in gap_pages[1:]:
                    if page == end + 1:
                        end = page
                    else:
                        gaps.append((start, end))
                        start = page
                        end = page

                gaps.append((start, end))

            print("\nGap Ranges:")
            for start, end in gaps[:10]:  # Show first 10 gaps
                if start == end:
                    print(f"  Page {start}")
                else:
                    print(f"  Pages {start}-{end} ({end - start + 1} pages)")

        return {
            'toc_entries': len(self.toc_entries),
            'pages_covered': coverage_count,
            'coverage_percentage': coverage_pct,
            'improvement': improvement,
            'gaps': gaps if gap_pages else [],
        }

    def validate_toc_quality(self) -> Dict:
        """
        Validate the quality of extracted TOC entries.

        Checks:
        1. Are page numbers in ascending order?
        2. Are there any suspicious entries (very short titles, etc.)?
        3. Do section numbers make sense (proper hierarchy)?
        """
        print("\n" + "="*80)
        print("TOC QUALITY VALIDATION")
        print("="*80)

        if not self.toc_entries:
            print("❌ No TOC entries found.")
            return {}

        issues = []

        # Check 1: Page number ordering
        print("\n1. Checking page number ordering...")
        prev_page = 0
        out_of_order = 0
        for entry in self.toc_entries:
            if entry['page_number'] < prev_page:
                out_of_order += 1
                if out_of_order <= 5:  # Show first 5 issues
                    issues.append(f"Out of order: {entry['section_number']} (p. {entry['page_number']} after p. {prev_page})")
            prev_page = entry['page_number']

        print(f"   {'✅' if out_of_order == 0 else '⚠️'} Out-of-order entries: {out_of_order}")

        # Check 2: Title quality
        print("\n2. Checking title quality...")
        short_titles = 0
        suspicious_titles = 0

        for entry in self.toc_entries:
            title = entry['section_title']

            # Too short (< 5 chars)
            if len(title) < 5:
                short_titles += 1
                if short_titles <= 5:
                    issues.append(f"Short title: {entry['section_number']} - '{title}'")

            # Suspicious patterns (all numbers, all dots, etc.)
            if re.match(r'^[\d\.\s]+$', title) or re.match(r'^[\.]+$', title):
                suspicious_titles += 1
                if suspicious_titles <= 5:
                    issues.append(f"Suspicious title: {entry['section_number']} - '{title}'")

        print(f"   {'✅' if short_titles == 0 else '⚠️'} Short titles (< 5 chars): {short_titles}")
        print(f"   {'✅' if suspicious_titles == 0 else '⚠️'} Suspicious titles: {suspicious_titles}")

        # Check 3: Section number hierarchy
        print("\n3. Checking section number hierarchy...")
        hierarchy_issues = 0

        # Build expected hierarchy
        expected_parents = {}
        for entry in self.toc_entries:
            parts = entry['section_number'].split('.')
            if len(parts) > 1:
                parent = '.'.join(parts[:-1])
                expected_parents[entry['section_number']] = parent

        # Check if all parents exist
        for section, parent in expected_parents.items():
            parent_exists = any(e['section_number'] == parent for e in self.toc_entries)
            if not parent_exists and len(parent.split('.')) > 1:  # Skip level-1 sections
                hierarchy_issues += 1
                if hierarchy_issues <= 5:
                    issues.append(f"Missing parent: {section} expects parent {parent}")

        print(f"   {'✅' if hierarchy_issues == 0 else '⚠️'} Hierarchy issues: {hierarchy_issues}")

        # Summary
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)

        total_issues = len(issues)
        quality_score = max(0, 100 - (total_issues * 2))  # Rough quality score

        print(f"\nTotal Issues Found: {total_issues}")
        print(f"Quality Score: {quality_score}/100")

        if issues:
            print("\nIssues (first 10):")
            for issue in issues[:10]:
                print(f"  ⚠️ {issue}")

        if quality_score >= 90:
            print("\n✅ TOC quality is EXCELLENT - safe to use for chunking")
        elif quality_score >= 70:
            print("\n⚠️ TOC quality is GOOD - usable with minor corrections")
        else:
            print("\n❌ TOC quality is POOR - needs significant cleanup")

        return {
            'total_issues': total_issues,
            'quality_score': quality_score,
            'out_of_order': out_of_order,
            'short_titles': short_titles,
            'suspicious_titles': suspicious_titles,
            'hierarchy_issues': hierarchy_issues,
        }

    def generate_report(self) -> str:
        """Generate comprehensive TOC extraction report."""
        report = []
        report.append("="*80)
        report.append("TOC EXTRACTION TEST REPORT")
        report.append("="*80)
        report.append(f"\nDocument: {Path(self.pdf_path).name}")
        report.append(f"Analysis Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if self.toc_entries:
            report.append(f"\n{'='*80}")
            report.append("RESULTS")
            report.append("="*80)
            report.append(f"\nTOC Pages Found: {self.toc_pages}")
            report.append(f"Total TOC Entries: {len(self.toc_entries)}")

            # Structure
            level_counts = defaultdict(int)
            for entry in self.toc_entries:
                level_counts[entry['level']] += 1

            report.append(f"\nSection Levels:")
            for level in sorted(level_counts.keys()):
                report.append(f"  Level {level}: {level_counts[level]} entries")

            # Coverage
            coverage_info = self.estimate_coverage()
            if coverage_info:
                report.append(f"\n{'='*80}")
                report.append("COVERAGE ANALYSIS")
                report.append("="*80)
                report.append(f"\nCurrent Approach: 71.9% (253/352 pages)")
                report.append(f"TOC-Based Approach: {coverage_info['coverage_percentage']:.1f}% ({coverage_info['pages_covered']}/352 pages)")
                report.append(f"Improvement: {coverage_info['improvement']:+.1f}%")

            # Quality
            quality_info = self.validate_toc_quality()
            if quality_info:
                report.append(f"\n{'='*80}")
                report.append("QUALITY ASSESSMENT")
                report.append("="*80)
                report.append(f"\nQuality Score: {quality_info['quality_score']}/100")
                report.append(f"Total Issues: {quality_info['total_issues']}")

            # Recommendation
            report.append(f"\n{'='*80}")
            report.append("RECOMMENDATION")
            report.append("="*80)

            if coverage_info and coverage_info['coverage_percentage'] >= 95:
                report.append("\n✅ PROCEED with TOC-based approach")
                report.append("   - Coverage is ≥95%")
                report.append("   - TOC extraction is reliable")
                report.append("   - Expected improvement: +{:.1f}%".format(coverage_info['improvement']))
            elif coverage_info and coverage_info['coverage_percentage'] >= 85:
                report.append("\n⚠️ CONSIDER TOC + Regex hybrid")
                report.append("   - Coverage is good but not excellent (85-95%)")
                report.append("   - Use TOC for major sections")
                report.append("   - Use regex for subsections and gaps")
            else:
                report.append("\n❌ TOC-only approach not recommended")
                report.append("   - Coverage is insufficient (<85%)")
                report.append("   - Consider improving regex approach instead")
        else:
            report.append("\n❌ Failed to extract TOC entries")
            report.append("   - Could not find TOC pages")
            report.append("   - Or TOC format is not parseable")

        report.append(f"\n{'='*80}")
        report.append("END OF REPORT")
        report.append("="*80)

        return '\n'.join(report)


def main():
    """Run TOC extraction test."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  Table of Contents (TOC) Extraction Test                                  ║
║                                                                            ║
║  Testing if we can extract TOC to improve chunking coverage               ║
║  from 71.9% to 95%+                                                       ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    # Path to PDF
    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    if not pdf_path.exists():
        print(f"❌ PDF not found at: {pdf_path}")
        return

    # Initialize extractor
    extractor = TOCExtractor(str(pdf_path))

    # Step 1: Find TOC pages
    toc_pages = extractor.find_toc_pages()

    if not toc_pages:
        print("\n❌ Could not find TOC pages. Aborting.")
        return

    # Step 2: Extract TOC entries
    entries = extractor.extract_toc_entries()

    if not entries:
        print("\n❌ Could not extract TOC entries. Aborting.")
        return

    # Step 3: Analyze structure
    structure = extractor.analyze_toc_structure()

    # Step 4: Estimate coverage
    coverage = extractor.estimate_coverage()

    # Step 5: Validate quality
    quality = extractor.validate_toc_quality()

    # Step 6: Generate report
    report = extractor.generate_report()
    print("\n" + report)

    # Save report
    report_path = Path(__file__).parent.parent / 'TOC_EXTRACTION_TEST_REPORT.md'
    report_path.write_text(report)
    print(f"\n📄 Report saved to: {report_path}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
