# Agentic RAG System Architecture

## Storage Protocol Specification Q&A System

---

## Executive Summary

This architecture designs a **high-precision Agentic RAG system** for storage protocol specifications (eMMC, UFS, etc.) with strict adherence to source documents, zero-tolerance for hallucinations, and complete answer traceability.

**Development Approach:** Phased implementation with 1-week MVP using AI-assisted development

**Key Design Principles:**

- **Accuracy First**: Multi-stage verification and citation tracking
- **Context Awareness**: Agentic query decomposition and multi-hop reasoning
- **Transparency**: Full provenance tracking from query to answer
- **Docker-Native**: Containerized microservices for easy deployment
- **Rapid Development**: AI-assisted coding with Claude/Gemini for 1-week MVP

**Timeline:**

- **Week 1:** Working MVP (Streamlit + simplified agents)
- **Week 2-3:** Production enhancements (React UI, advanced features)
- **Week 4+:** Scaling and optimization

**This document presents BOTH the MVP architecture and the full production vision.**

---

## Architecture Versions

This document presents two complementary architectures:

### **Version 1: 1-Week MVP (Simplified)**

- **Frontend:** Streamlit (rapid prototyping)
- **Orchestration:** Simple Python functions with 3 agents
- **Database:** SQLite for metadata, Qdrant for vectors
- **PDF Parsing:** Unstructured.io (basic mode)
- **Goal:** Prove concept, gather feedback

### **Version 2: Production (Full-Featured)**

- **Frontend:** React.js with advanced document interaction
- **Orchestration:** LangGraph for complex agentic workflows
- **Database:** PostgreSQL for metadata, Qdrant for vectors
- **PDF Parsing:** Hybrid (Unstructured + Camelot + Claude Vision)
- **Goal:** Production-grade system with all features

**Recommendation:** Start with MVP, migrate to production architecture as needs evolve.

---

## System Architecture Overview (MVP Version)

```
┌──────────────────────────────────────────────────────────────┐
│                    STREAMLIT UI                              │
│  - Chat interface with agent step visualization             │
│  - Citation display (text + page numbers)                   │
│  - Basic PDF viewer (streamlit-pdf-viewer)                  │
│  - Protocol selector sidebar                                │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│            SIMPLIFIED AGENTIC PIPELINE                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent 1: Query Router (DeepSeek-V3)                     │ │
│  │  - Classify query type (simple/comparison/complex)     │ │
│  │  - Extract key terms and protocols                     │ │
│  │  - Route to appropriate retrieval strategy             │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│  ┌──────────────────────▼─────────────────────────────────┐ │
│  │  Agent 2: Hybrid Retriever                             │ │
│  │  - Vector search (Qdrant, top-K=10)                    │ │
│  │  - Simple BM25 keyword boost                           │ │
│  │  - Re-rank by relevance + page proximity               │ │
│  └──────────────────────┬─────────────────────────────────┘ │
│  ┌──────────────────────▼─────────────────────────────────┐ │
│  │  Agent 3: Answer Generator (DeepSeek-R1)                │ │
│  │  - Strict citation-aware prompt                        │ │
│  │  - Extract exact quotes with page numbers              │ │
│  │  - Confidence scoring                                  │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                   DATA LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Qdrant       │  │ SQLite       │  │ Local Files      │  │
│  │ (Docker)     │  │ (metadata)   │  │ (PDFs, chunks)   │  │
│  │              │  │              │  │                  │  │
│  │ - Vectors    │  │ - Citations  │  │ - Raw specs      │  │
│  │ - HNSW index │  │ - Audit log  │  │ - JSON chunks    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│        DOCUMENT INGESTION (Run once per spec)                │
│  PDF → Unstructured → Chunk → Embed → Store in Qdrant       │
└──────────────────────────────────────────────────────────────┘
```

## System Architecture Overview (Production Version)

**Note:** This is the full-featured architecture to implement after MVP validation.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  Web UI      │  │  API Gateway │  │  Admin Dashboard        │  │
│  │  (Streamlit) │  │  (FastAPI)   │  │  (Doc Management)       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬──────────────┘  │
└─────────┼──────────────────┼───────────────────────┼─────────────────┘
          │                  │                       │
          └──────────────────┼───────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                              │
│                             │                                         │
│  ┌─────────────────────────▼──────────────────────────┐             │
│  │         AGENTIC ORCHESTRATOR (LangGraph)           │             │
│  │  ┌──────────────────────────────────────────────┐  │             │
│  │  │  Query Understanding & Decomposition Agent   │  │             │
│  │  └───────────────────┬──────────────────────────┘  │             │
│  │  ┌──────────────────▼───────────────────────────┐  │             │
│  │  │  Retrieval Planner Agent                     │  │             │
│  │  │  (Multi-hop, Cross-doc reasoning)            │  │             │
│  │  └───────────────────┬──────────────────────────┘  │             │
│  │  ┌──────────────────▼───────────────────────────┐  │             │
│  │  │  Answer Synthesis & Verification Agent       │  │             │
│  │  └──────────────────────────────────────────────┘  │             │
│  └─────────────────────────────────────────────────────┘             │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────────┐
│                      RETRIEVAL LAYER                                 │
│                             │                                         │
│  ┌─────────────────────────▼──────────────────────┐                 │
│  │         HYBRID RETRIEVAL PIPELINE               │                 │
│  │  ┌─────────────────────────────────────────┐   │                 │
│  │  │  Semantic Search (Vector DB)            │   │                 │
│  │  │  - Dense embeddings (all-MiniLM-L6-v2)  │   │                 │
│  │  │  - Contextual chunk embeddings          │   │                 │
│  │  └─────────────────┬───────────────────────┘   │                 │
│  │  ┌─────────────────▼───────────────────────┐   │                 │
│  │  │  Keyword Search (BM25)                  │   │                 │
│  │  │  - Technical term matching              │   │                 │
│  │  │  - Specification section lookup         │   │                 │
│  │  └─────────────────┬───────────────────────┘   │                 │
│  │  ┌─────────────────▼───────────────────────┐   │                 │
│  │  │  Re-ranker (Cross-Encoder)              │   │                 │
│  │  │  - Context-aware relevance scoring      │   │                 │
│  │  └─────────────────────────────────────────┘   │                 │
│  └─────────────────────────────────────────────────┘                 │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────────┐
│                       STORAGE LAYER                                  │
│                             │                                         │
│  ┌──────────────────┐  ┌───▼──────────────┐  ┌──────────────────┐  │
│  │  Vector Store    │  │  Document Store  │  │  Metadata Store  │  │
│  │  (Qdrant)        │  │  (PostgreSQL)    │  │  (PostgreSQL)    │  │
│  │                  │  │                  │  │                  │  │
│  │  - Embeddings    │  │  - Raw specs     │  │  - Lineage       │  │
│  │  - HNSW index    │  │  - Chunks        │  │  - Citations     │  │
│  │                  │  │  - Versions      │  │  - Audit logs    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE                                │
│  ┌────────────┐  ┌─────────────┐  ┌────────────┐  ┌──────────────┐ │
│  │ PDF Parser │→ │ Chunking    │→ │ Embedding  │→ │ Indexing     │ │
│  │ (PyMuPDF)  │  │ (Semantic)  │  │ Generation │  │ & Storage    │ │
│  └────────────┘  └─────────────┘  └────────────┘  └──────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Technology Selection & Trade-offs

### Frontend: Streamlit (MVP) → React.js (Production)

**MVP Choice: Streamlit**

- ✅ Build chat UI in 4 hours vs 2 days
- ✅ Python-native (same stack as backend)
- ✅ Built-in widgets for quick prototyping
- ❌ Limited document interaction features
- ❌ Poor state management for complex workflows

**Production Upgrade: React.js**

- ✅ Rich PDF viewer with citation highlighting
- ✅ Real-time agent progress visualization
- ✅ Side-by-side spec comparison
- ✅ Better for production UX
- ⏱️ Requires 3-4 weeks development

**Decision:** Use Streamlit for Week 1 MVP, migrate to React when validated.

---

### Orchestration: Simple Functions (MVP) → LangGraph (Production)

**MVP Choice: Simple Python Functions**

- ✅ Zero framework learning curve
- ✅ Easy to debug and modify
- ✅ Sufficient for 3-agent pipeline
- ❌ Manual state management
- ❌ Hard to add complex loops

**Production Upgrade: LangGraph**

- ✅ Explicit state management for agentic workflows
- ✅ Built-in cycles for iterative refinement
- ✅ Full execution trace for debugging
- ✅ Ideal for multi-hop reasoning
- ⏱️ 1-2 days learning curve

**Why NOT LangChain:** Too rigid for agentic workflows (sequential only)
**Why NOT LlamaIndex:** Optimized for indexing, not orchestration

**Decision:** Simple functions for MVP, LangGraph when complexity increases.

---

### Vector Database: Qdrant ✅

**Why Qdrant:**

- ✅ Single Docker container (vs Milvus's 8 containers)
- ✅ Native hybrid search (dense + sparse vectors)
- ✅ Advanced filtering (critical for spec metadata)
- ✅ Lightweight (<2GB RAM for small datasets)
- ✅ Production-ready with snapshots/backups

**Why NOT Milvus:** Over-engineered for small team, requires Kubernetes
**Why NOT ChromaDB:** Limited filtering, no hybrid search, not production-ready

**Decision:** Qdrant for both MVP and production.

---

### PDF Parsing: Unstructured (MVP) → Hybrid Approach (Production)

**Critical Issue:** Storage protocol specs have complex layouts:

- Multi-column text with tightly coupled diagrams
- Register bit-field tables with merged cells
- Timing diagrams with annotations
- Cross-references between sections

**MVP Choice: Unstructured.io (Basic Mode)**

```python
from unstructured.partition.pdf import partition_pdf

elements = partition_pdf(
    "spec.pdf",
    strategy="fast"  # Basic text extraction
)
```

- ✅ Better than PyMuPDF for layout awareness
- ✅ Extracts tables and maintains hierarchy
- ⏱️ Good enough for Week 1 MVP
- ❌ May miss complex diagram relationships

**Production Upgrade: Hybrid Approach**

```python
# 1. Layout-aware parsing
elements = partition_pdf("spec.pdf", strategy="hi_res")

# 2. Enhanced table extraction
tables = camelot.read_pdf("spec.pdf", flavor="lattice")

# 3. Diagram understanding with DeepSeek-VL2
diagram_analysis = deepseek.messages.create(
    model="deepseek-vl2",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"path": "timing_diagram.png"}},
            {"type": "text", "text": "Explain this timing diagram"}
        ]
    }]
)
```

**Components:**

- **Unstructured.io:** Layout detection, structure preservation
- **Camelot:** Complex table extraction
- **DeepSeek-VL2:** Diagram/figure analysis
- **Relationship Mapping:** Link tables, diagrams, and text

**Why NOT PyMuPDF alone:** Loses layout structure critical for spec accuracy

**Decision:** Basic Unstructured for MVP, full hybrid for production.

---

### Database: SQLite (MVP) → PostgreSQL (Production)

**MVP:** SQLite for simplicity (no setup needed)
**Production:** PostgreSQL for JSONB queries, better concurrency

---

## Core Components

### 1. **Agentic Orchestrator** (LangGraph)

The brain of the system - manages multi-step reasoning workflows.

**Agents:**

#### 1.1 Query Understanding Agent

- **Purpose**: Decomposes complex queries into sub-questions
- **Capabilities**:
  - Intent classification (definitional, procedural, comparative, troubleshooting)
  - Technical term extraction
  - Query expansion (e.g., "UFS initialization" → includes "device descriptor", "flags", "boot sequence")
  - Ambiguity detection ("What is the block size?" → which protocol? which mode?)

#### 1.2 Retrieval Planner Agent

- **Purpose**: Orchestrates multi-hop retrieval strategy
- **Capabilities**:
  - Determines retrieval sequence (e.g., fetch definition first, then examples)
  - Cross-document reasoning (compare eMMC v5.1 vs UFS 3.0)
  - Section navigation (table of contents awareness)
  - Relationship mapping (prerequisites, dependencies)

#### 1.3 Answer Synthesis & Verification Agent

- **Purpose**: Generates grounded answers with citations
- **Capabilities**:
  - Quote extraction with page/section numbers
  - Consistency checking across retrieved chunks
  - Hallucination detection (verify every claim has source)
  - Confidence scoring

---

### 2. **Hybrid Retrieval Pipeline**

#### 2.1 Vector Search (Qdrant)

```yaml
Configuration:
  Model: sentence-transformers/all-MiniLM-L6-v2
  Vector Dimensions: 384
  Distance Metric: Cosine Similarity
  Index: HNSW (Hierarchical Navigable Small World)
  
Search Strategy:
  - Top-K retrieval: 20 candidates
  - Minimum similarity threshold: 0.7
  - Include metadata: doc_id, page_num, section_title
```

#### 2.2 Keyword Search (BM25)

```yaml
Purpose: Capture exact technical terms and spec references
Implementation: Elasticsearch or custom BM25

Features:
  - Technical term boosting (register names, acronyms)
  - Section-aware search (prioritize matching section headers)
  - Version filtering (eMMC 5.1 vs 5.0)
```

#### 2.3 Re-ranking (Cross-Encoder)

```yaml
Model: cross-encoder/ms-marco-MiniLM-L-6-v2
Purpose: Context-aware re-scoring of retrieved chunks
Input: [query, retrieved_chunk] pairs
Output: Relevance scores (0-1)
Final Selection: Top 5-10 most relevant chunks
```

---

### 3. **Document Processing Pipeline**

#### 3.1 PDF Parsing (MVP: Basic / Production: Hybrid)

**MVP Approach (Week 1):**

```python
from unstructured.partition.pdf import partition_pdf

# Fast layout-aware parsing
elements = partition_pdf(
    "emmc_5.1_spec.pdf",
    strategy="fast",
    include_page_breaks=True
)

# Extract with metadata
for element in elements:
    chunk = {
        "text": element.text,
        "type": element.category,  # Title, Text, Table
        "page": element.metadata.page_number,
        "section": extract_section_from_hierarchy(element)
    }
```

**Production Hybrid Approach:**

```python
def parse_protocol_spec(pdf_path):
    results = {"text_chunks": [], "tables": [], "diagrams": []}
    
    # 1. High-resolution layout detection
    elements = partition_pdf(
        pdf_path,
        strategy="hi_res",
        infer_table_structure=True,
        extract_images_in_pdf=True,
        model_name="detectron2_onnx"
    )
    
    for element in elements:
        if element.category == "Table":
            # 2. Enhanced table extraction with Camelot
            table = extract_table_with_camelot(
                pdf_path,
                element.metadata.page_number
            )
            results["tables"].append({
                "content": table,
                "context": get_surrounding_text(element),
                "metadata": element.metadata
            })
        
        elif element.category == "Image":
            # 3. Diagram understanding with DeepSeek-VL2
            analysis = deepseek.messages.create(
                model="deepseek-vl2",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"path": element.image_path}},
                        {"type": "text", "text": f"""
                        This diagram appears in section: {element.metadata.section}
                        Caption: {element.text}
                        
                        Extract:
                        1. Technical relationships shown
                        2. Any numerical values or timing
                        3. Component names and connections
                        """}
                    ]
                }]
            )
            results["diagrams"].append({
                "image_path": element.image_path,
                "analysis": analysis.content,
                "metadata": element.metadata
            })
        
        else:
            # 4. Text chunking with relationship preservation
            results["text_chunks"].append(create_semantic_chunk(element))
    
    # 5. Build relationship graph
    link_related_elements(results)
    
    return results
```

**Why Hybrid Approach for Specs:**

- Register tables need structural extraction (Camelot)
- Timing diagrams need vision understanding (DeepSeek-VL2)
- Cross-references need relationship mapping
- Context preservation critical for accuracy

#### 3.2 Semantic Chunking Strategy

```yaml
Approach: Structure-aware chunking (not fixed-size)

Hierarchy:
  1. Section-based chunks (respect document structure)
  2. Paragraph-level chunks (maintain semantic coherence)
  3. Sliding window overlap: 50 tokens
  
Chunk Metadata:
  - doc_id: "emmc_5.1_spec"
  - section_path: "7.4.3 Device Identification"
  - page_numbers: [45, 46]
  - parent_chunk_id: for hierarchical retrieval
  - chunk_type: text | table | figure_caption
```

#### 3.3 Embedding Generation

```python
# Contextual embeddings with section context
def generate_embedding(chunk):
    context = f"Document: {doc_title}\nSection: {section_path}\n\n{chunk_text}"
    embedding = model.encode(context)
    return embedding
```

---

### 4. **Transparency & Provenance Tracking**

#### 4.1 Citation Format

```json
{
  "answer": "The eMMC device operates in 8-bit SDR mode during boot...",
  "citations": [
    {
      "text": "During boot operation, the device uses 8-bit Single Data Rate (SDR) mode.",
      "source": "JESD84-B51_eMMC_Spec.pdf",
      "section": "7.2.1 Boot Operation",
      "page": 134,
      "chunk_id": "emmc51_chunk_789",
      "confidence": 0.94
    }
  ],
  "reasoning_steps": [
    "1. Decomposed query into: boot mode operation",
    "2. Retrieved 8 relevant chunks from eMMC 5.1 spec",
    "3. Cross-verified with boot sequence section",
    "4. Extracted exact specification text"
  ]
}
```

#### 4.2 Audit Trail

```sql
-- Stored in PostgreSQL
CREATE TABLE query_audit (
    query_id UUID PRIMARY KEY,
    timestamp TIMESTAMP,
    user_id VARCHAR(50),
    query_text TEXT,
    retrieved_chunks JSONB,
    answer TEXT,
    citations JSONB,
    confidence_score FLOAT,
    feedback_rating INT
);
```

---

## Docker Architecture

### Container Stack

**MVP Version (Week 1):**

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage

  # Streamlit App (combined UI + backend)
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - qdrant
    volumes:
      - ./specs:/app/specs  # Mount spec PDFs

volumes:
  qdrant-data:
```

**Production Version:**

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Frontend (React)
  web-ui:
    image: agentic-rag-ui:latest
    build: ./ui
    ports:
      - "8501:8501"
    environment:
      - API_GATEWAY_URL=http://api-gateway:8000
    depends_on:
      - api-gateway

  # API Gateway
  api-gateway:
    image: agentic-rag-api:latest
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - ORCHESTRATOR_URL=http://orchestrator:8001
    depends_on:
      - orchestrator

  # Agentic Orchestrator
  orchestrator:
    image: agentic-rag-orchestrator:latest
    build: ./orchestrator
    ports:
      - "8001:8001"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - POSTGRES_URL=postgresql://user:pass@postgres:5432/rag_db
      - LLM_API_KEY=${DEEPSEEK_API_KEY}
    depends_on:
      - qdrant
      - postgres
    volumes:
      - ./models:/models  # Local model cache

  # Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage

  # Document & Metadata Store
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=rag_db
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Document Ingestion Service
  ingestion:
    image: agentic-rag-ingestion:latest
    build: ./ingestion
    environment:
      - QDRANT_URL=http://qdrant:6333
      - POSTGRES_URL=postgresql://user:pass@postgres:5432/rag_db
    volumes:
      - ./spec-documents:/input  # Mount spec PDFs here
    depends_on:
      - qdrant
      - postgres

volumes:
  qdrant-data:
  postgres-data:
```

---

## Technology Stack

### MVP Stack (Week 1)

**Core:**

- **Language:** Python 3.11+
- **Frontend:** Streamlit
- **LLM:** DeepSeek-R1 (API)
- **Fast Classifier:** DeepSeek-V3 (for query routing)

**Data:**

- **Vector DB:** Qdrant (Docker)
- **Metadata Store:** SQLite
- **Embeddings:** sentence-transformers/all-MiniLM-L6-v2
- **PDF Parsing:** Unstructured.io (basic mode)

**Deployment:**

- **Container:** Docker Compose (2 services)
- **Orchestration:** Simple Python functions

### Production Stack (Post-MVP)

**Language & Framework**

- **Python 3.11+**: Core language
- **FastAPI**: API Gateway & Orchestrator APIs
- **React.js + TypeScript**: Web UI
- **LangGraph**: Agentic workflow orchestration

**LLM & Embeddings**

- **LLM**: DeepSeek-R1 for agentic reasoning
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2`
- **Re-ranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Vector & Data Storage

- **Vector DB**: Qdrant (native Docker support, HNSW index)
- **Document Store**: PostgreSQL (specs, chunks, metadata)
- **Search**: Custom BM25 implementation or Elasticsearch (optional)

### Document Processing

- **PDF Parsing**: PyMuPDF (fitz)
- **Chunking**: LangChain TextSplitter + custom logic
- **Table Extraction**: Camelot or Tabula

---

## Key Workflows

### Workflow 1: Query Processing

```mermaid
graph TD
    A[User Query] --> B[Query Understanding Agent]
    B --> C{Complex Query?}
    C -->|Yes| D[Decompose into Sub-Queries]
    C -->|No| E[Single Query Path]
    D --> F[Retrieval Planner Agent]
    E --> F
    F --> G[Hybrid Retrieval]
    G --> H[Vector Search]
    G --> I[BM25 Search]
    H --> J[Re-ranker]
    I --> J
    J --> K[Top-K Relevant Chunks]
    K --> L[Answer Synthesis Agent]
    L --> M[Generate Answer with Citations]
    M --> N[Verification Check]
    N --> O{High Confidence?}
    O -->|Yes| P[Return Answer]
    O -->|No| Q[Request Clarification]
```

### Workflow 2: Document Ingestion

```mermaid
graph LR
    A[PDF Upload] --> B[Parse PDF]
    B --> C[Extract Sections]
    C --> D[Semantic Chunking]
    D --> E[Generate Embeddings]
    E --> F[Store in Qdrant]
    D --> G[Store Chunks in PostgreSQL]
    C --> H[Extract Metadata]
    H --> I[Store Metadata]
```

---

## API Specifications

### Query API

```python
POST /api/v1/query

Request:
{
  "query": "What is the block size for eMMC 5.1 in HS400 mode?",
  "filters": {
    "documents": ["emmc_5.1"],
    "sections": ["performance"]
  },
  "options": {
    "include_reasoning": true,
    "max_citations": 5
  }
}

Response:
{
  "query_id": "uuid-12345",
  "answer": "In eMMC 5.1, the block size is 512 bytes...",
  "confidence": 0.92,
  "citations": [...],
  "reasoning_steps": [...],
  "related_queries": [...]
}
```

### Document Upload API

```python
POST /api/v1/documents/upload

Request (multipart/form-data):
- file: PDF file
- metadata: {
    "title": "eMMC 5.1 Specification",
    "version": "JESD84-B51",
    "protocol": "eMMC"
  }

Response:
{
  "doc_id": "emmc_5.1_spec",
  "status": "processing",
  "chunks_created": 0
}
```

---

## 1-Week MVP Development Timeline

### Overview

Build working MVP using AI-assisted development with DeepSeek/Gemini to generate 80% of boilerplate code.

### Day 1-2: Document Ingestion 🏗️

**Objective:** Parse and index 1-2 protocol specs

**Tasks:**

1. **PDF Parsing Script** (4 hours)

   ```
   AI Prompt: "Create a Python script that uses unstructured.partition.pdf 
   to extract text from a PDF, chunk into 500-token segments with 50-token 
   overlap, preserve section headers in metadata, and save to JSON."
   ```

2. **Embedding & Indexing** (3 hours)

   ```
   AI Prompt: "Create a script that loads chunks from JSON, generates 
   embeddings using sentence-transformers, uploads to Qdrant with metadata 
   (doc_id, page, section), includes progress bar and error handling."
   ```

3. **Test & Validate** (1 hour)

**Deliverables:**

- ✅ 1-2 specs fully indexed in Qdrant
- ✅ Ingestion scripts committed

---

### Day 3-4: Core RAG Pipeline 🧠

**Objective:** Build retrieval + generation pipeline

**Day 3 Tasks:**

1. **Hybrid Search Function** (4 hours)

   ```python
   def hybrid_search(query, top_k=10):
       # Vector search from Qdrant
       vector_results = qdrant.search(query_vector, limit=10)
       # Simple keyword boost
       # Re-rank by page proximity
       return top_results
   ```

2. **Test Retrieval Quality** (2 hours)

**Day 4 Tasks:**

3. **Citation-Aware Prompt** (2 hours)

   ```python
   system_prompt = """
   You are a technical documentation assistant.
   Answer ONLY using provided chunks.
   Cite EVERY claim: [Doc, Section X.Y, Page Z]
   If uncertain, say "Not found in context."
   """
   ```

4. **Answer Generation Pipeline** (4 hours)

   ```
   AI Prompt: "Create function that takes query + retrieved chunks, 
   formats context for DeepSeek, generates answer with citations, 
   parses response into structured format with confidence score."
   ```

**Deliverables:**

- ✅ Working hybrid retrieval
- ✅ Answer generation with citations
- ✅ Tested on 20+ queries

---

### Day 5-6: Streamlit UI + Agents 🎨

**Day 5: UI Development** (6 hours)

```
AI Prompt: "Create Streamlit chat app with:
- Chat interface accepting user queries
- Loading states showing agent steps
- Answer display with expandable citations
- Sidebar to select protocols to search
- Basic PDF viewer for source documents"
```

**Day 6: Agentic Workflow** (4 hours)

1. **Query Router Agent**

   ```python
   def route_query(query):
       # Use DeepSeek-V3 to classify
       # Return: query_type, key_terms, protocols
   ```

2. **Integrate 3-Agent Pipeline**

   - Router → Retrieval → Generation

**Deliverables:**

- ✅ Working Streamlit interface
- ✅ 3-agent pipeline with routing
- ✅ Citation display with page numbers

---

### Day 7: Integration & Docker 🚀

**Morning: Docker Setup** (4 hours)

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
  
  app:
    build: .
    ports: ["8501:8501"]
    environment:
      - ANTHROPIC_API_KEY=${API_KEY}
    depends_on: [qdrant]
```

**Afternoon: Testing & Docs** (4 hours)

- Run 30 test queries
- Measure citation accuracy
- Write README with setup instructions

**Deliverables:**

- ✅ Docker deployment working
- ✅ Tested with 30+ queries
- ✅ Demo-ready system

---

### AI-Assisted Development Strategy

**Use Claude/Gemini to generate:**

- 80% of boilerplate code
- Docker configurations
- Test suites
- Documentation

**Your focus:**

- Prompt engineering for code generation
- Integration and testing
- Domain-specific logic (spec parsing nuances)
- Quality validation

**Time Savings:**

- Manual coding: 40+ hours
- AI-assisted: 15-20 hours
- **Net savings: 20-25 hours**

---

## Deployment Instructions

### Quick Start (MVP)

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/agentic-rag-mvp.git
cd agentic-rag-mvp

# 2. Set environment variables
cp .env.example .env
# Edit .env: Add DEEPSEEK_API_KEY=your-key-here

# 3. Launch with Docker
docker-compose up -d

# 4. Upload your first spec
docker-compose exec app python ingest_spec.py \
  --file /specs/emmc_5.1.pdf \
  --protocol eMMC \
  --version 5.1

# 5. Access the UI
open http://localhost:8501
```

**That's it!** Start asking questions about your protocol specs.

---

### Detailed Setup (Production)

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/yourorg/agentic-rag-system.git
cd agentic-rag-system

# Set environment variables
cp .env.example .env
# Edit .env with your DeepSeek API key
```

### 2. Build and Launch

```bash
# Build all containers
docker-compose build

# Launch services
docker-compose up -d

# Check status
docker-compose ps
```

### 3. Initialize System

```bash
# Upload specification documents
docker-compose exec ingestion python upload_specs.py \
  --input /input/emmc_5.1_spec.pdf \
  --metadata '{"protocol": "eMMC", "version": "5.1"}'

# Wait for indexing to complete
docker-compose logs -f ingestion
```

### 4. Access Interfaces

- **Web UI**: http://localhost:8501
- **API Gateway**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

---

## Performance Optimization

### For Small Team (<50 users)

1. **Single Node Deployment**: All services on one machine

2. **Resource Allocation**:

   ```yaml
   orchestrator:
     deploy:
       resources:
         limits:
           cpus: '4'
           memory: 8G
   
   qdrant:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 4G
   ```

3. **Caching Strategy**:

   - Cache frequent queries (Redis - optional)
   - Pre-compute embeddings for common terms
   - Keep hot documents in memory

4. **Query Optimization**:

   - Set `top_k=20` for initial retrieval
   - Re-rank to `top_n=5` for LLM context
   - Implement query timeout: 30 seconds

---

## Security & Compliance

### Access Control

```python
# JWT-based authentication
# Role-based access: admin, engineer, viewer
```

### Data Privacy

- All data stays within Docker network
- No external API calls except to DeepSeek (encrypted)
- Audit logging for all queries

### Document Versioning

```sql
CREATE TABLE document_versions (
    doc_id VARCHAR(100),
    version VARCHAR(20),
    uploaded_at TIMESTAMP,
    is_active BOOLEAN,
    PRIMARY KEY (doc_id, version)
);
```

---

## Monitoring & Observability

### Metrics to Track

1. **Query Metrics**:
   - Average response time
   - Confidence score distribution
   - User feedback ratings

2. **Retrieval Metrics**:
   - Precision@K
   - Recall@K
   - Re-ranker effectiveness

3. **System Metrics**:
   - Container resource usage
   - Database query performance
   - Vector search latency

### Logging

```python
# Structured logging with context
import structlog

logger = structlog.get_logger()
logger.info(
    "query_processed",
    query_id=query_id,
    latency_ms=latency,
    confidence=confidence,
    chunks_retrieved=len(chunks)
)
```

---

## Extension Points

### Future Enhancements

1. **Multi-Modal Support**: 
   - OCR for diagrams
   - Table understanding
   - Image-text alignment

2. **Collaborative Features**:
   - Query sharing
   - Answer curation
   - Expert annotations

3. **Advanced Reasoning**:
   - Comparative analysis (spec A vs B)
   - Temporal reasoning (changes between versions)
   - Causal inference (why does X affect Y?)

4. **Integration APIs**:
   - Slack bot for quick queries
   - VS Code extension
   - Jupyter notebook integration

---

## Testing Strategy

### Unit Tests

```python
# Test query decomposition
def test_query_understanding():
    agent = QueryUnderstandingAgent()
    result = agent.process("Compare eMMC and UFS boot times")
    assert len(result.sub_queries) == 2
    assert "eMMC" in result.entities
```

### Integration Tests

```python
# End-to-end retrieval test
def test_retrieval_pipeline():
    query = "What is the maximum transfer rate for UFS 3.0?"
    result = retrieval_pipeline.execute(query)
    assert result.confidence > 0.8
    assert len(result.citations) > 0
    assert "UFS 3.0" in result.answer
```

### Evaluation Dataset

```yaml
# Create golden Q&A pairs from specs
- question: "What is the block size in eMMC 5.1?"
  expected_answer: "512 bytes"
  source: "JESD84-B51, Section 7.2"
  
Metrics:
  - Exact match accuracy
  - Citation precision
  - Hallucination rate (0% target)
```

---

## Cost Estimation

### Week 1 MVP Development

| Component                             | Cost                 |
| ------------------------------------- | -------------------- |
| Anthropic API (testing ~1000 queries) | $10-20               |
| Cloud VM (optional, t3.medium)        | $0 (use local)       |
| Development tools                     | $0 (all open source) |
| **Total Week 1**                      | **$10-20**           |

### Monthly Operating Costs

**MVP (Small Team, <50 users, ~200 queries/day)**

| Component                       | Cost              |
| ------------------------------- | ----------------- |
| DeepSeek API (DeepSeek-R1)     | $5-10             |
| Cloud Infrastructure (optional) | $0-50             |
| Storage (50GB)                  | $5                |
| **Total MVP**                   | **$35-105/month** |

**Production (Small Team, <50 users, ~500 queries/day)**

| Component                                | Cost               |
| ---------------------------------------- | ------------------ |
| Cloud Infrastructure (AWS t3.xlarge)     | $120               |
| DeepSeek API (DeepSeek-R1 + VL2)        | $15-30           |
| Storage (100GB)                          | $10                |
| **Total Production**                     | **$230-280/month** |

**Self-Hosted Option**: Run on existing hardware, use local embeddings → $50-100/month (API only)

---

## MVP vs Production Feature Comparison

| Feature              | MVP (Week 1)       | Production                  |
| -------------------- | ------------------ | --------------------------- |
| **UI**               | Streamlit chat     | React with PDF highlighting |
| **Orchestration**    | 3 simple agents    | LangGraph multi-hop         |
| **PDF Parsing**      | Unstructured basic | Hybrid + Vision             |
| **Document Support** | 1-2 specs          | Multiple versions           |
| **Diagram Analysis** | Text only          | Claude Vision               |
| **Table Extraction** | Basic              | Camelot + structured        |
| **Deployment Time**  | 1 week             | 3-4 weeks                   |
| **Learning Curve**   | Low                | Medium                      |
| **Cost/month**       | $35-105            | $230-280                    |

---

## Migration Path: MVP → Production

### Phase 1: MVP (Week 1)

- ✅ Working chat interface
- ✅ Basic retrieval + citations
- ✅ Docker deployment
- ✅ 1-2 protocol specs

### Phase 2: Enhancements (Week 2-3)

- Migrate to React UI
- Add LangGraph orchestration
- Implement hybrid PDF parsing
- Support multiple spec versions

### Phase 3: Advanced Features (Week 4+)

- Diagram analysis with Claude Vision
- Table-aware retrieval
- Multi-hop reasoning
- Query refinement loops

### Phase 4: Production Hardening

- PostgreSQL migration
- Monitoring & logging
- Performance optimization
- User feedback integration

---

## Conclusion

This architecture provides a **realistic path from MVP to production**:

**Week 1 MVP delivers:**
✅ **Working system**: Answer questions with citations  
✅ **Proof of concept**: Validate approach with real specs  
✅ **Rapid feedback**: Test with users immediately  
✅ **Low cost**: $10-20 development, $35-105/month operation  

**Production upgrade provides:**
✅ **Better UX**: React UI with advanced document interaction  
✅ **Higher accuracy**: Hybrid parsing with diagram understanding  
✅ **More capabilities**: Complex reasoning, multi-document comparison  
✅ **Scalability**: LangGraph for complex workflows  

**Recommended Approach:**

1. **Week 1**: Build MVP with AI-assisted development
2. **Week 2**: Gather user feedback, identify pain points
3. **Week 3-4**: Selective upgrades based on actual needs
4. **Ongoing**: Iterate on features that provide most value

**The key insight**: Don't build everything upfront. Start simple, validate, then enhance based on real usage patterns.