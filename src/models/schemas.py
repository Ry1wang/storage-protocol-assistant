"""Data models and schemas for the RAG system."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class QueryType(str, Enum):
    """Types of user queries."""
    SIMPLE = "simple"
    COMPARISON = "comparison"
    COMPLEX = "complex"
    TROUBLESHOOTING = "troubleshooting"


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    doc_id: str
    chunk_id: str
    page_numbers: List[int]
    section_title: Optional[str] = None
    section_path: Optional[str] = None
    chunk_type: str = "text"  # text, table, figure_caption
    parent_chunk_id: Optional[str] = None


class DocumentChunk(BaseModel):
    """A chunk of document text with metadata."""
    text: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None


class Citation(BaseModel):
    """A citation referencing a source document."""
    text: str = Field(..., description="The exact quoted text")
    source: str = Field(..., description="Source document name")
    section: Optional[str] = Field(None, description="Section title/path")
    page: int = Field(..., description="Page number")
    chunk_id: str = Field(..., description="Reference to chunk")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class QueryRoute(BaseModel):
    """Result of query routing."""
    query_type: QueryType
    key_terms: List[str]
    protocols: List[str]
    sub_queries: Optional[List[str]] = None


class RetrievalResult(BaseModel):
    """Result from hybrid retrieval."""
    chunks: List[DocumentChunk]
    scores: List[float]
    retrieval_strategy: str


class Answer(BaseModel):
    """Generated answer with citations."""
    query_id: str
    query: str
    answer: str
    citations: List[Citation]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning_steps: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DocumentMetadata(BaseModel):
    """Metadata for a protocol specification document."""
    doc_id: str
    title: str
    protocol: str  # e.g., "eMMC", "UFS"
    version: str  # e.g., "5.1"
    file_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    total_pages: int
    total_chunks: int
    is_active: bool = True


class QueryAudit(BaseModel):
    """Audit record for a query."""
    query_id: str
    timestamp: datetime
    user_id: Optional[str] = None
    query_text: str
    retrieved_chunks: List[str]  # chunk_ids
    answer: str
    citations: List[Dict[str, Any]]
    confidence_score: float
    feedback_rating: Optional[int] = None
    processing_time_ms: Optional[float] = None
