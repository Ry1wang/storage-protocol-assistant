# Storage Protocol Assistant - AI Development Guide

This document provides context for AI assistants working on this project. For setup, usage, and deployment details, see [README.md](README.md).

## Project Overview

Agentic RAG system for storage protocol specifications (eMMC, UFS, etc.). Zero-tolerance for hallucinations, citation-backed answers, hybrid retrieval.

**Stack:** Python 3.11 / Streamlit / Qdrant / SQLite / DeepSeek API / Docker Compose

## Development Guidelines

- **MVP-first**: Simple, working solutions before optimization
- **Citation tracking**: Every answer must include source references
- **Structured logging**: Use `src/utils/logger.py`
- **Architecture reference**: See `docs/PRD_V2.md`
- **Code style**: `black` formatting, `flake8` linting, Google-style docstrings, type hints

## Key Architecture

### Three-Agent Pipeline (`src/agents/`)
1. **QueryRouter** (`query_router.py`) — Classifies queries into 6 types (factual, definition, comparison, specification, procedural, troubleshooting), selects retrieval strategy (vector/hybrid), sets search params (top_k, min_score)
2. **RetrieverAgent** (`retriever.py`) — Orchestrates vector/hybrid search, section-clustering rerank, context assembly with `[N]` numbered references
3. **AnswerGenerator** (`answer_generator.py`) — Produces citation-backed answers, extracts `[N]` citation references, calculates confidence scores

### Retrieval (`src/retrieval/`)
- **Vector search**: Qdrant with sentence-transformers/all-MiniLM-L6-v2 (384-dim)
- **Keyword search**: BM25 via rank_bm25
- **Hybrid search**: Reciprocal Rank Fusion (RRF) merging both sources

### Ingestion (`src/ingestion/`)
- **PDF parsing**: Unstructured.io (basic mode)
- **Chunking**: Section-aware chunker with configurable boundary levels, min/max chunk sizes
- **Chunker factory**: Selects between TOC-based and section-aware chunkers

### Data Layer
- **Qdrant** (`src/database/qdrant_client.py`) — Vector storage, search, scroll pagination, doc_id filtering
- **SQLite** (`src/database/sqlite_client.py`) — Document metadata, audit logs
- **Schemas** (`src/models/schemas.py`) — DocumentMetadata, DocumentChunk, ChunkMetadata

## Completed Development

### Phase 1: MVP (Complete)
- [x] Docker setup and containerization
- [x] Database clients (Qdrant + SQLite)
- [x] PDF ingestion pipeline with section-aware chunking
- [x] CLI for document ingestion (`python -m src.ingestion.ingest_spec`)
- [x] Vector search with metadata filtering
- [x] BM25 keyword search with rank_bm25
- [x] Hybrid search with RRF fusion
- [x] Three-agent pipeline (Router, Retriever, Generator)
- [x] Streamlit UI with document upload, strategy selector, citation display
- [x] eMMC 5.1 spec ingested (821 chunks, 95.2% section title accuracy)

### Testing Suite (Complete)
126 tests, all passing, fully mocked (no Docker/Qdrant/DeepSeek needed for CI).

| File | Category | Tests | Covers |
|------|----------|-------|--------|
| `test_config.py` | Unit | 2 | Settings validation |
| `test_ingestion.py` | Unit | 11 | PDF parser, chunker (requires `unstructured`) |
| `test_retrieval.py` | Unit | 2 | BM25, RRF, reranking |
| `test_blackbox_ingestion.py` | Black-box | 10 | Document ingest/delete/list lifecycle |
| `test_blackbox_retrieval.py` | Black-box | 12 | Search interface, strategy routing, context assembly |
| `test_blackbox_pipeline.py` | Black-box | 9 | End-to-end RAG pipeline orchestration |
| `test_blackbox_ui.py` | Black-box | 8 | Streamlit `process_query()` logic |
| `test_whitebox_query_router.py` | White-box | 12 | Strategy mapping, search params, route integration |
| `test_whitebox_answer_generator.py` | White-box | 15 | Citation extraction, confidence calc, instructions |
| `test_whitebox_chunker.py` | White-box | 10 | Section boundary detection, chunking behavior |
| `test_whitebox_qdrant.py` | White-box | 10 | Collection management, CRUD, pagination, filtering |
| `test_rag_accuracy.py` | Accuracy | 24 | All 6 query types + cross-cutting accuracy checks |
| `conftest.py` | Fixtures | — | 21 sample chunks, mock stores, shared helpers |

```bash
# Run all tests (pytest.ini has --cov flags; override if pytest-cov not installed)
python -m pytest tests/ -v --override-ini="addopts=-v --strict-markers --tb=short"

# By category
python -m pytest tests/test_blackbox_*.py -v --override-ini="addopts="
python -m pytest tests/test_whitebox_*.py -v --override-ini="addopts="
python -m pytest tests/test_rag_accuracy.py -v --override-ini="addopts="
```

## Remaining Requirements

### Phase 1 Remaining
- [ ] Citation tracking system (end-to-end provenance from query to source page)

### Phase 2: Enhancements
- [ ] React UI migration (replace Streamlit)
- [ ] LangGraph orchestration (replace manual agent wiring)
- [ ] Advanced PDF parsing (hybrid approach with Camelot for tables)
- [ ] Multi-document comparison (cross-protocol queries)
- [ ] LLM-based re-ranking
- [ ] Query expansion
- [ ] Better embedding model (mpnet or bge-large)

### Phase 3: Production
- [ ] PostgreSQL migration (replace SQLite)
- [ ] Monitoring and analytics dashboard
- [ ] Performance optimization (caching, batching)
- [ ] User feedback system
- [ ] Diagram analysis (DeepSeek-VL2)
- [ ] Scalability improvements

## Testing Notes

- `test_ingestion.py` requires `unstructured` library (Docker only). The equivalent functionality is covered by `test_blackbox_ingestion.py` with mocked deps for local runs.
- 10 warnings are expected: 1x Pydantic V2 deprecation, 9x `datetime.utcnow()` deprecation. Non-blocking.
- All accuracy tests use mocked DeepSeek responses but exercise real routing logic (strategy selection, search param mapping).

---

**Last Updated**: 2026-02-16
**Phase**: MVP Complete, Testing Complete
