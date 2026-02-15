"""Debug script to see actual text format in PDF."""

import sys
from pathlib import Path
import pdfplumber
import re

sys.path.insert(0, str(Path(__file__).parent.parent))


def inspect_pages(pdf_path, start_page, end_page):
    """Inspect actual text from pages."""
    print(f"\nInspecting pages {start_page}-{end_page} from {Path(pdf_path).name}")
    print("="*80)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page, end_page + 1):
            if page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]
                text = page.extract_text()

                if text:
                    print(f"\n{'='*80}")
                    print(f"PAGE {page_num}")
                    print('='*80)

                    # Show first 2000 characters
                    print(text[:2000])

                    # Look for section patterns
                    print(f"\n--- Searching for 6.6.2.X patterns ---")

                    patterns = [
                        r'6\.6\.2\.\d+',  # Basic pattern
                        r'^6\.6\.2\.\d+\s+[A-Z]',  # With title
                        r'\b6\.6\.2\.\d+\b',  # Word boundary
                    ]

                    for i, pattern in enumerate(patterns, 1):
                        matches = re.findall(pattern, text, re.MULTILINE)
                        if matches:
                            print(f"  Pattern {i} ({pattern}): {matches}")

                    print()


def main():
    """Main debug function."""
    pdf_path = Path(__file__).parent.parent / 'specs' / 'emmc5.1-protocol-JESD84-B51.pdf'

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    # Inspect pages 43-48 (where 6.6.2.X should be)
    inspect_pages(str(pdf_path), 43, 48)


if __name__ == '__main__':
    main()
