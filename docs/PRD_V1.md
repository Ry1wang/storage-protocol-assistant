# Storage Protocol Assistant - Product Requirements Document (PRD)

## 1. Introduction

### 1.1 Purpose
The Storage Protocol Assistant is an advanced **Agentic RAG (Retrieval-Augmented Generation)** system designed to provide high-precision, grounded, and context-aware answers for storage protocol specifications (e.g., eMMC, UFS). Unlike general-purpose LLMs, this system strictly adheres to provided protocol documents, preventing hallucinations and ensuring technical accuracy for engineering and learning use cases.

### 1.2 Target Audience
- **Protocol Engineers**: Need exact register values, timing sequences, and configuration steps.
- **Learners/Developers**: Need to understand protocol concepts, terminology, and functional flows.
    
### 1.3 Core Value Proposition
- **Accuracy**: Strict "Grounding" to protocol text/tables.
- **Context Awareness**: Understanding of cross-chapter relationships and protocol versions.
- **Transparency**: Visible reasoning process (Chain of Thought) and strict citation sources.

---

## 2. System Architecture

The system follows a "Hybrid Data Flow" architecture with distinct Offline and Online phases.

### 2.1 High-Level Data Flow
1.  **Offline Phase (Ingestion)**:
    -   **Parsing**: Layout-aware extraction of Text, Tables, and Figures from Spec PDFs.
    -   **Chunking**: Semantic segmentation based on protocol structure (Chapter -> Section).
    -   **Indexing**: Hybrid indexing (Dense Vector + Sparse Keyword + Structural Metadata).
2.  **Online Phase (Retrieval & Generation)**:
    -   **Router**: Semantic intent classification to select optimal retrieval tools.
    -   **Retrieval**: Hybrid Search (Milvus) + Reranking (BGE-Reranker).
    -   **Reasoning**: ReAct (Reason+Act) loop for complex query decomposition.
    -   **Synthesis**: Strict citation-based answer generation.

### 2.2 Technology Stack
-   **Frontend**: React.js (Tailwind CSS, Zustand)
-   **Gateway**: Nginx (Dockerized)
-   **Backend**: Python FastAPI (Async I/O)
-   **Orchestration**: LlamaIndex Workflows (Event-driven Agentic RAG)
    -   **Reasoning Loop**: Custom ReAct implementation using LlamaIndex's event-based state machine for strict flow control (Decompose -> Tool Call -> Reflect -> Synthesize).
-   **LLM**: DeepSeek
-   **Vector DB**: Milvus Standalone (IVFFLAT Index)
-   **Embedding**: BGE-M3 (Multi-lingual, Multi-functionality)
-   **Reranker**: BGE-Reranker
-   **PDF Parsing**: LayoutPDFReader (Smart parsing)

---

## 3. Functional Requirements

### 3.1 Data Ingestion & Parsing (Parsing Layer)
**Goal**: Transform unstructured PDF Specs into structured, semantically rich chunks.

#### 3.1.1 Domain Isolation
-   **Input**: User specifies page ranges for:
    -   **TOC** (Table of Contents)
    -   **Glossary** (Definitions)
    -   **Body** (Core Content)
-   **Logic**: Apply different parsing strategies per domain.

#### 3.1.2 Text Parsing
-   **Strategy**: **Semantic Boundary Chunking**.
-   **Constraint**: Never split a list or small section across chunks.
-   **Metadata Injection**: Each chunk MUST contain: `Protocol Version`, `Chapter/Section Path`, `Page Number`.

#### 3.1.3 Table Parsing
-   **Strategy**: **Table Flattening**.
-   **Logic**:
    -   Recursively flatten nested headers.
    -   Inject table footnotes (Notes) into relevant rows.
    -   Standardize `Reserved` or empty cells.
-   **Output**: JSON format with `table_name`, `header`, `row_data`.

#### 3.1.4 Figure Parsing
-   **Strategy**: **Placeholder + Context**.
-   **Logic**:
    -   Extract high-res generic images/diagrams to file storage.
    -   Insert `[IMAGE_ID: <ID>]` placeholder in text flow.
    -   Capture caption (`Figure X-X`) and surrounding description anchor text.

### 3.2 Retrieval & Indexing (Retrieval Layer)

#### 3.2.1 Hybrid Indexing Schema
-   **Vector Search**: BGE-M3 embeddings for semantic similarity.
-   **Keyword Search**: BM25/Sparse vectors for exact term matching (e.g., "CMD6").
-   **Metadata Filtering**: Filter by `protocol_version`, `chapter`, `chunk_type`.

#### 3.2.2 Query Routing (Agentic Router)
-   **Mechanism**: LLM Function Calling to select specialised tools.
-   **Tools Defined**:
    1.  **`Tool_Glossary`**: Query term definitions from Glossary/Definitions chapters.
    2.  **`Tool_Spec_Table`**: Query parameters, bit-fields, voltages from structured Table chunks.
    3.  **`Tool_General_Text`**: Query operational flows, sequences, and descriptions from Text chunks.
    4.  **`Tool_Figure_Retrieval`**: Query diagrams, state machines, and timing charts.

### 3.3 Reasoning & Orchestration (Agentic Layer)

#### 3.3.1 ReAct Loop (Reason + Act)
-   **Step 1: Decomposition**: Break down complex queries (e.g., "Compare X and Y") into sub-tasks.
-   **Step 2: Execution**: Call retrieval tools.
-   **Step 3: Reflection**: Evaluate if retrieved context is sufficient. If not, refine query or expand search scope (Parent-Child).
-   **Step 4: Synthesis**: Compile final answer with citations.

#### 3.3.2 Guardrails & Safety
-   **"I Don't Know" Policy**: Reject low-confidence results (< threshold).
-   **Scope Restriction**: Reject non-protocol questions.
-   **Conflict Resolution**: Table Data > Text Description; Specific Chapter > General Chapter.
-   **Hallucination Check**: NLI (Natural Language Inference) check to ensure answer is entailed by retrieving chunks.

#### 3.3.3 State Management
-   **Protocol Locking**: Sticky session for Protocol Version (e.g., "eMMC 5.1").
-   **Context Sliding Window**: Retain last N=3-5 turns.
-   **Coreference Resolution**: Handle "it", "that", "the previous command".

### 3.4 User Interface (Frontend Layer)

#### 3.4.1 Chat Interface
-   **Streaming Response**: Display token-by-token generation via SSE.
-   **Reasoning Accordion**: Collapsible view of the "Thinking Process" (tool calls, reflections).
-   **Rich Markdown**: Support for complex tables, code blocks, and LaTeX formulas.

#### 3.4.2 Dual-Pane PDF Review
-   **PDF Viewer**: Integrated right-panel viewer.
-   **Citation Linking**: Clicking `[Sec 7.4, Page 102]` in chat automatically:
    -   Scrolls PDF to Page 102.
    -   Highlights the referenced paragraph/table/figure.

#### 3.4.3 Feature Controls
-   **Protocol Selector**: Dropdown to switch active protocol context.
-   **Mode Switch**: "Fast Mode" (Direct Retrieval) vs "Deep Mode" (ReAct Reasoning).

---

## 4. Data Models & API Interface

### 4.1 Metadata Models (Pydantic)
**BaseProtocolMetadata**:
-   `protocol_type`: str (e.g., "eMMC")
-   `version`: str (e.g., "5.1")
-   `chapter_path`: str (Full hierarchy)
-   `page_number`: int
-   `data_type`: Enum (text, table, image)

**Chunk Specifics**:
-   `TextChunk`: `content` (str)
-   `TableChunk`: `table_name` (str), `rows` (List[Dict])
-   `ImageChunk`: `image_id` (str), `anchor_text` (str)

### 4.2 API DTOs (Data Transfer Objects)

**POST /api/chat**
-   **Request**:
    ```json
    {
      "query": "How to configure CMD6?",
      "session_id": "uuid",
      "selected_protocol": "eMMC 5.1",
      "mode": "deep"
    }
    ```
-   **Response**:
    ```json
    {
      "answer": "To configure CMD6...",
      "sources": [{"page": 102, "text": "...", "score": 0.89}],
      "reasoning_trace": "Step 1: Check Glossary... Step 2: Search Table...",
      "suggested_questions": ["What is the argument for CMD6?"]
    }
    ```

---

## 5. Non-Functional Requirements

-   **Accuracy**: < 5% Hallucination rate on technical specs.
-   **Latency**:
    -   Simple Query: < 2s TTFB (Time to First Byte).
    -   Complex Reasoning: < 10s total completion.
-   **Scalability**: Support large PDF files (500+ pages) without memory overflow during parsing.
-   **Security**: No external model calls for proprietary data (local deployment capable); Read-only access to source PDFs.
