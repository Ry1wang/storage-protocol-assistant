"""PDF parsing utilities using Unstructured.io."""

from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib

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


class PDFParser:
    """Parse PDF documents and extract structured content."""

    def __init__(self):
        """Initialize PDF parser."""
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
        Parse a PDF file and extract structured elements.

        Args:
            file_path: Path to the PDF file
            strategy: Parsing strategy - 'fast' (text-only) or 'hi_res' (OCR + tables)

        Returns:
            List of parsed elements with metadata
        """
        logger.info(f"Parsing PDF: {file_path} with strategy: {strategy}")

        # Validate file exists
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Parse PDF using Unstructured
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

        # Process elements and extract metadata
        parsed_elements = []
        current_section = None
        section_hierarchy = []

        for element in elements:
            element_data = self._process_element(
                element, current_section, section_hierarchy
            )

            if element_data:
                parsed_elements.append(element_data)

                # Update section tracking for headings
                if isinstance(element, Title):
                    current_section = element.text
                    # Simple hierarchy: use text length as proxy for level
                    level = self._estimate_heading_level(element.text)

                    # Update hierarchy
                    if level == 1:
                        section_hierarchy = [element.text]
                    elif level == 2 and len(section_hierarchy) >= 1:
                        section_hierarchy = [section_hierarchy[0], element.text]
                    elif level == 3 and len(section_hierarchy) >= 2:
                        section_hierarchy = section_hierarchy[:2] + [element.text]
                    else:
                        section_hierarchy.append(element.text)

        logger.info(f"Extracted {len(parsed_elements)} elements from PDF")
        return parsed_elements

    def _process_element(
        self,
        element: Element,
        current_section: Optional[str],
        section_hierarchy: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single element and extract metadata.

        Args:
            element: Unstructured element
            current_section: Current section title
            section_hierarchy: List of parent section titles

        Returns:
            Processed element data or None if element should be skipped
        """
        # Skip empty elements
        if not element.text or not element.text.strip():
            return None

        # Determine element type
        element_type = self._get_element_type(element)

        # Extract page numbers
        page_numbers = self._extract_page_numbers(element)

        # Build section path
        section_path = " > ".join(section_hierarchy) if section_hierarchy else None

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
            # Try to get page number from metadata
            if hasattr(element.metadata, "page_number"):
                page_num = element.metadata.page_number
                if page_num is not None:
                    page_numbers.append(page_num)

        # Default to page 1 if no page info found
        return page_numbers if page_numbers else [1]

    def _estimate_heading_level(self, text: str) -> int:
        """
        Estimate heading level based on text characteristics.

        This is a simple heuristic:
        - Very short (< 30 chars) = Level 1 (Chapter/Major section)
        - Short (< 60 chars) = Level 2 (Section)
        - Longer = Level 3 (Subsection)
        """
        text_len = len(text)
        if text_len < 30:
            return 1
        elif text_len < 60:
            return 2
        else:
            return 3

    def get_total_pages(self, file_path: str) -> int:
        """
        Get total number of pages in PDF.

        Args:
            file_path: Path to PDF file

        Returns:
            Total page count
        """
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.warning(f"Failed to get page count: {e}, returning estimate")
            # Fallback: parse and find max page number
            elements = self.parse_pdf(file_path)
            max_page = max(
                (max(elem["page_numbers"]) for elem in elements if elem["page_numbers"]),
                default=1,
            )
            return max_page

    @staticmethod
    def generate_doc_id(file_path: str, protocol: str, version: str) -> str:
        """
        Generate a unique document ID.

        Args:
            file_path: Path to the PDF file
            protocol: Protocol name (e.g., "eMMC")
            version: Protocol version (e.g., "5.1")

        Returns:
            Unique document ID
        """
        # Create ID from protocol, version, and file hash
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]

        doc_id = f"{protocol}_{version}_{file_hash}"
        return doc_id.replace(".", "_").replace(" ", "_")
