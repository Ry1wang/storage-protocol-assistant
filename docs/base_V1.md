---

<aside>
💡

RAG System Flow:

User Query → System retrieves relevant information from protocols → Feeds information to LLM → LLM provides result → Feedback result to web page

Unlike direct LLM querying, this system requires the LLM to derive conclusions ONLY from the provided protocol content, preventing divergent thinking or fabrication.

Agentic RAG System Flow:

Query flow change: Task Planning & Decomposition → Dynamic Retrieval Tool Invocation → Strict Grounding Verification → Logical Synthesis & Reasoning → Result Feedback with Transparency

</aside>

---

# 1. Architecture Design

## 1.1 Core Considerations

Building such specialized domain assistants focuses on data accuracy and retrieval precision.

```markdown
1. Document Parsing: Characteristics of storage protocol documents—closely related context, frequent and important diagrams. Therefore, content extraction must ensure continuity and integrity.
2. Chunking Strategy: Protocol documents have strong logic; simple fixed-length splitting destroys context. Semantic chunking is mandatory.
3. Retrieval Precision: Protocols contain numerous technical terms; a Rerank mechanism must be introduced to ensure the most relevant original protocol fragments are fed to the LLM.
4. Prompt Injection & Constraints: LLM behavior must be explicitly defined.
```

---

## 1.2 Data Flow

The system's data flow is divided into "Offline Pre-processing" and "Online Retrieval Response" phases:

```markdown
Phase A:
1. Original Protocol Document (PDF) -> Parsing & Extraction
2. Text Chunking -> Vectorization
3. Vector Storage

Phase B:
1. User Query -> Query Rewriting/Pre-processing
2. Vector Retrieval + Keyword Search -> Hybrid Retrieval Results
3. Rerank Filtering -> Top-K Relevant Protocol Fragments
4. Prompt Encapsulation -> LLM
5. Strict LLM Response -> Web Frontend Display
```

---

## 1.3 Technology Stack

```markdown
Frontend Framework: React.js (Considerations: streaming rendering, componentization needs, ecosystem plugins)
Backend Framework: Python FastAPI (Considerations: native async support, automatic API doc generation and data validation; FastAPI can deeply integrate with async AI frameworks like LangChain/LlamaIndex with minimal code)
Vector Database: Milvus Standalone + Attu (Considerations: strong metadata filtering, supports hybrid search)
Document Processing: LayoutPDFReader (Considerations: structural fidelity, semantic integrity, figure/table handling strategies)
Large Language Model: DeepSeek
Orchestration Tool: Responsible for串联 frontend requests, vector database, document parser, and LLM to complete automated workflow scheduling.
Deployment: Docker
Embedding Model: BGE-M3
Reranker: BGE-Reranker
Static File Service

Thinking:
Q: LlamaIndex natively supports recursive retrieval and hierarchical indexing. eMMC/UFS protocol features mean a knowledge point might involve multiple chapters and needs to be pieced together.
A: Introduce GraphRAG; Multi-Query/Query Expansion; "Small chunk retrieval, large chunk feeding" strategy (Parent-Child Retriever); Introduce Reranker.

Q: Why deploy to Docker?
A: Docker is a containerization technology. It allows us to package an application and all its dependencies (code, runtime, system libraries, configuration files, etc.) into an independent, lightweight "container."
For the selected stack, Docker handles version conflicts, isolates complex PDF parsing environments, simplifies Milvus deployment, and is easy to scale and migrate.
```

<aside>
💡

**Tech Stack Summary**

Frontend: React.js

Gateway: Nginx (Docker)

Service: Python FastAPI

Orchestration: LlamaIndex

Model: DeepSeek / BGE-M3 / Reranker

Storage: Milvus Standalone

Parsing: LayoutPDFReader

</aside>

---

# 2. Process / Logic

Ordered by hierarchy and priority.

## 2.1 Parsing Layer

- Demo
    
    ```markdown
    1. Define Input and Output
    	- text: 
    		- Individual Paragraph -> Context-Aware Chunk (includes paragraph text + parent header path)
    		- Bulleted list (multiple paragraphs) -> Preserve logical structure, convert to Markdown list format
    		metadata: protocol version, chapter, page number, keywords (user defined)
    	- table:
    		- table -> Combine headers with data rows, output multiple key-value chunks. E.g., if header is "CMD Index, Argument" and there are 10 rows, output 10 chunks, each containing "CMD Index: CMD0, Argument: ..."
    		metadata: protocol version, chapter, page number, table name, keywords (user defined)
    	- figure (Temporarily not introducing image parsing, only need to know what figure is here):
    		- vector figure -> figure name
    		- bitmap -> figure name
    		metadata: protocol version, chapter, page number
    ```

### 2.1.1 Text Data Parsing Solution

- **Input:** Text stream identified by LayoutPDFReader.
- **Processing Logic:**
    1. **Chunking Strategy:** No longer purely physical (e.g., every 500 characters), but cut by **Semantic Boundaries**. A list must be fully preserved in one chunk.
    2. **Metadata Injection:** Automatically backtrack the PDF directory tree during slicing to attach hierarchical information to the chunk.
- **Output Expected:**
    
    ```json
    {
      "content": "### 7.4.1 Read Operation \n * Step 1: ... \n * Step 2: ...",
      "metadata": {
        "protocol": "eMMC 5.1",
        "chapter": "7.4.1",
        "page_range": [102, 103],
        "entities": ["Read", "CMD18"],
        "logical_type": "sequence_list"
      }
    }
    ```

---

### 2.1.2 Table Data Parsing Solution

- **Input:** Table structure identified by LayoutPDFReader (including cross-page recognition).
- **Processing Logic:**
    1. **Header Flattening:** Recursively process multi-level headers to generate composite keys.
    2. **Footnote Injection:** Distribute table footnotes to each row according to index numbers.
    3. **Null Value Handling:** Standardize common `Reserved` bits in protocols or decide whether to keep them based on requirements.
- **Output Expected:**
    
    ```json
    {
      "content": "[Table 32: Host Control Register] - Offset [0x04] - Bit [15:8]: Timeout Counter Value. (Note: Valid only when bit 0 is set)",
      "metadata": {
        "protocol": "UFS 4.0",
        "chapter": "10.2.1",
        "page": 215,
        "table_name": "Host Control Register",
        "has_notes": true
      }
    }
    ```

---

### 2.1.3 Image Data Parsing Solution

- **Input:** Figure/chart areas identified by LayoutPDFReader.
- **Processing Logic:**
    1. **Automatic Extraction:** Export images as high-resolution independent files (stored in file system).
    2. **Context Linkage:** Search for `Figure X-X` keywords in the document, grab the chapter title and adjacent explanatory descriptions.
    3. **Placeholder Generation:** Insert an `[IMAGE_ID: XXX]` tag in the corresponding text chunk to maintain semantic continuity.
- **Output Expected:**
    
    ```json
    {
      "content": "[Figure 7-1: Write Operation Flowchart] - This figure illustrates the state transitions during a multi-block write sequence and error handling.",
      "metadata": {
        "protocol": "eMMC 5.1",
        "chapter": "7.4.2",
        "page": 105,
        "figure_id": "fig_7_1_001",
        "anchor_text": "The sequence is described in Figure 7-1...",
        "image_type": "vector"
      }
    }
    ```

---

### 2.1.4 Others

1. **Table of Contents & Hierarchy**
    - **Input:** PDF TOC page or sidebar labels.
    - **Output:** A flattened but parent-child relational JSON tree.
    - **Metadata:** Depth (Level 1/2/3), title name, starting page number.
2. **Cross-Reference Map**
    - **Logic:** Identify regex `Section \d+(\.\d+)*` or `Table \d+`.
    - **Output:** Establish an index dictionary. E.g., `"Table 15" -> { "page": 102, "chapter": "7.2" }`.
3. **Formulas & Pseudo-code**
    - **Input:** Formula blocks or code blocks.
    - **Output:** Convert to **LaTeX format** (for formulas) or **standard Markdown code blocks**.
    - **Metadata:** Involved variables (e.g., $V_{CC}$), so the Agent can directly find calculation methods via variable names.
4. **Glossary & Acronyms**
    - **Input:** "Terminology" or "Definitions" chapters at the beginning of protocols.
    - **Output:** Key-Value pairs (Term: Definition).
    - **Metadata:** Labeled as `Entity_Definition`.

<aside>
💡

**Introducing "Domain Isolation"**

Users specify physical page ranges for TOC, Glossary, and Body (including Appendices) in the PDF, effectively as follows:

{
"toc_pages": [2, 5],
"glossary_pages": [6, 12],
"body_pages": [13, 340]
}

Body range uses the parsing solution discussed in 2.1.1~2.1.3.

</aside>

---

### 2.1.5 Technical Solution

Parsing layer logic:

- **Manually specified regions** (TOC, Glossary, Body).
- **Domain-specific execution strategy** (TOC to Tree, Glossary to KV, Body uses three formatting parses).
- **Structured output** (Semantic chunks with metadata).

Technical solution:

- **Input Control:** User specifies page ranges.
- **Tool Matrix:** `PyMuPDF` (Slicing) + `LlamaParse` (Layout) + `Pandas` (Tables) + `OCR/Formula Libs` (Specialized).
- **Quality Guard:** **Pydantic** (Standardized output).

---

## 2.2 Orchestration Layer

### 2.2.1 Query Understanding & Routing

- Demo
    
    ```python
    User Scenarios:
    1. Application-oriented:
        - How to implement a function? (e.g., Partitioning? Answer steps, registers, CMDs)
        - How to configure a CMD argument? (e.g., CMD24? Answer purpose, specific arguments)
        - What does command response xxx mean?
        - Verify code snippet against protocol specs.
    
    2. Learning-oriented:
        - What are eMMC features?
        - What registers does eMMC have?
        - How to understand timing diagram? (Future support)
    ```

---

**Implementation Plan:**

**1. Tool Definition:**
Wrap retrievers as tools with clear descriptions:
- **Tool_Glossary**: Description: "Dedicated tool for querying technical terms and acronym definitions."
- **Tool_Spec_Table**: Description: "Tool for querying specific parameters, register bit widths, voltages, and other structured data."
- **Tool_General_Text**: Description: "Tool for querying operational procedures, timing descriptions, and functional overviews."

**2. Decision Layer (Agent Router):**
Leverage LLM's Function Calling (e.g., DeepSeek):
- **Simple Queries**: If LLM determines it's a parameter query, call `Tool_Spec_Table` directly.
- **Complex Queries** (e.g., "What is the CMD18 parameter configuration flow?"): LLM automatically decomposes: first call `Tool_Spec_Table` for parameters, then `Tool_General_Text` for flow, finally synthesize results.

---

### 2.2.2 Tool Definitions / Skill Set

**1. Tool_Glossary**
- Function: Query official definitions of technical terms to eliminate ambiguity.
- Input: `term: str` (e.g., "Reliable Write", "UFS")
- Logic:
    - Exact/fuzzy matching in Glossary index.
    - If no hit, search for segments matching "Definition of..." in the whole document.
- Output: Original definition text.

**2. Tool_Spec_Table**
- Function: High-precision query for register widths, command arguments, voltage ranges, etc.
- Input:
    - `keywords: List[str]` (e.g., ["CMD6", "Argument", "Access Mode"])
    - `target_attribute: str` (Optional, e.g., "Bit 24")
- Logic:
    - Hybrid search (keyword + vector) in Table chunks.
    - Prioritize Header and Table Name matching.
    - Extract specific **Rows** containing target attributes and associated **Notes**.
- Output: JSON formatted row data + relevant Table Notes.

**3. Tool_General_Text**
- Function: Query operational flows, initialization steps, and functional descriptions.
- Input: `query: str` (Natural language query, e.g., "Initialization sequence of HS400")
- Logic:
    - **Query Expansion**: Convert query into terms matching document expressions.
    - **Hybrid Search**: Vector retrieval + BM25 keyword search in Text chunks.
    - **Rerank**: Semantic re-ranking of top 50 results to select Top-K.
- Output: List of Top-K relevant text segments with parent chapter paths.

**4. Tool_Figure_Retrieval**
- Function: Find state machines, timing diagrams, or architecture diagrams.
- Input: `description: str` (e.g., "Device State Diagram")
- Logic:
    - Search Image Chunk metadata (Caption, Anchor Text).
    - Match surrounding context descriptions.
- Output: Image file path/ID + Image Title + brief caption explanation.

---

### 2.2.3 Reasoning Loop

Adopting the **ReAct (Reason + Act)** pattern with a "Self-Reflection" mechanism.

**Flow Diagram:**

`User Input` -> Step 1: Analyze & Decompose -> Step 2: Execution Loop -> Step 3: Verify & Synthesize -> `Final Response`

**Detailed Steps:**

**Step 1: Decomposition**
- Input: Raw user query.
- LLM Action: Determine if the query consists of multiple sub-questions (e.g., "Compare throughput of eMMC 5.1 and UFS 4.0" -> "Check eMMC 5.1 throughput" + "Check UFS 4.0 throughput").
- Output: Chain of Thought (CoT), generating initial action plan.

**Step 2: Execution Loop**
- Action: Invoke tools per plan (e.g., `Tool_Spec_Table(query="eMMC 5.1 max throughput")`).
- Observation: Receive JSON data or text segments from tools.
- Reflection (Critical): Check if results contain the required answer.
    - Case A (Hit): Proceed to next step.
    - Case B (Missing/Vague): Refine keywords, try `Tool_General_Text` as fallback, or expand search scope (e.g., parent chapter).

**Step 3: Synthesize & Verify**
- Input: All retrieved Context Chunks.
- LLM Actions:
    - **Conflict Detection**: If data from different sources (e.g., different chapters) conflict, prioritize **Table Data** or the **Latest Protocol Version**.
    - **Answer Generation**: Generate answer based on facts.
    - **Citation Tagging**: MUST tag every fact with source anchors like `[Source: Protocol Version, Section X.X]`.
- Output: Final response.

---

### 2.2.4 Response Synthesis & Guardrails

**1. Synthesis Strategy**
- Structured Output Enforcement:
    - Use Markdown tables for parameter comparisons.
    - Use ordered lists (1. 2. 3.) for operational procedures.
- Strict Citations:
    - Every statement MUST include a source anchor: `[eMMC 5.1, Sec 6.6.2, Page 128]`.
    - Forbidden to answer based purely on internal knowledge (prevents confusion between versions).
- Verbatim Quotes:
    - For register definitions or critical warning Notes/Cautions, prioritize direct quotes (English original) over paraphrasing to ensure no ambiguity.

**2. Guardrails**
- "I Don't Know" Policy:
    - Set **Relevance Threshold**: If similarity scores of all retrieved chunks are below a threshold (e.g., 0.6), the system must state "Information not found in current protocol documents" to prevent fabrication.
- Scope Restriction: Identify and reject non-technical/non-protocol queries (e.g., "How is the weather?").
- Hallucination Check / Grounding:
    - **NLI (Natural Language Inference) Verification**: Before outputting, call a small model (or the model itself) to verify: "Is the generated answer supported (Entailed) by the retrieved context?". If "No", discard or retry.
- Conflict Resolution:
    - Hard rule: **Spec Tables** override text descriptions.
    - Hierarchy rule: **Specific Chapters** override General Intro chapters.

---

### 2.2.5 State & Memory Management

**1. Global Context**
- Protocol Locking: Remember the protocol version in focus (e.g., `Current_Protocol = "eMMC 5.1"`). Default to this version if not specified in follow-up queries.
- Chapter Focus: Record currently browsed/queried chapters, prioritizing them for next searches.

**2. Multi-turn Follow-up**
- Coreference Resolution: Identify "it" in "What are its parameters?" as the previously discussed entity (e.g., CMD6).
- List Navigation: If the previous output had 5 steps, handle "How to do step 3?" by locating and expanding step 3 content (Step-level Memory).

**3. Reset Strategy**
- Explicit Switch: Clear old protocol context cache upon explicit user commands (e.g., "Switch to UFS 3.0").
- Sliding Window: Retain only N-turns (e.g., 3-5 turns) of dialogue history as prompt context to prevent noise.

---

## 2.3 Model Layer

### 2.3.1 Data Storage Chunks

**Base Metadata Model**

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class BaseProtocolMetadata(BaseModel):
    protocol_type: str = Field(..., description="eMMC or UFS")
    version: str = Field(..., description="e.g., 5.1, 4.0")
    chapter_path: str = Field(..., description="Full path, e.g., 7 > 7.4 > 7.4.1")
    page_number: int
    data_type: str = Field(..., description="text, table, or image")
    keywords: List[str] = []
```

**Specialized Model**

| Model Name | Core Fields | Validation Logic Example |
| --- | --- | --- |
| **TextChunk** | `content: str` | Ensure text is not empty and extra control chars removed. |
| **TableChunk** | `rows: List[Dict]`, `table_name: str` | Ensure every row has header keys and linked footnotes. |
| **ImageChunk** | `image_id: str`, `anchor_text: str` | Ensure image ID exists in local storage. |

---

### 2.3.2 API DTOs

**ChatRequest**

- `query: str`
- `session_id: str`
- `selected_protocol: Optional[str]` (e.g., "eMMC 5.1")
- `mode: str` ("fast" or "deep")

**ChatResponse**
- `answer: str`
- `sources: List[SourceNode]` (includes page, chapter, snippet)
- `reasoning_trace: Optional[str]` (For "Thinking..." display)
- `suggested_questions: List[str]`

---

### 2.3.3 Vector DB Schema (Milvus)

**Collection: Protocol_Chunks**
- `id: Int64` (Primary Key)
- `vector: FloatVector[1024]` (BGE-M3 vector)
- `content: VarChar` (Text/Table JSON)
- `metadata_json: JSON` (Serialized `BaseProtocolMetadata` for advanced filtering)
- `chunk_type: Int8` (1=Text, 2=Table, 3=Image)

---

## 2.4 Storage Layer

### 2.4.1 Hybrid Storage Strategy

**Vector Store: Milvus**
- **Use**: Store embeddings for Text/Table chunks.
- **Config**: Enable MMap for reading speed; use IVFFLAT index for protocol terms to balance speed/recall.

**Relational DB: SQLite / PostgreSQL**
- **Use**:
    - **Session History**: Persist user chat history.
    - **File Index**: Store PDF metadata (filename, version, parsing status).
    - **Feedback**: Log Upvotes/Downvotes for optimization.

**Object/File Storage: Local File System**
- **Use**:
    - Store original PDFs for frontend preview.
    - Store high-res **Figures** and **Table screenshots** extracted during parsing.

**Cache: Redis**
- **Use**:
    - **LLM Context Cache**: Cache current session context to speed up multi-turn chat.
    - **Hot Query**: Cache standard answers for high-frequency questions (e.g., "eMMC pinout").

---

## 2.5 Service Layer

Asynchronous microservices based on **FastAPI**, emphasizing **high-concurrency I/O**.

### 2.5.1 Core Service Modules
**Ingestion Service**
- **Responsibility**: Handle PDF uploads, LayoutPDFReader parsing, chunk cleaning, vectorization.
- **Features**: Use **Background Tasks** or Celery for long parsing tasks; push progress to frontend via WebSocket.

**Retrieval Service**
- **Responsibility**: Encapsulate Milvus query interface and BGE-Reranker logic. Provide atomic capabilities like `search_text`, `search_table`, `search_image`.

**Chat Service**
- **Responsibility**: Implement Agentic logic (ReAct Loop), assemble prompts, manage states, and interact with LLM.

### 2.5.2 Communication
**Streaming**: Use **Server-Sent Events (SSE)** to push LLM reasoning and final answers token-by-token, lowering perceived latency.

---

## 2.6 Frontend Layer

Stack: **React.js + Tailwind CSS + Zustand**

### 2.6.1 Core Interaction Design
**Chat Interface**
- **Markdown Pro Rendering**: Support complex tables and code blocks.
- **Reasoning Accordion**: Hide intermediate "Thinking" process by default; click to expand.

**Dual-Pane PDF Viewer**
- **Citation Navigation**: Users click `[Sec 7.4, Page 102]` to **Auto-Scroll** and **Highlight** that segment in the PDF viewer.

**Protocol Switcher**
- Global dropdown for protocol version (e.g., `[ eMMC 5.1 ▼ ]`), filtering searches to that context.

---

## 2.7 Gateway Layer

Unified entry via **Nginx** (Docker).

**Reverse Proxy**
- `/api/v1/*` -> Forward to FastAPI (Port 8000).
- `/static/*` -> Map to host file storage for PDFs/Images.
- `/*` -> Point to React static assets (SPA).

**Base Security**
- CORS policies.
- `client_max_body_size` adjustment for large Spec PDFs.

---
