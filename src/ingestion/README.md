# Document Ingestion Pipeline

This module handles the ingestion of protocol specification documents (PDFs) into the RAG system.

## Overview

The ingestion pipeline consists of three main components:

1. **PDF Parser** (`pdf_parser.py`) - Extracts structured content from PDF files
2. **Chunker** (`chunker.py`) - Splits documents into semantic chunks with metadata
3. **Ingestion Orchestrator** (`ingest_spec.py`) - Coordinates the pipeline and stores data

## Quick Start

### Using Docker (Recommended)

```bash
# Start services
docker-compose up -d

# Ingest a document
make ingest FILE=/path/to/spec.pdf PROTOCOL=eMMC VERSION=5.1

# Or use docker-compose directly
docker-compose exec app python -m src.ingestion.ingest_spec ingest \
  --file /app/specs/emmc_5.1.pdf \
  --protocol eMMC \
  --version 5.1 \
  --title "eMMC 5.1 Specification"

# List ingested documents
make list
```

### Using Python Directly

```python
from src.ingestion.ingest_spec import SpecificationIngester

# Initialize ingester
ingester = SpecificationIngester()

# Ingest a document
doc_id = ingester.ingest_document(
    file_path="/path/to/spec.pdf",
    protocol="eMMC",
    version="5.1",
    title="eMMC 5.1 Specification",  # Optional
    strategy="fast"  # or "hi_res" for OCR
)

# List documents
ingester.list_documents()

# Delete a document
ingester.delete_document(doc_id)
```

## Components

### PDF Parser

Extracts structured elements from PDF files using Unstructured.io.

**Features:**
- Identifies headings, paragraphs, lists, tables, and figure captions
- Preserves document structure and hierarchy
- Extracts page numbers for each element
- Builds section paths for context

**Parsing Strategies:**
- `fast` - Text extraction only (default, faster)
- `hi_res` - OCR + table structure detection (slower, more accurate)

**Usage:**
```python
from src.ingestion.pdf_parser import PDFParser

parser = PDFParser()
elements = parser.parse_pdf("spec.pdf", strategy="fast")

# Each element contains:
# - text: The element content
# - type: heading, text, table, list_item, figure_caption
# - page_numbers: List of page numbers
# - section_title: Current section title
# - section_path: Full section hierarchy
```

### Semantic Chunker

Splits parsed elements into semantically coherent chunks.

**Features:**
- Respects document structure (doesn't split mid-section)
- Preserves large tables as single chunks
- Token-based chunking with configurable size and overlap
- Maintains metadata (page numbers, sections, types)

**Configuration:**
```python
from src.ingestion.chunker import SemanticChunker

chunker = SemanticChunker(
    chunk_size=500,      # Target chunk size in tokens
    chunk_overlap=50,    # Overlap between chunks
)

chunks = chunker.chunk_elements(elements, doc_id="emmc_5_1_abc123")

# Each chunk contains:
# - text: Combined text from multiple elements
# - metadata: ChunkMetadata with page numbers, sections, etc.
# - embedding: Will be generated during storage
```

### Ingestion Orchestrator

Coordinates the full pipeline from PDF to vector storage.

**Pipeline Steps:**
1. Parse PDF into structured elements
2. Chunk elements semantically
3. Generate embeddings and store in Qdrant
4. Store metadata in SQLite

**CLI Commands:**

```bash
# Ingest a document
python -m src.ingestion.ingest_spec ingest \
  --file /path/to/spec.pdf \
  --protocol eMMC \
  --version 5.1 \
  --title "eMMC Specification v5.1" \
  --strategy fast

# List all documents
python -m src.ingestion.ingest_spec list

# Delete a document
python -m src.ingestion.ingest_spec delete --doc-id emmc_5_1_abc123
```

## Configuration

Settings are loaded from environment variables (`.env` file):

```bash
# Chunk size in tokens (default: 500)
CHUNK_SIZE=500

# Overlap between chunks in tokens (default: 50)
CHUNK_OVERLAP=50

# Embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Qdrant connection
QDRANT_URL=http://qdrant:6333
```

## Data Storage

### Qdrant (Vector Store)

Chunks are stored in the `protocol_specs` collection with:
- **Vector**: Sentence embedding (384 dimensions for MiniLM)
- **Payload**:
  - `text`: Chunk text
  - `doc_id`: Document ID
  - `chunk_id`: Unique chunk ID
  - `page_numbers`: List of page numbers
  - `section_title`: Current section
  - `section_path`: Full section hierarchy
  - `chunk_type`: text, table, figure_caption

### SQLite (Metadata Store)

Document metadata is stored in the `documents` table:
- `doc_id`: Unique document ID
- `title`: Document title
- `protocol`: Protocol name (eMMC, UFS, etc.)
- `version`: Protocol version
- `file_path`: Original file path
- `uploaded_at`: Upload timestamp
- `total_pages`: Number of pages
- `total_chunks`: Number of chunks created
- `is_active`: Active status (for soft deletes)

## Document ID Format

Document IDs are generated as: `{protocol}_{version}_{file_hash}`

Example: `eMMC_5_1_a1b2c3d4`

This ensures:
- Unique IDs for each document
- Same file can't be uploaded twice
- Easy to identify protocol and version

## Example Workflow

```bash
# 1. Start services
docker-compose up -d

# 2. Place your PDF in the specs directory
mkdir -p specs
cp /path/to/emmc_spec.pdf specs/

# 3. Ingest the document
make ingest FILE=/app/specs/emmc_spec.pdf PROTOCOL=eMMC VERSION=5.1

# 4. Verify ingestion
make list

# Output:
# Found 1 document(s):
# --------------------------------
# Protocol  Version  Title         Pages  Chunks  Uploaded
# --------------------------------
# eMMC      5.1      emmc_spec     512    1024    2026-02-14 10:30:00
```

## Troubleshooting

### Issue: "No elements extracted from PDF"
- **Cause**: PDF may be scanned image without text layer
- **Solution**: Use `--strategy hi_res` for OCR

### Issue: "Failed to parse PDF"
- **Cause**: Corrupted or encrypted PDF
- **Solution**: Check PDF file integrity, decrypt if encrypted

### Issue: "Out of memory during ingestion"
- **Cause**: Large PDF file
- **Solution**: Reduce `CHUNK_SIZE` or process in batches

### Issue: "Qdrant connection refused"
- **Cause**: Qdrant service not running
- **Solution**: Check `docker-compose ps`, restart with `docker-compose up -d`

## Performance Tips

1. **Use `fast` strategy** for most documents (10x faster)
2. **Batch processing**: Ingest multiple documents sequentially
3. **Chunk size**: Larger chunks = fewer embeddings = faster ingestion
4. **Monitor memory**: Large PDFs may require more RAM

## Next Steps

After ingesting documents, you can:
1. Query them using the Streamlit UI (http://localhost:8501)
2. Use the retrieval API for hybrid search
3. View data in Qdrant dashboard (http://localhost:6333/dashboard)

## Development

### Adding New Parsers

To add support for other file formats:

1. Create parser in `src/ingestion/`
2. Implement `parse_document()` returning list of elements
3. Register in `SpecificationIngester`

### Testing Ingestion

```bash
# Run ingestion tests
pytest tests/test_ingestion.py -v

# Test with sample PDF
python -m src.ingestion.ingest_spec ingest \
  --file tests/fixtures/sample.pdf \
  --protocol TEST \
  --version 1.0
```
