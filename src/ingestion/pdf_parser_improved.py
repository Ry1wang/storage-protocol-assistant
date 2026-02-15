"""Improved PDF parsing with intelligent section title extraction."""

from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
import re

from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import (
    Title,
    NarrativeText,
    ListItem,
    Table,
    FigureCaption,
    Element,
)

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ImprovedPDFParser:
    """Parse PDF documents with intelligent section title extraction."""

    # Patterns to EXCLUDE from section titles
    EXCLUDE_PATTERNS = [
        r'^Figure\s+\d+',           # Figure captions
        r'^Table\s+\d+',            # Table captions
        r'^Figures?$',              # Generic "Figures"
        r'^Tables?$',               # Generic "Tables"
        r'^Contents?$',             # Table of contents
        r'^Page\s+\d+',             # Page numbers
        r'^Reserved',               # Reserved fields
        r'^JEDEC',                  # Standard headers
        r'^\w{1,3}$',               # Very short (likely noise)
    ]

    # Patterns to IDENTIFY valid section headings
    SECTION_PATTERNS = [
        r'^\d+\.\d+\.?\d*\s+\w+',   # "6.3.3 Boot operation"
        r'^[A-Z]\.\d+\.?\d*\s+\w+', # "B.2.6 Queue-Barrier"
        r'^Chapter\s+\d+',          # "Chapter 4"
        r'^Appendix\s+[A-Z]',       # "Appendix B"
        r'^Section\s+\d+',          # "Section 4"
    ]

    def __init__(self):
        """Initialize improved PDF parser."""
        self.supported_element_types = {
            Title,
            NarrativeText,
            ListItem,
            Table,
            FigureCaption,
        }

    def parse_pdf(
        self,
        file_path: str,
        strategy: str = "fast",
    ) -> List[Dict[str, Any]]:
        """
        Parse a PDF file with improved section tracking.

        Args:
            file_path: Path to the PDF file
            strategy: Parsing strategy - 'fast' or 'hi_res'

        Returns:
            List of parsed elements with metadata
        """
        logger.info(f"Parsing PDF: {file_path} with strategy: {strategy}")

        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        try:
            elements = partition_pdf(
                filename=str(pdf_path),
                strategy=strategy,
                include_page_breaks=True,
                infer_table_structure=(strategy == "hi_res"),
            )
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            raise

        # Process elements with improved section tracking
        parsed_elements = []
        current_section = None
        section_hierarchy = []
        last_valid_section = None  # Track last known good section

        for element in elements:
            element_data = self._process_element(
                element, current_section, section_hierarchy
            )

            if element_data:
                parsed_elements.append(element_data)

                # Update section tracking ONLY for valid headings
                if isinstance(element, Title):
                    is_valid, section_info = self._is_valid_section_title(element.text)

                    if is_valid:
                        current_section = section_info['cleaned_title']
                        last_valid_section = current_section
                        level = section_info['level']

                        # Update hierarchy based on level
                        if level == 1:
                            section_hierarchy = [current_section]
                        elif level == 2:
                            section_hierarchy = section_hierarchy[:1] + [current_section]
                        elif level == 3:
                            section_hierarchy = section_hierarchy[:2] + [current_section]
                        else:
                            # Deeper nesting or unknown level
                            if len(section_hierarchy) >= 3:
                                section_hierarchy = section_hierarchy[:3] + [current_section]
                            else:
                                section_hierarchy.append(current_section)

                        logger.debug(f"Valid section: {current_section} (level {level})")
                    else:
                        # Invalid title (figure/table caption) - keep last valid section
                        logger.debug(f"Skipped non-section title: {element.text[:50]}")
                        current_section = last_valid_section

        logger.info(f"Extracted {len(parsed_elements)} elements from PDF")
        logger.info(f"Identified {len(set(e['section_title'] for e in parsed_elements if e.get('section_title')))} unique sections")
        return parsed_elements

    def _is_valid_section_title(self, text: str) -> tuple[bool, Optional[Dict]]:
        """
        Validate if a title is a real section heading.

        Args:
            text: Title text to validate

        Returns:
            Tuple of (is_valid, section_info_dict)
        """
        if not text or len(text.strip()) < 3:
            return False, None

        cleaned = text.strip()

        # Check exclusion patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if re.match(pattern, cleaned, re.IGNORECASE):
                return False, None

        # Check if it's too long (likely concatenated text)
        if len(cleaned) > 120:
            return False, None

        # Check for section number patterns
        section_level = None
        for level, pattern in enumerate(self.SECTION_PATTERNS, start=1):
            if re.match(pattern, cleaned):
                section_level = level
                break

        # If no pattern match, use heuristics
        if section_level is None:
            # Must have some letters
            if not any(c.isalpha() for c in cleaned):
                return False, None

            # Check if it looks like a heading (short, capitalized)
            words = cleaned.split()
            if len(words) > 15:  # Too many words for a heading
                return False, None

            # Estimate level based on content
            if re.match(r'^\d+\s', cleaned):  # Starts with number
                section_level = 1
            elif re.match(r'^\d+\.\d+\s', cleaned):  # "6.3"
                section_level = 2
            elif re.match(r'^\d+\.\d+\.\d+\s', cleaned):  # "6.3.3"
                section_level = 3
            else:
                section_level = 2  # Default to level 2

        # Extract clean title (remove numbering if needed)
        cleaned_title = cleaned

        return True, {
            'cleaned_title': cleaned_title,
            'level': section_level,
            'has_number': bool(re.match(r'^\d+', cleaned)),
        }

    def _process_element(
        self,
        element: Element,
        current_section: Optional[str],
        section_hierarchy: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Process a single element and extract metadata."""
        if not element.text or not element.text.strip():
            return None

        element_type = self._get_element_type(element)
        page_numbers = self._extract_page_numbers(element)

        # Build section path from hierarchy
        section_path = " > ".join(section_hierarchy) if section_hierarchy else None

        # For figure/table captions, annotate in section path
        if isinstance(element, (FigureCaption, Table)):
            element_text = element.text.strip()
            if element_text.startswith('Figure') or element_text.startswith('Table'):
                # Don't update section title with figure/table caption
                pass

        return {
            "text": element.text.strip(),
            "type": element_type,
            "page_numbers": page_numbers,
            "section_title": current_section,
            "section_path": section_path,
            "metadata": element.metadata.to_dict() if hasattr(element, "metadata") else {},
        }

    def _get_element_type(self, element: Element) -> str:
        """Determine the type of element."""
        if isinstance(element, Title):
            return "heading"
        elif isinstance(element, Table):
            return "table"
        elif isinstance(element, FigureCaption):
            return "figure_caption"
        elif isinstance(element, ListItem):
            return "list_item"
        elif isinstance(element, NarrativeText):
            return "text"
        else:
            return "text"

    def _extract_page_numbers(self, element: Element) -> List[int]:
        """Extract page numbers from element metadata."""
        page_numbers = []

        if hasattr(element, "metadata") and element.metadata:
            if hasattr(element.metadata, "page_number"):
                page_num = element.metadata.page_number
                if page_num is not None:
                    page_numbers.append(page_num)

        return page_numbers if page_numbers else [1]

    def get_total_pages(self, file_path: str) -> int:
        """Get total number of pages in PDF."""
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.warning(f"Failed to get page count: {e}, using fallback")
            elements = self.parse_pdf(file_path)
            max_page = max(
                (max(elem["page_numbers"]) for elem in elements if elem["page_numbers"]),
                default=1,
            )
            return max_page

    @staticmethod
    def generate_doc_id(file_path: str, protocol: str, version: str) -> str:
        """Generate a unique document ID."""
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]

        doc_id = f"{protocol}_{version}_{file_hash}"
        return doc_id.replace(".", "_").replace(" ", "_")
