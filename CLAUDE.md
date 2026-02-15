# Storage Protocol Assistant - AI Development Guide

This document provides context for AI assistants (Claude, etc.) working on this project.

## Project Overview

**Type:** Agentic RAG System for Storage Protocol Specifications
**Status:** Initial Setup Complete (MVP Phase)
**Architecture:** Streamlit + Qdrant + SQLite + DeepSeek
**Deployment:** Docker Compose

## Project Goals

Build a high-precision Q&A system for storage protocol specifications (eMMC, UFS, etc.) with:
- Zero-tolerance for hallucinations
- Complete answer traceability with citations
- Multi-agent architecture for query processing
- Hybrid retrieval (vector + keyword search)

## Development Phases

### Phase 1: MVP (Week 1) - **CURRENT PHASE**
- [x] Initial project setup
- [x] Docker configuration
- [x] Database clients (Qdrant, SQLite)
- [x] Basic Streamlit UI
- [ ] Document ingestion pipeline
- [ ] Three-agent pipeline (Router, Retriever, Generator)
- [ ] Citation tracking system

### Phase 2: Enhancements (Week 2-3)
- [ ] React UI migration
- [ ] LangGraph orchestration
- [ ] Advanced PDF parsing (hybrid approach)
- [ ] Multi-document comparison

### Phase 3: Production (Week 4+)
- [ ] PostgreSQL migration
- [ ] Monitoring and logging
- [ ] Performance optimization
- [ ] User feedback system

## Project Structure

```
storage-protocol-assistant/
├── src/
│   ├── agents/              # Agentic components (TO BE IMPLEMENTED)
│   │   ├── query_router.py      # Query classification and routing
│   │   ├── retriever.py         # Hybrid retrieval agent
│   │   └── answer_generator.py  # Citation-backed answer generation
│   ├── ingestion/           # Document processing (TO BE IMPLEMENTED)
│   │   ├── pdf_parser.py        # PDF parsing with Unstructured
│   │   ├── chunker.py           # Semantic chunking
│   │   └── ingest_spec.py       # Main ingestion script
│   ├── retrieval/           # Search components (TO BE IMPLEMENTED)
│   │   ├── vector_search.py     # Qdrant vector search
│   │   ├── keyword_search.py    # BM25 keyword search
│   │   └── hybrid_search.py     # Hybrid retrieval pipeline
│   ├── models/              # Data models (✅ COMPLETE)
│   │   └── schemas.py
│   ├── utils/               # Utilities (✅ COMPLETE)
│   │   ├── config.py
│   │   └── logger.py
│   └── database/            # Database clients (✅ COMPLETE)
│       ├── qdrant_client.py
│       └── sqlite_client.py
├── app.py                   # Main Streamlit app (✅ SKELETON)
├── docker-compose.yml       # Docker setup (✅ COMPLETE)
├── Dockerfile               # Application container (✅ COMPLETE)
└── requirements.txt         # Python dependencies (✅ COMPLETE)
```

## Technology Stack

### Core
- **Python 3.11+**: Main language
- **Streamlit**: MVP UI framework
- **DeepSeek API**: LLM for reasoning (deepseek-reasoner) and routing (deepseek-chat)

### Data Storage
- **Qdrant**: Vector database for embeddings
- **SQLite**: Metadata and audit logs (MVP)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2

### Document Processing
- **Unstructured.io**: PDF parsing (basic mode for MVP)
- **Custom chunking**: Semantic chunking with structure preservation

## Key Design Principles

1. **Accuracy First**: Multi-stage verification and citation tracking
2. **No Hallucinations**: Every claim must have a source citation
3. **Transparency**: Full provenance tracking from query to answer
4. **Docker-Native**: Containerized for easy deployment
5. **Iterative Development**: Start simple (MVP), enhance based on feedback

## Development Guidelines

### For AI Assistants

When working on this project:

1. **Follow the MVP approach**: Implement simple, working solutions first
2. **Maintain citation tracking**: Every answer must include source references
3. **Use structured logging**: Use the logger from `src/utils/logger.py`
4. **Follow the architecture**: See `docs/PRD_V2.md` for detailed architecture
5. **Test incrementally**: Write tests as you implement features

### Code Style

- **Formatting**: Use `black` for code formatting
- **Linting**: Follow `flake8` rules
- **Type hints**: Use type annotations where appropriate
- **Docstrings**: Use Google-style docstrings

### Testing

```bash
# Run tests
make test

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Next Steps (Priority Order)

1. ✅ **~~Implement PDF Ingestion Pipeline~~** (`src/ingestion/`) - **COMPLETE**
   - ✅ PDF parser using Unstructured.io
   - ✅ Semantic chunking with metadata preservation
   - ✅ Embedding generation and storage
   - ✅ CLI script for ingesting specs

2. **Implement Retrieval Components** (`src/retrieval/`) - **NEXT**
   - Vector search wrapper for Qdrant (basic version exists, enhance with filters)
   - BM25 keyword search implementation
   - Hybrid search combining both approaches
   - Reranking and score fusion

3. **Implement Agent Pipeline** (`src/agents/`)
   - Query Router Agent (classify and route queries)
   - Retriever Agent (orchestrate hybrid search)
   - Answer Generator Agent (create citation-backed answers)

4. **Integrate with Streamlit UI**
   - Connect agents to `app.py`
   - Display agent reasoning steps
   - Show citations with page numbers
   - Add document upload interface

5. **Testing & Validation**
   - Create test query dataset
   - Measure citation accuracy
   - Test with sample protocol specs
   - End-to-end integration tests

## Common Tasks

### Start Development Environment

```bash
# Copy environment template
cp .env.example .env
# Edit .env and add DEEPSEEK_API_KEY

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app
```

### Ingest a Document

```bash
# Using Makefile (recommended)
make ingest FILE=/app/specs/emmc_5.1.pdf PROTOCOL=eMMC VERSION=5.1

# Or using CLI directly
docker-compose exec app python -m src.ingestion.ingest_spec ingest \
  --file /app/specs/emmc_5.1.pdf \
  --protocol eMMC \
  --version 5.1 \
  --title "eMMC Specification v5.1" \
  --strategy fast

# List all documents
make list
```

### Access Services

- **Streamlit UI**: http://localhost:8501
- **Qdrant Dashboard**: http://localhost:6333/dashboard

## Configuration

Key settings in `.env`:

- `DEEPSEEK_API_KEY`: Your DeepSeek API key (required)
- `QDRANT_URL`: Qdrant connection URL (default: http://qdrant:6333)
- `TOP_K`: Number of chunks to retrieve (default: 10)
- `CHUNK_SIZE`: Size of text chunks in tokens (default: 500)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 50)

## Debugging Tips

1. **Check service health**:
   ```bash
   docker-compose ps
   ```

2. **View application logs**:
   ```bash
   docker-compose logs -f app
   ```

3. **Check Qdrant collections**:
   - Visit http://localhost:6333/dashboard
   - Or use: `docker-compose exec app python -c "from src.database.qdrant_client import QdrantVectorStore; print(QdrantVectorStore().client.get_collections())"`

4. **Check SQLite database**:
   ```bash
   sqlite3 data/metadata.db "SELECT * FROM documents;"
   ```

## Resources

- **PRD**: See `docs/PRD_V2.md` for complete architecture
- **API Docs**: DeepSeek API - https://platform.deepseek.com/api-docs
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **Streamlit Docs**: https://docs.streamlit.io/

## Notes for Future Development

- **Vector DB**: Qdrant chosen for simplicity and hybrid search support
- **LLM**: DeepSeek-R1 for reasoning, DeepSeek-V3 for fast routing
- **Migration Path**: Plan to migrate to React UI and LangGraph post-MVP
- **Table Extraction**: Will add Camelot for complex tables in production
- **Diagram Analysis**: Will add DeepSeek-VL2 for diagram understanding later

## Current Status Summary

✅ **Complete**:
- Project structure and configuration
- Docker setup (compose + Dockerfile)
- Database clients (Qdrant + SQLite)
- Data models and schemas
- Logging and configuration utilities
- Basic Streamlit UI shell
- **PDF ingestion pipeline** (pdf_parser.py, chunker.py, ingest_spec.py)
- **Semantic chunking** with metadata preservation
- **CLI interface** for document ingestion
- **Makefile commands** for easy ingestion
- **Unit tests** for ingestion components
- **Documentation** and examples

🚧 **In Progress**:
- None (ready for next phase)

❌ **Not Started**:
- Retrieval components (vector + keyword search)
- Agent implementations (Router, Retriever, Generator)
- Full UI integration
- Production testing suite

---

**Last Updated**: 2026-02-14
**Phase**: MVP - Ingestion Pipeline Complete ✅
