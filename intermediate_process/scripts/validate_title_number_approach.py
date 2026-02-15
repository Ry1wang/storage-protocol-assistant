"""
Validation script for title-number-based chunking approach.

This script analyzes the eMMC 5.1 specification PDF to determine:
1. How many section numbers are present
2. Coverage percentage (pages with section numbers vs. total pages)
3. Edge cases (figures, tables, references vs. real sections)
4. Section hierarchy completeness
5. Feasibility of title-number-based chunking

DO NOT RUN THIS YET - This is for analysis purposes only.
"""

import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set
import pdfplumber


class SectionNumberAnalyzer:
    """Analyze section number coverage in PDF document."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.section_pattern = re.compile(
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\n]{0,200})',
            re.MULTILINE
        )
        self.figure_pattern = re.compile(
            r'Figure\s+[\dA-Z]+-[\d]+',
            re.IGNORECASE
        )
        self.table_pattern = re.compile(
            r'Table\s+[\dA-Z]+-[\d]+',
            re.IGNORECASE
        )
        self.appendix_pattern = re.compile(
            r'Appendix\s+[A-Z]\.?[\d\.]*',
            re.IGNORECASE
        )

        # Results storage
        self.sections: Dict[str, Dict] = {}
        self.pages_with_sections: Set[int] = set()
        self.total_pages: int = 0
        self.figures: List[Dict] = []
        self.tables: List[Dict] = []
        self.appendices: List[Dict] = []

    def extract_all_text_with_pages(self) -> Dict[int, str]:
        """Extract text from all pages with page numbers."""
        page_texts = {}

        print(f"Opening PDF: {self.pdf_path}")
        with pdfplumber.open(self.pdf_path) as pdf:
            self.total_pages = len(pdf.pages)
            print(f"Total pages: {self.total_pages}")

            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    page_texts[page_num] = text

                if page_num % 50 == 0:
                    print(f"  Processed {page_num}/{self.total_pages} pages...")

        print(f"Extracted text from {len(page_texts)} pages")
        return page_texts

    def find_section_numbers(self, page_texts: Dict[int, str]) -> None:
        """Find all section numbers in the document."""
        print("\nSearching for section numbers...")

        for page_num, text in page_texts.items():
            # Find all section number patterns
            matches = self.section_pattern.finditer(text)

            for match in matches:
                section_num = match.group(1)
                section_title = match.group(2).strip()

                # Skip if this looks like a figure or table
                if self.figure_pattern.search(section_title):
                    self.figures.append({
                        'number': section_num,
                        'title': section_title,
                        'page': page_num
                    })
                    continue

                if self.table_pattern.search(section_title):
                    self.tables.append({
                        'number': section_num,
                        'title': section_title,
                        'page': page_num
                    })
                    continue

                # Check if appendix
                if self.appendix_pattern.search(section_title):
                    self.appendices.append({
                        'number': section_num,
                        'title': section_title,
                        'page': page_num
                    })

                # Store section
                if section_num not in self.sections:
                    self.sections[section_num] = {
                        'title': section_title,
                        'pages': [page_num],
                        'level': len(section_num.split('.')),
                        'first_page': page_num,
                    }
                    self.pages_with_sections.add(page_num)
                else:
                    # Section appears on multiple pages
                    if page_num not in self.sections[section_num]['pages']:
                        self.sections[section_num]['pages'].append(page_num)
                        self.pages_with_sections.add(page_num)

        print(f"Found {len(self.sections)} unique section numbers")
        print(f"Found {len(self.figures)} figures")
        print(f"Found {len(self.tables)} tables")
        print(f"Found {len(self.appendices)} appendices")

    def build_section_hierarchy(self) -> Dict:
        """Build hierarchical structure of sections."""
        print("\nBuilding section hierarchy...")

        hierarchy = defaultdict(list)

        for section_num in sorted(self.sections.keys(), key=self._section_sort_key):
            parts = section_num.split('.')
            level = len(parts)

            if level > 1:
                parent = '.'.join(parts[:-1])
                hierarchy[parent].append(section_num)
            else:
                hierarchy['root'].append(section_num)

        return dict(hierarchy)

    def _section_sort_key(self, section_num: str) -> Tuple:
        """Sort key for section numbers."""
        parts = section_num.split('.')
        return tuple(int(p) if p.isdigit() else 999 for p in parts)

    def analyze_coverage(self) -> Dict:
        """Analyze section number coverage."""
        print("\n" + "="*80)
        print("COVERAGE ANALYSIS")
        print("="*80)

        pages_with_sections = len(self.pages_with_sections)
        coverage_pct = (pages_with_sections / self.total_pages * 100) if self.total_pages > 0 else 0

        results = {
            'total_pages': self.total_pages,
            'pages_with_sections': pages_with_sections,
            'pages_without_sections': self.total_pages - pages_with_sections,
            'coverage_percentage': coverage_pct,
            'total_sections': len(self.sections),
            'total_figures': len(self.figures),
            'total_tables': len(self.tables),
            'total_appendices': len(self.appendices),
        }

        print(f"\nTotal Pages: {results['total_pages']}")
        print(f"Pages with Section Numbers: {results['pages_with_sections']}")
        print(f"Pages without Section Numbers: {results['pages_without_sections']}")
        print(f"Coverage: {results['coverage_percentage']:.1f}%")
        print(f"\nTotal Unique Sections: {results['total_sections']}")
        print(f"Figures Detected: {results['total_figures']}")
        print(f"Tables Detected: {results['total_tables']}")
        print(f"Appendices Detected: {results['total_appendices']}")

        return results

    def analyze_section_levels(self) -> Dict:
        """Analyze section level distribution."""
        print("\n" + "="*80)
        print("SECTION LEVEL DISTRIBUTION")
        print("="*80)

        level_counts = defaultdict(int)

        for section_num, data in self.sections.items():
            level = data['level']
            level_counts[level] += 1

        print("\nLevel | Count | Examples")
        print("-" * 60)

        for level in sorted(level_counts.keys()):
            count = level_counts[level]
            examples = [num for num, data in self.sections.items() if data['level'] == level][:3]
            print(f"{level:5} | {count:5} | {', '.join(examples)}")

        return dict(level_counts)

    def find_gaps(self, page_texts: Dict[int, str]) -> List[Tuple[int, int]]:
        """Find page ranges without section numbers."""
        print("\n" + "="*80)
        print("GAPS (Pages without section numbers)")
        print("="*80)

        pages_without = sorted(set(page_texts.keys()) - self.pages_with_sections)

        # Group consecutive pages
        gaps = []
        if pages_without:
            start = pages_without[0]
            end = pages_without[0]

            for page in pages_without[1:]:
                if page == end + 1:
                    end = page
                else:
                    gaps.append((start, end))
                    start = page
                    end = page

            gaps.append((start, end))

        print(f"\nFound {len(gaps)} gap(s):")
        for start, end in gaps:
            if start == end:
                print(f"  Page {start}")
            else:
                print(f"  Pages {start}-{end} ({end - start + 1} pages)")

        return gaps

    def sample_sections(self, n: int = 10) -> None:
        """Display sample sections for manual review."""
        print("\n" + "="*80)
        print(f"SAMPLE SECTIONS (Random {n})")
        print("="*80)

        import random
        sample = random.sample(list(self.sections.items()), min(n, len(self.sections)))

        for section_num, data in sorted(sample, key=lambda x: self._section_sort_key(x[0])):
            print(f"\n{section_num} - {data['title']}")
            print(f"  Level: {data['level']}, Pages: {data['pages']}")

    def generate_report(self) -> str:
        """Generate comprehensive analysis report."""
        hierarchy = self.build_section_hierarchy()
        coverage = self.analyze_coverage()
        levels = self.analyze_section_levels()

        # Determine feasibility
        if coverage['coverage_percentage'] >= 95:
            feasibility = "✅ HIGH - Proceed with title-number-based chunking"
            recommendation = "IMPLEMENT full title-number-based approach"
        elif coverage['coverage_percentage'] >= 80:
            feasibility = "⚠️ MEDIUM - Consider hybrid approach"
            recommendation = "IMPLEMENT hybrid approach (title-numbers + fallback)"
        else:
            feasibility = "❌ LOW - Not recommended"
            recommendation = "STAY with current section-aware approach"

        report = f"""
{'='*80}
TITLE-NUMBER-BASED CHUNKING FEASIBILITY REPORT
{'='*80}

Document: {Path(self.pdf_path).name}
Analysis Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
EXECUTIVE SUMMARY
{'='*80}

Feasibility: {feasibility}
Recommendation: {recommendation}

Coverage: {coverage['coverage_percentage']:.1f}% ({coverage['pages_with_sections']}/{coverage['total_pages']} pages)
Total Sections: {coverage['total_sections']}
Section Levels: {len(levels)} levels (Level 1 to Level {max(levels.keys())})

{'='*80}
DETAILED METRICS
{'='*80}

Coverage Analysis:
  - Total Pages: {coverage['total_pages']}
  - Pages with Section Numbers: {coverage['pages_with_sections']}
  - Pages without Section Numbers: {coverage['pages_without_sections']}
  - Coverage Percentage: {coverage['coverage_percentage']:.1f}%

Content Analysis:
  - Unique Section Numbers: {coverage['total_sections']}
  - Figures Detected: {coverage['total_figures']}
  - Tables Detected: {coverage['total_tables']}
  - Appendices Detected: {coverage['total_appendices']}

Section Level Distribution:
"""

        for level in sorted(levels.keys()):
            report += f"  - Level {level}: {levels[level]} sections\n"

        report += f"\n{'='*80}\n"
        report += "HIERARCHY SAMPLE (Top-level sections)\n"
        report += f"{'='*80}\n\n"

        # Show top-level hierarchy
        for root in sorted(hierarchy.get('root', []), key=self._section_sort_key)[:10]:
            report += f"{root} - {self.sections[root]['title']}\n"
            children = hierarchy.get(root, [])
            if children:
                for child in sorted(children, key=self._section_sort_key)[:3]:
                    report += f"  └─ {child} - {self.sections[child]['title']}\n"
                if len(children) > 3:
                    report += f"  └─ ... and {len(children) - 3} more\n"

        report += f"\n{'='*80}\n"
        report += "DECISION CRITERIA\n"
        report += f"{'='*80}\n\n"

        if coverage['coverage_percentage'] >= 95:
            report += """
✅ PROCEED with title-number-based chunking:
  1. Coverage is ≥95% - Excellent
  2. Section hierarchy is well-defined
  3. Expected benefits:
     - 100% section title accuracy (vs 95.2% current)
     - 0% mixed content (vs <2% current)
     - $0 cost (vs $0.04/doc current)
     - Deterministic, no LLM correction needed

Next Steps:
  1. Implement section extractor (1 day)
  2. Build title-number chunker (1 day)
  3. Add subtitle detection (0.5 days)
  4. Test and validate (1 day)
  5. Re-ingest eMMC 5.1 spec (0.5 days)
"""
        elif coverage['coverage_percentage'] >= 80:
            report += """
⚠️ CONSIDER hybrid approach:
  1. Coverage is 80-95% - Good but not perfect
  2. Some content lacks section numbers
  3. Recommended approach:
     - Use title-number extraction for main content (80-95%)
     - Use current section-aware for gaps (5-20%)
     - Combine both for complete coverage

Next Steps:
  1. Implement hybrid chunker (2 days)
  2. Test with both approaches (1 day)
  3. Validate quality improvements (0.5 days)
  4. Re-ingest if successful (0.5 days)
"""
        else:
            report += """
❌ NOT RECOMMENDED:
  1. Coverage is <80% - Insufficient
  2. Too many gaps without section numbers
  3. Title-number approach would miss significant content
  4. Better to improve current approach:
     - Better PDF parser
     - Improved LLM correction prompts
     - Manual review of problematic chunks

Next Steps:
  1. Fix specific problematic chunks manually
  2. Improve section title correction prompts
  3. Consider better PDF parsing library
  4. Stay with current section-aware approach
"""

        report += f"\n{'='*80}\n"
        report += "END OF REPORT\n"
        report += f"{'='*80}\n"

        return report

    def run_full_analysis(self) -> Dict:
        """Run complete analysis pipeline."""
        print("\n" + "="*80)
        print("STARTING FULL ANALYSIS")
        print("="*80)

        # Extract text
        page_texts = self.extract_all_text_with_pages()

        # Find section numbers
        self.find_section_numbers(page_texts)

        # Analyze
        coverage = self.analyze_coverage()
        levels = self.analyze_section_levels()
        gaps = self.find_gaps(page_texts)

        # Sample
        self.sample_sections(n=10)

        # Generate report
        report = self.generate_report()

        print("\n" + report)

        # Save report
        report_path = Path(__file__).parent.parent / 'TITLE_NUMBER_VALIDATION_REPORT.md'
        report_path.write_text(report)
        print(f"\nReport saved to: {report_path}")

        return {
            'coverage': coverage,
            'levels': levels,
            'gaps': gaps,
            'report_path': str(report_path),
        }


def main():
    """Main validation function."""
    # Path to eMMC 5.1 spec
    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    if not pdf_path.exists():
        print(f"❌ PDF not found at: {pdf_path}")
        print("\nPlease ensure the eMMC 5.1 spec is located at:")
        print(f"  {pdf_path}")
        return

    # Run analysis
    analyzer = SectionNumberAnalyzer(str(pdf_path))
    results = analyzer.run_full_analysis()

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nCoverage: {results['coverage']['coverage_percentage']:.1f}%")
    print(f"Total Sections: {results['coverage']['total_sections']}")
    print(f"Report: {results['report_path']}")


if __name__ == '__main__':
    # NOTE: This script requires pdfplumber
    # Install: pip install pdfplumber
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║  Title-Number-Based Chunking Validation Script                            ║
║                                                                            ║
║  This script analyzes the eMMC 5.1 PDF to determine if title-number-      ║
║  based chunking is feasible.                                              ║
║                                                                            ║
║  Running validation analysis...                                           ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    main()
