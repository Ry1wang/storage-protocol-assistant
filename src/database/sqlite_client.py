"""SQLite database client for metadata storage."""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from ..utils.config import settings
from ..utils.logger import get_logger
from ..models.schemas import DocumentMetadata, QueryAudit

logger = get_logger(__name__)


class SQLiteClient:
    """Manages interactions with SQLite metadata database."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize SQLite client.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or settings.database_path

        # Ensure database directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                protocol TEXT NOT NULL,
                version TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                total_pages INTEGER NOT NULL,
                total_chunks INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Query audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_audit (
                query_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                query_text TEXT NOT NULL,
                retrieved_chunks TEXT NOT NULL,
                answer TEXT NOT NULL,
                citations TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                feedback_rating INTEGER,
                processing_time_ms REAL
            )
        """)

        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def add_document(self, doc: DocumentMetadata) -> None:
        """
        Add document metadata.

        Args:
            doc: Document metadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO documents
            (doc_id, title, protocol, version, file_path, uploaded_at,
             total_pages, total_chunks, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc.doc_id,
            doc.title,
            doc.protocol,
            doc.version,
            doc.file_path,
            doc.uploaded_at.isoformat(),
            doc.total_pages,
            doc.total_chunks,
            1 if doc.is_active else 0,
        ))

        conn.commit()
        conn.close()
        logger.info(f"Added document: {doc.doc_id}")

    def get_document(self, doc_id: str) -> Optional[DocumentMetadata]:
        """
        Get document metadata.

        Args:
            doc_id: Document ID

        Returns:
            Document metadata if found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return DocumentMetadata(
                doc_id=row["doc_id"],
                title=row["title"],
                protocol=row["protocol"],
                version=row["version"],
                file_path=row["file_path"],
                uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
                total_pages=row["total_pages"],
                total_chunks=row["total_chunks"],
                is_active=bool(row["is_active"]),
            )
        return None

    def list_documents(self, active_only: bool = True) -> List[DocumentMetadata]:
        """
        List all documents.

        Args:
            active_only: Only return active documents

        Returns:
            List of document metadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM documents"
        if active_only:
            query += " WHERE is_active = 1"

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        return [
            DocumentMetadata(
                doc_id=row["doc_id"],
                title=row["title"],
                protocol=row["protocol"],
                version=row["version"],
                file_path=row["file_path"],
                uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
                total_pages=row["total_pages"],
                total_chunks=row["total_chunks"],
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    def add_query_audit(self, audit: QueryAudit) -> None:
        """
        Add query audit record.

        Args:
            audit: Query audit record
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO query_audit
            (query_id, timestamp, user_id, query_text, retrieved_chunks,
             answer, citations, confidence_score, feedback_rating, processing_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit.query_id,
            audit.timestamp.isoformat(),
            audit.user_id,
            audit.query_text,
            json.dumps(audit.retrieved_chunks),
            audit.answer,
            json.dumps(audit.citations),
            audit.confidence_score,
            audit.feedback_rating,
            audit.processing_time_ms,
        ))

        conn.commit()
        conn.close()
        logger.info(f"Added query audit: {audit.query_id}")

    def get_query_history(self, limit: int = 100) -> List[QueryAudit]:
        """
        Get query history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of query audit records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM query_audit
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            QueryAudit(
                query_id=row["query_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                user_id=row["user_id"],
                query_text=row["query_text"],
                retrieved_chunks=json.loads(row["retrieved_chunks"]),
                answer=row["answer"],
                citations=json.loads(row["citations"]),
                confidence_score=row["confidence_score"],
                feedback_rating=row["feedback_rating"],
                processing_time_ms=row["processing_time_ms"],
            )
            for row in rows
        ]
