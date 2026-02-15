"""Text chunking utilities for semantic document splitting."""

from typing import List, Dict, Any, Optional
import uuid
import tiktoken

from ..models.schemas import DocumentChunk, ChunkMetadata
from ..utils.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SemanticChunker:
    """Chunk documents semantically while preserving structure."""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize semantic chunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            encoding_name: Tiktoken encoding name
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk_elements(
        self,
        elements: List[Dict[str, Any]],
        doc_id: str,
    ) -> List[DocumentChunk]:
        """
        Chunk parsed PDF elements into semantic chunks.

        Args:
            elements: List of parsed PDF elements
            doc_id: Document ID

        Returns:
            List of document chunks with metadata
        """
        logger.info(f"Chunking {len(elements)} elements for doc {doc_id}")

        chunks = []
        current_chunk_text = []
        current_chunk_tokens = 0
        current_metadata = {
            "page_numbers": set(),
            "section_title": None,
            "section_path": None,
            "types": set(),
        }

        for element in elements:
            element_text = element["text"]
            element_tokens = self._count_tokens(element_text)
            element_type = element["type"]

            # Handle large tables separately (don't split them)
            if element_type == "table" and element_tokens > self.chunk_size:
                # Flush current chunk if exists
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            doc_id,
                            current_chunk_text,
                            current_metadata,
                        )
                    )
                    current_chunk_text = []
                    current_chunk_tokens = 0
                    current_metadata = {
                        "page_numbers": set(),
                        "section_title": None,
                        "section_path": None,
                        "types": set(),
                    }

                # Add table as its own chunk
                chunks.append(
                    self._create_chunk(
                        doc_id,
                        [element_text],
                        {
                            "page_numbers": set(element["page_numbers"]),
                            "section_title": element["section_title"],
                            "section_path": element["section_path"],
                            "types": {"table"},
                        },
                        chunk_type="table",
                    )
                )
                continue

            # Check if adding this element would exceed chunk size
            if current_chunk_tokens + element_tokens > self.chunk_size:
                # If current chunk has content, save it
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            doc_id,
                            current_chunk_text,
                            current_metadata,
                        )
                    )

                    # Start new chunk with overlap
                    overlap_text = self._get_overlap_text(
                        current_chunk_text,
                        current_chunk_tokens,
                    )
                    current_chunk_text = overlap_text
                    current_chunk_tokens = self._count_tokens(" ".join(overlap_text))
                    current_metadata = {
                        "page_numbers": set(),
                        "section_title": None,
                        "section_path": None,
                        "types": set(),
                    }

            # Add element to current chunk
            current_chunk_text.append(element_text)
            current_chunk_tokens += element_tokens
            current_metadata["page_numbers"].update(element["page_numbers"])
            current_metadata["types"].add(element_type)

            # Update section metadata (use most recent)
            if element["section_title"]:
                current_metadata["section_title"] = element["section_title"]
            if element["section_path"]:
                current_metadata["section_path"] = element["section_path"]

        # Add final chunk
        if current_chunk_text:
            chunks.append(
                self._create_chunk(
                    doc_id,
                    current_chunk_text,
                    current_metadata,
                )
            )

        logger.info(f"Created {len(chunks)} chunks for doc {doc_id}")
        return chunks

    def _create_chunk(
        self,
        doc_id: str,
        text_parts: List[str],
        metadata: Dict[str, Any],
        chunk_type: str = "text",
    ) -> DocumentChunk:
        """
        Create a document chunk with metadata.

        Args:
            doc_id: Document ID
            text_parts: List of text segments
            metadata: Chunk metadata
            chunk_type: Type of chunk (text, table, etc.)

        Returns:
            DocumentChunk instance
        """
        # Combine text parts
        text = "\n\n".join(text_parts)

        # Generate unique chunk ID
        chunk_id = str(uuid.uuid4())

        # Sort page numbers
        page_numbers = sorted(list(metadata["page_numbers"]))

        # Create metadata
        chunk_metadata = ChunkMetadata(
            doc_id=doc_id,
            chunk_id=chunk_id,
            page_numbers=page_numbers,
            section_title=metadata.get("section_title"),
            section_path=metadata.get("section_path"),
            chunk_type=chunk_type,
        )

        return DocumentChunk(
            text=text,
            metadata=chunk_metadata,
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def _get_overlap_text(
        self,
        text_parts: List[str],
        total_tokens: int,
    ) -> List[str]:
        """
        Get text for overlap with previous chunk.

        Args:
            text_parts: List of text segments in current chunk
            total_tokens: Total tokens in current chunk

        Returns:
            Text parts for overlap
        """
        if not text_parts or total_tokens <= self.chunk_overlap:
            return []

        # Work backwards to get overlap
        overlap_parts = []
        overlap_tokens = 0

        for part in reversed(text_parts):
            part_tokens = self._count_tokens(part)
            if overlap_tokens + part_tokens <= self.chunk_overlap:
                overlap_parts.insert(0, part)
                overlap_tokens += part_tokens
            else:
                break

        return overlap_parts


class SimpleChunker:
    """Simple fixed-size chunker for basic use cases."""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize simple chunker.

        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            encoding_name: Tiktoken encoding name
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        page_number: int = 1,
        section_title: Optional[str] = None,
    ) -> List[DocumentChunk]:
        """
        Chunk text into fixed-size chunks.

        Args:
            text: Input text
            doc_id: Document ID
            page_number: Page number
            section_title: Section title

        Returns:
            List of document chunks
        """
        # Tokenize text
        tokens = self.encoding.encode(text)

        chunks = []
        start = 0

        while start < len(tokens):
            # Get chunk tokens
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Create chunk
            chunk_id = str(uuid.uuid4())
            chunk_metadata = ChunkMetadata(
                doc_id=doc_id,
                chunk_id=chunk_id,
                page_numbers=[page_number],
                section_title=section_title,
            )

            chunks.append(
                DocumentChunk(
                    text=chunk_text,
                    metadata=chunk_metadata,
                )
            )

            # Move to next chunk with overlap
            start = end - self.chunk_overlap

        return chunks
