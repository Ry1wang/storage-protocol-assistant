# Chunking Strategy & Context Integrity

## Overview

This document explains the **semantic chunking strategy** and how **context integrity** is guaranteed throughout the ingestion pipeline.

## Chunking Strategy

### 1. Element-Based Semantic Chunking

Unlike naive fixed-size chunking that splits text arbitrarily, our approach uses **structure-aware semantic chunking**:

```
Traditional Chunking:          Semantic Chunking:
┌─────────────────┐           ┌──────────────────────┐
│ "...data trans  │           │ Section 1: Power Mgmt│
│ fer rate is..." │ ❌        │ • Paragraph 1        │ ✅
├─────────────────┤           │ • Paragraph 2        │
│ "fer rate is... │           │ • Table 1            │
│ maximum of..."  │           └──────────────────────┘
└─────────────────┘           ┌──────────────────────┐
                              │ Section 2: Data Rate │
                              │ • Paragraph 1        │
                              │ • List items         │
                              └──────────────────────┘
```

**Key Principle:** Chunks respect document structure and never split in the middle of semantic units.

### 2. Multi-Level Structure Preservation

#### Level 1: PDF Parsing (pdf_parser.py)
Extracts structured elements while preserving hierarchy:

```python
# Each element extracted contains:
{
    "text": "Actual content",
    "type": "heading" | "text" | "table" | "list_item" | "figure_caption",
    "page_numbers": [1, 2],
    "section_title": "Chapter 1: Introduction",
    "section_path": "Chapter 1 > Section 1.1 > Subsection 1.1.1",
    "metadata": {...}
}
```

**Hierarchy Tracking:**
- Heading levels estimated from text length
- Section paths built progressively (e.g., "Chapter 1 > Power Management > Sleep Mode")
- Page numbers tracked for every element

#### Level 2: Semantic Chunking (chunker.py)
Combines elements into coherent chunks:

```python
# Chunking Logic:
1. Start with empty chunk
2. For each element:
   - Check if adding it exceeds chunk_size (default: 500 tokens)
   - If NO: Add element to current chunk
   - If YES: Save current chunk, start new chunk with overlap
3. Special handling for tables (never split)
4. Preserve all metadata from elements
```

### 3. Configuration Parameters

```bash
# .env configuration
CHUNK_SIZE=500        # Target chunk size in tokens
CHUNK_OVERLAP=50      # Overlap between consecutive chunks
```

**Why 500 tokens?**
- Large enough: Captures complete semantic units (2-3 paragraphs)
- Small enough: Precise retrieval without too much noise
- Optimal for embedding models (384-512 dim embeddings)

**Why 50 token overlap?**
- Prevents information loss at chunk boundaries
- Ensures concepts spanning chunk boundaries are captured
- ~10% overlap provides continuity without excessive duplication

## Context Integrity Guarantees

### Mechanism 1: Structure-Aware Splitting

**Guarantee:** Chunks never split mid-paragraph or mid-sentence.

**Implementation:**
```python
# Elements are atomic units - never split
for element in elements:
    if current_chunk_tokens + element_tokens > chunk_size:
        # Save current chunk BEFORE adding element
        save_chunk(current_chunk)
        # Start new chunk, add complete element
        start_new_chunk()
        add_element(element)
```

**Example:**
```
Element 1: "Power management enables battery optimization..." (120 tokens)
Element 2: "The device supports three power states..." (130 tokens)
Element 3: "Table 1-1: Power State Specifications..." (280 tokens)

Chunk 1: Element 1 + Element 2 = 250 tokens ✅
Chunk 2: Element 3 = 280 tokens ✅ (complete table)

NOT: Element 1 + half of Element 2 ❌
```

### Mechanism 2: Table Integrity Protection

**Guarantee:** Tables are NEVER split, regardless of size.

**Implementation:**
```python
# Special handling for large tables
if element_type == "table" and element_tokens > chunk_size:
    # Flush current chunk
    save_chunk(current_chunk)

    # Add table as its own dedicated chunk
    create_chunk([table_text], chunk_type="table")
```

**Rationale:**
- Tables contain structured data where rows/columns are interdependent
- Splitting a table destroys semantic meaning
- Better to have one large chunk than fragmented data

**Example:**
```
Table: Register Specifications (800 tokens)
├─ Column 1: Register Name
├─ Column 2: Address
├─ Column 3: Description
└─ Column 4: Default Value

Result: Single chunk with complete table ✅
```

### Mechanism 3: Chunk Overlap for Continuity

**Guarantee:** Context from previous chunk is preserved in next chunk.

**Implementation:**
```python
def _get_overlap_text(text_parts, total_tokens):
    # Work backwards from end of previous chunk
    overlap_parts = []
    overlap_tokens = 0

    for part in reversed(text_parts):
        if overlap_tokens + part_tokens <= chunk_overlap:
            overlap_parts.insert(0, part)  # Maintain order
            overlap_tokens += part_tokens

    return overlap_parts
```

**Example:**
```
Chunk 1 (500 tokens):
  "...Power states include Active, Idle, and Sleep.
   Active mode draws 200mA current.
   Idle mode reduces to 50mA.
   Sleep mode achieves <1mA consumption..."
   [Last 50 tokens = overlap] ← Copied to Chunk 2

Chunk 2 (500 tokens):
   [First 50 tokens = overlap] ← From Chunk 1
   "Sleep mode achieves <1mA consumption.
   Wake-up latency varies by state.
   Table 2-1 shows transition times..."
```

**Benefit:**
- Queries about "sleep mode power consumption" can match either chunk
- No information lost at boundaries
- Improved retrieval recall

### Mechanism 4: Rich Metadata Preservation

**Guarantee:** Every chunk knows its provenance and context.

**Metadata Tracked:**
```python
class ChunkMetadata:
    doc_id: str                  # Source document
    chunk_id: str                # Unique identifier (UUID)
    page_numbers: List[int]      # All pages this chunk spans
    section_title: str           # Most recent section heading
    section_path: str            # Full hierarchy path
    chunk_type: str              # text | table | figure_caption
    parent_chunk_id: Optional[str]  # For hierarchical relationships
```

**Usage Example:**
```python
# Retrieved chunk knows:
chunk.metadata.page_numbers = [23, 24]
chunk.metadata.section_path = "Chapter 4 > Power Management > Sleep Modes"
chunk.metadata.chunk_type = "text"

# Can generate citation:
"According to the eMMC spec (Section 4.2 Sleep Modes, pp. 23-24)..."
```

### Mechanism 5: Element Type Tracking

**Guarantee:** Know what kinds of content are in each chunk.

**Implementation:**
```python
current_metadata["types"] = {"text", "list_item"}  # Mixed content
current_metadata["types"] = {"table"}              # Pure table

# Stored in chunk for filtering:
chunk.metadata.chunk_type = "table"  # Can filter retrieval by type
```

**Benefits:**
- Can prioritize table chunks for spec lookup queries
- Can prioritize text chunks for conceptual queries
- Enables type-aware reranking

## Visual Example: Real Document Processing

Let's trace a real example from your eMMC spec:

### Input PDF Elements
```
Page 23:
  Element 1: (heading) "4.2 Sleep Modes"
  Element 2: (text) "Sleep mode is the lowest power state..."
  Element 3: (text) "The device supports two sleep variants..."
  Element 4: (list) "• Sleep: Standard sleep with fast wake"
  Element 5: (list) "• Deep Sleep: Ultra-low power mode"
  Element 6: (table) "Table 4-1: Sleep Mode Specifications" (large)

Page 24:
  Element 7: (text) "Wake-up from sleep requires..."
```

### Chunking Process
```
Chunk 1 (350 tokens):
  Content: Elements 1 + 2 + 3 + 4 + 5
  Metadata:
    - page_numbers: [23]
    - section_title: "4.2 Sleep Modes"
    - section_path: "Chapter 4 > Power Management > Sleep Modes"
    - types: {heading, text, list_item}

Chunk 2 (650 tokens - large table):
  Content: Element 6 (complete table)
  Metadata:
    - page_numbers: [23]
    - section_title: "4.2 Sleep Modes"
    - chunk_type: "table"
    - types: {table}

Chunk 3 (with overlap):
  Content: [overlap from Chunk 1] + Element 7
  Metadata:
    - page_numbers: [23, 24]  # Spans boundary
    - section_title: "4.2 Sleep Modes"
```

### Query Matching
```
Query: "What is the wake-up latency for sleep mode?"

Matches:
1. Chunk 2 (table) - Score: 0.89
   → Table contains "Wake-up Latency" column
   → Can cite exact table

2. Chunk 3 (text) - Score: 0.85
   → Contains "Wake-up from sleep requires..."
   → Provides context around latency
```

## Quality Assurance

### Token Counting Accuracy
```python
# Uses tiktoken for precise token counting
encoding = tiktoken.get_encoding("cl100k_base")
tokens = encoding.encode(text)
# Same tokenizer used by embedding model
```

### Validation Checks
1. **No empty chunks:** All chunks have content
2. **No orphaned metadata:** Every chunk has page numbers and doc_id
3. **Consistent encoding:** Same tokenizer throughout pipeline
4. **UUID uniqueness:** Every chunk has globally unique ID

## Performance Characteristics

### Your eMMC Document
```
Input: 352 pages, 9,371 elements
Output: 382 chunks

Average chunk size: ~24 elements per chunk
Size distribution:
  - Tables: 1-30 chunks (varies by size)
  - Text: 380-450 tokens per chunk
  - Mixed: 300-500 tokens per chunk
```

### Processing Speed
- **Parsing:** ~17 seconds (9,371 elements)
- **Chunking:** ~0.2 seconds (382 chunks)
- **Embedding:** ~14 seconds (382 embeddings)
- **Total:** ~35 seconds for 352-page document

## Advantages Over Alternatives

### vs. Fixed-Size Character Chunking ❌
```
Fixed (1000 chars):
  "...maximum transfer rate is 200MB/s. 4.3 Powe"  ← Splits mid-word!
  "r Management The device supports three pow..."

Ours (semantic):
  "...maximum transfer rate is 200MB/s."
  "4.3 Power Management. The device supports..."   ← Clean boundaries ✅
```

### vs. Sentence-Based Chunking ❌
```
Sentence-based:
  - Loses document structure
  - Tables become sentence soup
  - No section context

Ours:
  - Preserves hierarchy ✅
  - Tables intact ✅
  - Full section paths ✅
```

### vs. Paragraph-Based Chunking ⚠️
```
Paragraph-based:
  - Better than sentences
  - Still loses hierarchy
  - Variable chunk sizes (10-2000 tokens)

Ours:
  - Consistent sizes (500 ± overlap) ✅
  - Hierarchy preserved ✅
  - Controlled overlap ✅
```

## Future Enhancements

Potential improvements for production:

1. **Hierarchical Chunking:**
   - Parent chunks (full sections)
   - Child chunks (paragraphs)
   - Multi-level retrieval

2. **Semantic Similarity Splitting:**
   - Use embeddings to detect topic shifts
   - Split even within size limits if topic changes

3. **Cross-References:**
   - Link "See Section 4.3" to actual Section 4.3 chunk
   - Graph-based navigation

4. **Adaptive Chunk Sizes:**
   - Smaller chunks for dense technical content
   - Larger chunks for explanatory text

## Summary

**Context Integrity is Guaranteed By:**

✅ **Structure Preservation:** Elements are atomic units, never split
✅ **Table Protection:** Tables always kept whole, regardless of size
✅ **Chunk Overlap:** 50-token overlap ensures continuity
✅ **Rich Metadata:** Page numbers, sections, hierarchy all tracked
✅ **Element-Type Awareness:** Know what's in each chunk
✅ **Precise Token Counting:** Consistent tokenization throughout

**Result:** High-precision retrieval with full citation traceability and zero information loss.

---

**Related Files:**
- Implementation: `src/ingestion/chunker.py`
- PDF Parsing: `src/ingestion/pdf_parser.py`
- Data Models: `src/models/schemas.py`
- Configuration: `.env` (CHUNK_SIZE, CHUNK_OVERLAP)
