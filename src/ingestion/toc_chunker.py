"""
TOC-based chunking system for technical specifications.

This module implements a hybrid approach using Table of Contents (TOC) extraction
combined with bounded regex search to achieve high-accuracy chunking.

Components:
    - TOCExtractor: Extract TOC entries from PDF
    - TOCPreprocessor: Sort, infer parents, calculate page ranges
    - BoundedRegexSearcher: Find subsections within page ranges
    - ContentExtractor: Extract text and detect subtitles
    - IntelligentTruncator: Handle long sections
    - TOCBasedChunker: Main integration class
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import pdfplumber

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TOCExtractor:
    """
    Extract Table of Contents from PDF documents.

    This class identifies TOC pages and extracts section numbers, titles,
    and page numbers from the table of contents.
    """

    def __init__(self, pdf_path: str):
        """
        Initialize TOC extractor.

        Args:
            pdf_path: Path to PDF file
        """
        self.pdf_path = pdf_path
        self.toc_pages: List[int] = []
        self.toc_entries: List[Dict] = []

    def find_toc_pages(self, max_search_pages: int = 30) -> List[int]:
        """
        Find pages containing the Table of Contents.

        Uses heuristics to identify TOC pages:
        1. Contains "Contents" or "Table of Contents" header
        2. Has many page number references (e.g., "........ 45")
        3. Has section number patterns (e.g., "6.6.2 Title")

        Args:
            max_search_pages: Maximum pages to search (default: 30, front matter)

        Returns:
            List of page numbers containing TOC
        """
        logger.info(f"Searching for TOC pages in {self.pdf_path}")
        toc_pages = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                search_limit = min(max_search_pages, len(pdf.pages))

                for page_num in range(1, search_limit + 1):
                    page = pdf.pages[page_num - 1]
                    text = page.extract_text()

                    if not text:
                        continue

                    # Heuristic 1: "Contents" header
                    text_lower = text.lower()
                    has_contents_header = (
                        'contents' in text_lower
                        or 'table of contents' in text_lower
                    )

                    # Heuristic 2: Many page numbers (........ 45)
                    page_num_pattern = r'\.{3,}\s*\d+'
                    page_num_matches = len(re.findall(page_num_pattern, text))

                    # Heuristic 3: Section number patterns at start of lines
                    section_pattern = r'^\s*\d+\.\d+(?:\.\d+)?\s+[A-Z]'
                    section_matches = len(re.findall(section_pattern, text, re.MULTILINE))

                    # Criteria: header OR many page refs OR many section patterns
                    if has_contents_header or page_num_matches > 10 or section_matches > 5:
                        toc_pages.append(page_num)
                        logger.debug(
                            f"  Page {page_num}: TOC candidate "
                            f"(header={has_contents_header}, "
                            f"page_refs={page_num_matches}, "
                            f"sections={section_matches})"
                        )

            self.toc_pages = toc_pages
            logger.info(f"Found {len(toc_pages)} TOC pages: {toc_pages}")

            return toc_pages

        except Exception as e:
            logger.error(f"Error finding TOC pages: {e}")
            raise

    def extract_toc_entries(self) -> List[Dict]:
        """
        Extract TOC entries from identified TOC pages.

        Expected TOC format examples:
            - "6.6.2 HS400 Configuration ...................... 65"
            - "7.4.35 INI_TIMEOUT_AP [241] .................... 206"
            - "10.10.3 HS400 Device Command Output Timing ..... 180"

        Returns:
            List of dictionaries with keys:
                - section_number: str (e.g., "6.6.2")
                - section_title: str (e.g., "HS400 Configuration")
                - page_number: int (e.g., 65)
                - toc_page: int (page where this entry was found)
                - level: int (nesting level, e.g., 3 for "6.6.2")
                - pattern_used: int (which regex pattern matched)
        """
        if not self.toc_pages:
            logger.warning("No TOC pages found. Run find_toc_pages() first.")
            return []

        logger.info("Extracting TOC entries...")
        toc_entries = []

        # Multiple regex patterns to try (in order of preference)
        patterns = [
            # Pattern 1: "6.6.2 Title ........ 65"
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\.\n]{5,150}?)\s*\.{3,}\s*(\d+)\s*$',

            # Pattern 2: "6.6.2 Title  65" (minimal dots)
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\n]{5,150}?)\s+(\d+)\s*$',

            # Pattern 3: With brackets like "7.4.35 INI_TIMEOUT_AP [241] ... 206"
            r'^\s*(\d+\.[\d\.]+)\s+([A-Z][^\n]{5,150}?)\[[\d]+\]\s*\.{0,}\s*(\d+)\s*$',

            # Pattern 4: More flexible
            r'(\d+\.[\d\.]+)\s+([A-Z].*?)\s+\.{2,}\s*(\d+)',
        ]

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num in self.toc_pages:
                    page = pdf.pages[page_num - 1]
                    text = page.extract_text()

                    if not text:
                        continue

                    # Try each pattern
                    for pattern_idx, pattern in enumerate(patterns):
                        matches = re.finditer(pattern, text, re.MULTILINE)

                        for match in matches:
                            section_num = match.group(1)
                            section_title = match.group(2).strip()
                            page_number = int(match.group(3))

                            # Clean up title (remove excessive dots/spaces)
                            section_title = re.sub(r'\s*\.{2,}\s*', ' ', section_title)
                            section_title = re.sub(r'\s{2,}', ' ', section_title)
                            section_title = section_title.strip()

                            entry = {
                                'section_number': section_num,
                                'section_title': section_title,
                                'page_number': page_number,
                                'toc_page': page_num,
                                'pattern_used': pattern_idx,
                                'level': len(section_num.split('.'))
                            }

                            toc_entries.append(entry)

            # Remove duplicates (same section number)
            seen = set()
            unique_entries = []

            for entry in toc_entries:
                if entry['section_number'] not in seen:
                    seen.add(entry['section_number'])
                    unique_entries.append(entry)

            self.toc_entries = unique_entries

            logger.info(f"Extracted {len(unique_entries)} unique TOC entries")

            # Log sample entries
            if unique_entries:
                logger.debug("Sample TOC entries:")
                for entry in unique_entries[:5]:
                    logger.debug(
                        f"  {entry['section_number']} - {entry['section_title'][:50]}... "
                        f"(page {entry['page_number']})"
                    )

            return unique_entries

        except Exception as e:
            logger.error(f"Error extracting TOC entries: {e}")
            raise

    def extract(self) -> List[Dict]:
        """
        Main method: find TOC pages and extract entries.

        Returns:
            List of TOC entries with complete metadata
        """
        logger.info(f"Starting TOC extraction from {self.pdf_path}")

        # Step 1: Find TOC pages
        toc_pages = self.find_toc_pages()

        if not toc_pages:
            logger.warning("No TOC pages found in document")
            return []

        # Step 2: Extract entries
        entries = self.extract_toc_entries()

        logger.info(f"TOC extraction complete: {len(entries)} entries")

        return entries


class TOCPreprocessor:
    """
    Preprocess TOC entries for optimal chunking.

    Operations:
        1. Sort entries by section number
        2. Infer missing parent sections
        3. Calculate page ranges for each section
        4. Flag long sections that need truncation
    """

    def __init__(self):
        """Initialize preprocessor."""
        pass

    def sort_entries(self, entries: List[Dict]) -> List[Dict]:
        """
        Sort TOC entries by section number.

        Fixes out-of-order entries that may occur due to TOC formatting.

        Args:
            entries: List of TOC entries

        Returns:
            Sorted list of entries
        """
        logger.info("Sorting TOC entries by section number...")

        sorted_entries = sorted(
            entries,
            key=lambda e: self._parse_section_number(e['section_number'])
        )

        logger.debug(f"Sorted {len(sorted_entries)} entries")

        return sorted_entries

    def _parse_section_number(self, section_num: str) -> Tuple:
        """
        Parse section number for proper sorting.

        Examples:
            "6.6.2" -> (6, 6, 2)
            "10.10.3" -> (10, 10, 3)
            "Appendix A.2" -> (999, 2)  # Appendices sorted last

        Args:
            section_num: Section number string

        Returns:
            Tuple of integers for sorting
        """
        # Handle appendices
        clean_num = section_num.replace('Appendix ', '').strip('.')

        parts = clean_num.split('.')

        # Convert to integers, use 999 for non-numeric parts
        return tuple(int(p) if p.isdigit() else 999 for p in parts)

    def infer_missing_parents(self, entries: List[Dict]) -> List[Dict]:
        """
        Create synthetic entries for missing parent sections.

        For example, if TOC contains 5.3.1, 5.3.2, 5.3.3 but not 5.3,
        this creates a synthetic 5.3 entry.

        Args:
            entries: List of TOC entries

        Returns:
            Original entries + synthetic parent entries
        """
        logger.info("Inferring missing parent sections...")

        existing = {e['section_number']: e for e in entries}
        synthetic = []

        for entry in entries:
            parts = entry['section_number'].split('.')

            # For each level, check if parent exists
            for i in range(1, len(parts)):
                parent_num = '.'.join(parts[:i])

                if parent_num not in existing:
                    # Find all children of this parent
                    children = [
                        e for e in entries
                        if e['section_number'].startswith(parent_num + '.')
                    ]

                    if children:
                        # Use first child's page as parent's page
                        first_child = min(children, key=lambda x: x['page_number'])

                        synthetic_entry = {
                            'section_number': parent_num,
                            'section_title': '[Inferred]',
                            'page_number': first_child['page_number'],
                            'level': len(parent_num.split('.')),
                            'inferred': True,
                            'toc_page': None
                        }

                        synthetic.append(synthetic_entry)
                        existing[parent_num] = synthetic_entry

        logger.info(f"Inferred {len(synthetic)} missing parent sections")

        return entries + synthetic

    def calculate_page_ranges(self, entries: List[Dict]) -> List[Dict]:
        """
        Calculate start and end page for each section.

        A section starts at its page and ends at (next section's page - 1).

        Args:
            entries: List of TOC entries

        Returns:
            Entries with added 'page_start' and 'page_end' fields
        """
        logger.info("Calculating page ranges...")

        # Sort by page number
        sorted_entries = sorted(entries, key=lambda e: e['page_number'])

        for i, entry in enumerate(sorted_entries):
            entry['page_start'] = entry['page_number']

            # End page is next section's start - 1
            if i + 1 < len(sorted_entries):
                # Ensure page_end >= page_start (for sections on same page)
                entry['page_end'] = max(
                    entry['page_start'],
                    sorted_entries[i + 1]['page_number'] - 1
                )
            else:
                # Last section goes to end of document
                # TODO: Make this configurable or detect from PDF
                entry['page_end'] = 352  # eMMC spec has 352 pages

        logger.debug("Page ranges calculated")

        return entries

    def flag_long_sections(
        self,
        entries: List[Dict],
        threshold: int = 10
    ) -> List[Dict]:
        """
        Flag sections spanning more than threshold pages.

        These sections will need intelligent truncation.

        Args:
            entries: List of TOC entries
            threshold: Page count threshold (default: 10)

        Returns:
            Entries with added 'is_long' and 'page_count' fields
        """
        logger.info(f"Flagging sections longer than {threshold} pages...")

        long_count = 0

        for entry in entries:
            page_count = entry['page_end'] - entry['page_start'] + 1
            entry['page_count'] = page_count
            entry['is_long'] = page_count > threshold

            if entry['is_long']:
                long_count += 1
                logger.debug(
                    f"  Long section: {entry['section_number']} "
                    f"({page_count} pages)"
                )

        logger.info(f"Flagged {long_count} long sections")

        return entries

    def process(self, entries: List[Dict]) -> List[Dict]:
        """
        Main preprocessing pipeline.

        Args:
            entries: Raw TOC entries

        Returns:
            Preprocessed entries ready for chunking
        """
        logger.info("Starting TOC preprocessing...")

        # Step 1: Sort
        entries = self.sort_entries(entries)

        # Step 2: Infer parents
        entries = self.infer_missing_parents(entries)

        # Step 3: Calculate ranges
        entries = self.calculate_page_ranges(entries)

        # Step 4: Flag long sections
        entries = self.flag_long_sections(entries)

        logger.info(f"Preprocessing complete: {len(entries)} total entries")

        return entries


# Placeholder classes for other components (to be implemented in later phases)

class BoundedRegexSearcher:
    """
    Find subsections within bounded page ranges.

    This class searches for subsections (e.g., 6.6.2.3) within the page range
    of their parent section (e.g., 6.6.2). By bounding the search, we reduce
    false positives and improve accuracy.
    """

    def __init__(self, pdf_path: str, page_offset: int = 20):
        """
        Initialize bounded regex searcher.

        Args:
            pdf_path: Path to PDF file
            page_offset: Offset between TOC page numbers and PDF page numbers
                        (default: 20 for eMMC spec where doc page 1 = PDF page 21)
        """
        self.pdf_path = pdf_path
        self.page_offset = page_offset

    def find_subsections(self, parent_section: Dict) -> List[Dict]:
        """
        Find all subsections within parent's page range.

        For example, if parent_section is:
            {
                'section_number': '6.6.2',
                'page_start': 43,
                'page_end': 47
            }

        This will search pages 43-47 for:
            6.6.2.1 [title]
            6.6.2.2 [title]
            6.6.2.3 [title]  ← Our problematic section!
            etc.

        Args:
            parent_section: TOC entry with page_start and page_end

        Returns:
            List of subsection dictionaries with metadata
        """
        parent_num = parent_section['section_number']
        start_page = parent_section.get('page_start', parent_section['page_number'])
        end_page = parent_section.get('page_end', start_page)

        logger.debug(
            f"Searching for subsections of {parent_num} "
            f"in pages {start_page}-{end_page}"
        )

        # Extract text from page range
        page_texts = self._extract_page_range_by_page(start_page, end_page)

        if not page_texts:
            return []

        # Pattern for subsections
        # Escape dots in parent number: 6.6.2 -> 6\.6\.2
        escaped_parent = re.escape(parent_num)

        # Match: "6.6.2.3 Title text here" or '6.6.2.3 "Title with quotes"'
        # Group 1: subsection digit (3)
        # Group 2: title (any non-newline chars, 5-200 chars)
        # Don't restrict first character - titles can start with quotes, uppercase, etc.
        pattern = rf'^{escaped_parent}\.(\d+)\s+([^\n]{{5,200}}?)(?=\s*\n|$)'

        subsections = []

        # Search in each page
        for page_num, text in page_texts.items():
            matches = re.finditer(pattern, text, re.MULTILINE)

            for match in matches:
                subsection_digit = match.group(1)
                subsection_num = f"{parent_num}.{subsection_digit}"
                subsection_title = match.group(2).strip()

                # Clean title (remove trailing dots/page numbers)
                subsection_title = re.sub(r'\s*\.{2,}\s*\d+\s*$', '', subsection_title)
                subsection_title = re.sub(r'\s{2,}', ' ', subsection_title)
                subsection_title = subsection_title.strip()

                # Skip if title looks like noise
                if len(subsection_title) < 3:
                    continue

                subsection = {
                    'section_number': subsection_num,
                    'section_title': subsection_title,
                    'page_number': page_num,
                    'level': len(subsection_num.split('.')),
                    'parent': parent_num,
                    'from_regex': True  # Flag to indicate this was found by regex
                }

                subsections.append(subsection)

                logger.debug(
                    f"  Found: {subsection_num} - {subsection_title[:40]}... "
                    f"(page {page_num})"
                )

        # Remove duplicates (same section number)
        seen = set()
        unique_subsections = []

        for sub in subsections:
            if sub['section_number'] not in seen:
                seen.add(sub['section_number'])
                unique_subsections.append(sub)

        # Validate ascending order
        unique_subsections = self._validate_order(unique_subsections)

        return unique_subsections

    def _extract_page_range_by_page(
        self,
        start_page: int,
        end_page: int
    ) -> Dict[int, str]:
        """
        Extract text from a range of pages, keeping track of page numbers.

        Args:
            start_page: First page to extract (document page number)
            end_page: Last page to extract (document page number)

        Returns:
            Dictionary mapping document_page_number -> text
        """
        page_texts = {}

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for doc_page_num in range(start_page, end_page + 1):
                    # Convert document page to PDF page
                    pdf_page_num = doc_page_num + self.page_offset

                    if 1 <= pdf_page_num <= len(pdf.pages):
                        page = pdf.pages[pdf_page_num - 1]
                        text = page.extract_text()

                        if text:
                            # Store with document page number as key
                            page_texts[doc_page_num] = text

        except Exception as e:
            logger.error(f"Error extracting pages {start_page}-{end_page}: {e}")

        return page_texts

    def _validate_order(self, subsections: List[Dict]) -> List[Dict]:
        """
        Validate that subsections are in ascending numerical order.

        Args:
            subsections: List of subsections

        Returns:
            Sorted and validated subsections
        """
        if not subsections:
            return subsections

        # Sort by the last digit in section number
        sorted_subs = sorted(
            subsections,
            key=lambda s: int(s['section_number'].split('.')[-1])
        )

        # Check for gaps or duplicates
        prev_num = None
        for sub in sorted_subs:
            current_num = int(sub['section_number'].split('.')[-1])

            if prev_num is not None and current_num != prev_num + 1:
                # Gap detected
                logger.debug(
                    f"  Gap in subsections: {prev_num} -> {current_num} "
                    f"(missing {prev_num + 1})"
                )

            prev_num = current_num

        return sorted_subs

    def search_all(self, toc_entries: List[Dict]) -> List[Dict]:
        """
        Search for subsections in all TOC entries.

        For each TOC entry, searches its page range for deeper subsections.

        Args:
            toc_entries: List of preprocessed TOC entries

        Returns:
            List of all found subsections
        """
        logger.info("Searching for subsections in all TOC entries...")

        all_subsections = []
        entries_searched = 0
        entries_with_subsections = 0

        for entry in toc_entries:
            # Skip inferred entries (they're synthetic)
            if entry.get('inferred'):
                continue

            # Only search level 2 and 3 sections
            # (Level 4+ is too deep, unlikely to have children)
            if entry['level'] > 3:
                continue

            # Skip if page range is invalid
            if entry.get('page_start', 0) > entry.get('page_end', 0):
                continue

            entries_searched += 1

            # Search for subsections
            subsections = self.find_subsections(entry)

            if subsections:
                entries_with_subsections += 1
                all_subsections.extend(subsections)

        logger.info(
            f"Searched {entries_searched} entries, "
            f"found subsections in {entries_with_subsections} entries"
        )
        logger.info(f"Total subsections found: {len(all_subsections)}")

        return all_subsections


class ContentExtractor:
    """
    Extract content and detect subtitles for sections.

    Phase 3: Content extraction with subtitle detection.
    """

    def __init__(self, pdf_path: str, page_offset: int = 20):
        """
        Initialize content extractor.

        Args:
            pdf_path: Path to PDF file
            page_offset: Offset between document pages and PDF pages
        """
        self.pdf_path = pdf_path
        self.page_offset = page_offset
        logger.debug(f"ContentExtractor initialized with page_offset={page_offset}")

    def extract_content(self, section: Dict) -> Dict:
        """
        Extract content for a single section.

        Handles:
        - Single page sections
        - Multi-page sections
        - Subtitle detection within content

        Args:
            section: Section dictionary with page_start and page_end

        Returns:
            Section dict with added 'content' and 'subtitle' fields
        """
        section_num = section['section_number']
        start_page = section.get('page_start', section['page_number'])
        end_page = section.get('page_end', start_page)

        logger.debug(
            f"Extracting content for {section_num} "
            f"(pages {start_page}-{end_page})"
        )

        # Extract full text from page range
        full_text = self._extract_page_range(start_page, end_page)

        if not full_text:
            logger.warning(f"No content extracted for {section_num}")
            section['content'] = ""
            section['subtitle'] = None
            section['full_text'] = ""  # Store for later title extraction
            return section

        # Store full text for title extraction (before cleaning)
        section['full_text'] = full_text

        # Detect subtitle
        subtitle = self._detect_subtitle(full_text, section_num)

        # Clean content (remove section header, page numbers, etc.)
        cleaned_content = self._clean_content(full_text, section_num)

        section['content'] = cleaned_content
        section['subtitle'] = subtitle

        logger.debug(
            f"  Extracted {len(cleaned_content)} chars, "
            f"subtitle: {subtitle if subtitle else 'None'}"
        )

        return section

    def extract_all_content(self, sections: List[Dict]) -> List[Dict]:
        """
        Extract content for all sections.

        Args:
            sections: List of section dictionaries

        Returns:
            Sections with added content and subtitle fields
        """
        logger.info(f"Extracting content for {len(sections)} sections...")

        enriched_sections = []

        for section in sections:
            enriched = self.extract_content(section)

            # For inferred sections, try to extract the actual title from content
            if section.get('inferred') and section.get('section_title') == '[Inferred]':
                # Use full_text (before cleaning) for better title extraction
                actual_title = self._extract_section_title(
                    enriched.get('full_text', enriched.get('content', '')),
                    section['section_number']
                )
                if actual_title:
                    enriched['section_title'] = actual_title
                    logger.debug(f"  Extracted title for inferred section {section['section_number']}: {actual_title}")

            # Clean up full_text (don't need to store it)
            enriched.pop('full_text', None)

            enriched_sections.append(enriched)

        logger.info(f"Content extraction complete for {len(enriched_sections)} sections")

        return enriched_sections

    def _extract_section_title(self, text: str, section_num: str) -> Optional[str]:
        """
        Extract the actual section title from PDF content.

        Looks for patterns like:
        - "7 Device Register"
        - "7.3 CSD Register"
        - "7.3.3 TAAC [119:112]"
        - "Device Register" (for top-level sections without number in heading)

        Args:
            text: Section content (preferably before cleaning)
            section_num: Section number to look for

        Returns:
            Extracted title or None
        """
        if not text:
            return None

        # Clean section number for regex (escape dots)
        escaped_num = re.escape(section_num.rstrip('.'))

        search_text = text[:2000]  # Search first 2000 chars

        # Pattern 1: Section number followed by title on same line
        # e.g., "7.3 CSD Register" or "7.3 CSD Register (cont'd)"
        patterns = [
            # Match "7.3 CSD Register" anywhere in text
            rf'{escaped_num}\s+([A-Z][^\n]{{2,80}}?)(?:\n|$|\.\.\.)',
        ]

        for pattern in patterns:
            match = re.search(pattern, search_text, re.MULTILINE)
            if match:
                title = match.group(1).strip()

                # Clean up the title
                # Remove trailing punctuation except for brackets
                title = re.sub(r'[.,;:]\s*$', '', title)

                # Remove common suffixes like "(cont'd)"
                title = re.sub(r"\s*\(cont['']d\)\s*$", '', title, flags=re.IGNORECASE)

                # Skip if it looks like page content rather than a title
                if len(title) > 80 or title.count('\n') > 0:
                    continue

                # Skip if it's just numbers or special chars
                if not any(c.isalpha() for c in title):
                    continue

                # Skip if it starts with "Page " (page references)
                if title.startswith('Page '):
                    continue

                # Skip if it looks like a table entry (contains colons with values)
                # e.g., "V -1.95 V V voltage Range" or "70: V -1.95 V"
                if re.match(r'^\d+:', title) or title.count(':') > 1:
                    continue

                # Skip if it's too short (less than 5 chars) unless it's an acronym
                if len(title) < 5 and not title.isupper():
                    continue

                logger.debug(f"  Found title for {section_num}: {title}")
                return title

        # Pattern 2 is disabled for now - it causes too many false positives
        # Top-level inferred sections will keep "[Inferred]" as title
        # This is safer than picking up random capitalized text from the page

        return None

    def _extract_page_range(self, start_page: int, end_page: int) -> str:
        """
        Extract text from page range.

        Args:
            start_page: First page (document page number)
            end_page: Last page (document page number)

        Returns:
            Combined text from all pages
        """
        all_text = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for doc_page_num in range(start_page, end_page + 1):
                    # Convert document page to PDF page
                    pdf_page_num = doc_page_num + self.page_offset

                    if 0 < pdf_page_num <= len(pdf.pages):
                        page = pdf.pages[pdf_page_num - 1]
                        text = page.extract_text()

                        if text:
                            all_text.append(text)
        except Exception as e:
            logger.error(f"Error extracting pages {start_page}-{end_page}: {e}")
            return ""

        return "\n\n".join(all_text)

    def _detect_subtitle(self, text: str, section_num: str) -> Optional[str]:
        """
        Detect subtitle in content.

        Looks for patterns like:
        - "HS400" (quoted text near beginning)
        - Bold/emphasized text
        - Text in specific formats

        Args:
            text: Full section text
            section_num: Section number for context

        Returns:
            Detected subtitle or None
        """
        if not text:
            return None

        # Only look at first 500 chars to avoid false positives from body text
        search_text = text[:500]

        # Common document headers/footers and non-subtitle patterns to exclude
        excluded_patterns = [
            r'JEDEC Standard No\.',
            r'Page \d+',
            r'^\d+\s*$',  # Just page numbers
            r'Copyright',
            r'All rights reserved',
            r'^Table \d+',  # Table captions like "Table 79 — CSD register structure"
            r'^Figure \d+',  # Figure captions
            r'^\d+\.\d+',  # Section numbers like "7.3.1"
        ]

        # Pattern 1: Look for quoted text near the beginning
        # e.g., "HS400" timing mode selection
        match = re.search(r'^[^\n]{0,100}?"([^"]{2,50})"', search_text, re.MULTILINE)
        if match:
            subtitle = match.group(1).strip()
            logger.debug(f"  Detected subtitle (quoted): {subtitle}")
            return subtitle

        # Pattern 2: Look for text in specific formats
        # e.g., HS400, HS200, etc. (capital letters + numbers)
        match = re.search(r'^[^\n]{0,100}?\b([A-Z]{2,}[0-9]{2,})\b', search_text, re.MULTILINE)
        if match:
            subtitle = match.group(1).strip()
            logger.debug(f"  Detected subtitle (pattern): {subtitle}")
            return subtitle

        # Pattern 3: Look for short capitalized phrases at start
        # e.g., "High-speed mode"
        lines = search_text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip section number line
            if line.startswith(section_num):
                continue

            # Skip document headers/footers
            is_excluded = False
            for pattern in excluded_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    is_excluded = True
                    break
            if is_excluded:
                continue

            # Look for short capitalized phrase (5-50 chars)
            if 5 <= len(line) <= 50 and line[0].isupper():
                # Check if it looks like a title (not regular sentence)
                if not line.endswith('.') or line.count(' ') <= 5:
                    logger.debug(f"  Detected subtitle (capitalized): {line}")
                    return line

        return None

    def _clean_content(self, text: str, section_num: str) -> str:
        """
        Clean extracted content.

        Removes:
        - Document headers (JEDEC Standard No.)
        - Page numbers (Page XXX)
        - Section number headers
        - Continuation markers (cont'd)
        - Excessive whitespace

        Args:
            text: Raw extracted text
            section_num: Section number to remove

        Returns:
            Cleaned text ready for indexing
        """
        if not text:
            return ""

        lines = text.split('\n')
        cleaned_lines = []
        skip_initial_headers = True

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines at the beginning
            if skip_initial_headers and not line_stripped:
                continue

            # Skip document header lines
            if re.match(r'^JEDEC Standard No\.', line_stripped, re.IGNORECASE):
                continue

            # Skip page number lines
            if re.match(r'^Page \d+$', line_stripped, re.IGNORECASE):
                continue

            # Skip standalone page footers like "JESD84-B51    43"
            if re.match(r'^JESD84-B\d+\s+\d+$', line_stripped):
                continue

            # Skip section number lines that are just the number
            # e.g., "7.3.1" or "6.6.2.3"
            if re.match(rf'^{re.escape(section_num.rstrip("."))}\.?\s*$', line_stripped):
                continue

            # Skip section headers with (cont'd)
            # e.g., "7.3 CSD Register (cont'd)" or just "CSD Register (cont'd)"
            # Note: PDFs use various apostrophe types: ' (U+0027), ' (U+2018), ' (U+2019)
            # Using explicit Unicode codes to match all apostrophe variants
            if re.search(r"\(cont[\u0027\u2018\u2019]?d\)", line_stripped, re.IGNORECASE):
                # Skip any line ending with (cont'd) that looks like a title
                # Titles are typically short and don't end with periods
                if len(line_stripped) < 80 and not line_stripped.endswith('.'):
                    continue

            # Skip subsection title lines (e.g., "7.3.1 CSD_STRUCTURE [127:126]")
            # Pattern: section number + uppercase title + optional field notation
            if re.match(r'^\d+(\.\d+)+\s+[A-Z_]+(\s+\[[\d:]+\])?$', line_stripped):
                continue

            # We've passed the initial headers
            if line_stripped:
                skip_initial_headers = False

            cleaned_lines.append(line)

        # Join lines back together
        cleaned_text = '\n'.join(cleaned_lines)

        # Remove section number at the start of lines
        # e.g., "6.6.2.3 Title..." -> "Title..."
        pattern = rf'^\s*{re.escape(section_num.rstrip("."))}\s+'
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.MULTILINE)

        # Remove inline page footers
        cleaned_text = re.sub(r'JESD84-B\d+\s+\d+', '', cleaned_text)

        # Normalize whitespace
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # Max 2 consecutive newlines
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)  # Max 1 space
        cleaned_text = re.sub(r'[ \t]+\n', '\n', cleaned_text)  # Remove trailing spaces

        return cleaned_text.strip()


class IntelligentTruncator:
    """
    Handle long sections with intelligent splitting.

    Phase 4: Split long sections while preserving context.
    """

    def __init__(
        self,
        max_tokens: int = 800,
        min_tokens: int = 100,
        overlap_tokens: int = 50
    ):
        """
        Initialize truncator.

        Args:
            max_tokens: Maximum tokens per chunk
            min_tokens: Minimum tokens per chunk
            overlap_tokens: Overlap between chunks for context
        """
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens
        logger.debug(
            f"IntelligentTruncator initialized: "
            f"max_tokens={max_tokens}, min_tokens={min_tokens}, "
            f"overlap_tokens={overlap_tokens}"
        )

    def process_all(self, sections: List[Dict]) -> List[Dict]:
        """
        Process all sections, splitting long ones.

        Args:
            sections: List of sections with content

        Returns:
            List of sections with long ones split into chunks
        """
        logger.info(f"Processing {len(sections)} sections for truncation...")

        processed_sections = []
        split_count = 0

        for section in sections:
            content = section.get('content', '')

            # Estimate token count (rough: 1 token ≈ 4 chars)
            estimated_tokens = len(content) // 4

            if estimated_tokens > self.max_tokens:
                # Split long section
                chunks = self._split_section(section)
                processed_sections.extend(chunks)
                split_count += 1
                logger.debug(
                    f"  Split {section['section_number']} into {len(chunks)} chunks"
                )
            else:
                # Keep as-is
                processed_sections.append(section)

        logger.info(
            f"Truncation complete: {len(processed_sections)} total sections "
            f"({split_count} were split)"
        )

        return processed_sections

    def _split_section(self, section: Dict) -> List[Dict]:
        """
        Split a long section into multiple chunks.

        Improved strategy:
        1. Split by paragraphs (double newlines)
        2. If paragraph is too long, split by sentences
        3. Group into chunks with sliding window overlap
        4. Ensure chunks never exceed max_tokens

        Args:
            section: Section dictionary with content

        Returns:
            List of chunk dictionaries
        """
        content = section.get('content', '')

        # Split by paragraphs and handle oversized ones
        paragraphs = content.split('\n\n')
        processed_paragraphs = []

        for para in paragraphs:
            para_tokens = len(para) // 4

            if para_tokens > self.max_tokens:
                # Paragraph too large - split by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                processed_paragraphs.extend(sentences)
            else:
                processed_paragraphs.append(para)

        # Group paragraphs/sentences into chunks with overlap
        chunks = []
        current_chunk_parts = []
        current_size = 0
        previous_chunk_tail = ""  # For overlap

        for part in processed_paragraphs:
            part_tokens = len(part) // 4

            # Check if adding this part would exceed limit
            if current_size + part_tokens > self.max_tokens:
                if current_chunk_parts:
                    # Save current chunk
                    chunk_text = '\n\n'.join(current_chunk_parts)
                    chunks.append(chunk_text)

                    # Create overlap from end of current chunk
                    # Take last N chars for overlap
                    overlap_chars = self.overlap_tokens * 4
                    previous_chunk_tail = chunk_text[-overlap_chars:] if len(chunk_text) > overlap_chars else chunk_text

                    # Start new chunk with overlap + current part
                    if previous_chunk_tail:
                        current_chunk_parts = [previous_chunk_tail, part]
                        current_size = len(previous_chunk_tail) // 4 + part_tokens
                    else:
                        current_chunk_parts = [part]
                        current_size = part_tokens
                else:
                    # Single part exceeds limit - force add it
                    current_chunk_parts = [part]
                    current_size = part_tokens
            else:
                # Add to current chunk
                current_chunk_parts.append(part)
                current_size += part_tokens

        # Add remaining parts as final chunk
        if current_chunk_parts:
            chunks.append('\n\n'.join(current_chunk_parts))

        # If still no chunks (empty content), return original section
        if not chunks:
            return [section]

        # Create chunk dictionaries
        chunk_sections = []

        for idx, chunk_content in enumerate(chunks):
            chunk_section = section.copy()
            chunk_section['content'] = chunk_content
            chunk_section['chunk_index'] = idx
            chunk_section['total_chunks'] = len(chunks)
            chunk_section['is_split'] = True

            # Keep the original section_number - don't modify it for split chunks
            # The chunk_index and total_chunks fields track which part this is

            chunk_sections.append(chunk_section)

        return chunk_sections

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Simple heuristic: 1 token ≈ 4 characters

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        return len(text) // 4


class TOCBasedChunker:
    """
    Main TOC + Regex hybrid chunker.

    Integrates all components to provide a complete chunking solution.
    """

    def __init__(
        self,
        chunk_size: int = 350,
        max_chunk_size: int = 800,
        min_chunk_size: int = 100
    ):
        """
        Initialize TOC-based chunker.

        Args:
            chunk_size: Target chunk size in tokens (default: 350)
            max_chunk_size: Maximum chunk size in tokens (default: 800)
            min_chunk_size: Minimum chunk size in tokens (default: 100)
        """
        self.chunk_size = chunk_size
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, pdf_path: str) -> List[Dict]:
        """
        Main chunking pipeline.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of chunks with complete metadata
        """
        logger.info(f"Starting TOC-based chunking for {pdf_path}")

        # Phase 1: Extract TOC
        logger.info("Phase 1: Extracting TOC...")
        extractor = TOCExtractor(pdf_path)
        toc_entries = extractor.extract()
        logger.info(f"  ✓ Extracted {len(toc_entries)} TOC entries")

        # Phase 2: Preprocess TOC
        logger.info("Phase 2: Preprocessing TOC...")
        preprocessor = TOCPreprocessor()
        processed_entries = preprocessor.process(toc_entries)
        logger.info(
            f"  ✓ Processed {len(processed_entries)} entries "
            f"(incl. {len(processed_entries) - len(toc_entries)} inferred)"
        )

        # Phase 3: Find subsections
        logger.info("Phase 3: Finding subsections with bounded regex...")
        searcher = BoundedRegexSearcher(pdf_path, page_offset=20)
        subsections = searcher.search_all(processed_entries)
        logger.info(f"  ✓ Found {len(subsections)} subsections")

        # Combine TOC + subsections
        all_sections = processed_entries + subsections

        # Store for later use in path building
        self.preprocessed_entries = all_sections

        # Phase 4: Extract content
        logger.info("Phase 4: Extracting content and detecting subtitles...")
        content_extractor = ContentExtractor(pdf_path, page_offset=20)
        sections_with_content = content_extractor.extract_all_content(all_sections)
        logger.info(f"  ✓ Extracted content for {len(sections_with_content)} sections")

        # Phase 5: Intelligent truncation
        logger.info("Phase 5: Applying intelligent truncation...")
        truncator = IntelligentTruncator(
            max_tokens=self.max_chunk_size,
            min_tokens=self.min_chunk_size
        )
        final_chunks = truncator.process_all(sections_with_content)
        logger.info(f"  ✓ Created {len(final_chunks)} final chunks")

        logger.info(f"TOC-based chunking complete: {len(final_chunks)} chunks")

        return final_chunks
