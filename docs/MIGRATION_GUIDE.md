## TOC-Based Chunking Migration Guide

**Date**: 2026-02-15
**Purpose**: Replace old chunking system with TOC-based chunker
**Estimated Time**: ~5 minutes

---

## Quick Start (TL;DR)

```bash
# 1. Delete old chunks
python src/ingestion/ingest_spec_toc.py delete --doc-id "emmc_v5.1_<hash>"

# 2. Re-ingest with new chunker
python src/ingestion/ingest_spec_toc.py ingest \
  --file specs/emmc5.1-protocol-JESD84-B51.pdf \
  --protocol "eMMC" \
  --version "5.1"

# 3. Verify in UI
streamlit run app.py
# Search for: "HS400 timing mode"
# Verify: Section 6.6.2.3 appears with subtitle
```

---

## Detailed Migration Steps

### Step 1: Check Current Documents

First, see what documents are currently ingested:

```bash
python src/ingestion/ingest_spec_toc.py list
```

**Expected Output:**
```
Found 1 document(s):
--------------------------------------------------------------------------------
Protocol        Version    Title                          Pages    Chunks   Uploaded
--------------------------------------------------------------------------------
eMMC            5.1        emmc5.1-protocol-JESD84-B51    258      1061     2026-02-12 10:30:00
--------------------------------------------------------------------------------
```

### Step 2: Get Document ID

From the list above, note the document ID pattern. You can also get it programmatically:

```bash
# Option A: List documents and copy the doc_id
python src/ingestion/ingest_spec_toc.py list

# Option B: Check SQLite directly
sqlite3 data/metadata.db "SELECT doc_id, protocol, version FROM documents WHERE is_active = 1;"
```

### Step 3: Delete Old Document

Delete the old document (this removes vectors from Qdrant and marks inactive in SQLite):

```bash
python src/ingestion/ingest_spec_toc.py delete --doc-id "emmc_v5.1_<hash>"
```

**Note**: Replace `<hash>` with the actual hash from your doc_id.

**Alternative**: If you want to keep the old document as backup, you can use Qdrant dashboard to manually create a new collection first.

### Step 4: Re-ingest with TOC-Based Chunker

Run the new ingestion pipeline:

```bash
python src/ingestion/ingest_spec_toc.py ingest \
  --file specs/emmc5.1-protocol-JESD84-B51.pdf \
  --protocol "eMMC" \
  --version "5.1" \
  --page-offset 20 \
  --chunk-size 350 \
  --max-chunk-size 800
```

**Expected Output:**
```
Starting TOC-based ingestion of specs/emmc5.1-protocol-JESD84-B51.pdf
Generated doc_id: emmc_v5.1_<new_hash>
Step 1/3: Running TOC-based chunking pipeline...
Phase 1: Extracting TOC...
  ✓ Extracted 351 TOC entries
Phase 2: Preprocessing TOC...
  ✓ Processed 400 entries (incl. 49 inferred)
Phase 3: Finding subsections with bounded regex...
  ✓ Found 44 subsections
Phase 4: Extracting content and detecting subtitles...
  ✓ Extracted content for 444 sections
Phase 5: Applying intelligent truncation...
  ✓ Created 561 final chunks
  ✓ Generated 561 raw chunks
Step 2/3: Converting to Chunk objects and filtering...
  ✓ Filtered to 355 chunks (removed 206 empty)
Step 3/3: Generating embeddings and storing...
Step 4/4: Storing document metadata...

Chunking Statistics:
  Total chunks: 355
  Total content: 740,530 chars (185,003 tokens)
  Average chunk: 330 tokens
  Chunks with subtitles: 224 (63.1%)
  Split chunks: 171
  Regex-found chunks: 46

✓ Successfully ingested document emmc_v5.1_<hash> (355 chunks, 258 pages)

✓ Document ingested successfully using TOC-based chunking!
  Document ID: emmc_v5.1_<hash>
  Protocol: eMMC v5.1

Note: This used the new TOC-based chunker with:
  - 98.6% section coverage
  - Subtitle detection enabled
  - Intelligent truncation
```

### Step 5: Verify in Streamlit UI

1. **Start Streamlit:**
   ```bash
   streamlit run app.py
   ```

2. **Test Critical Query:**
   - Query: `"HS400 timing mode selection"`
   - **Expected**: Section 6.6.2.3 appears in results
   - **Verify**: Subtitle "HS400" is displayed
   - **Verify**: Page citation (page 46) is correct

3. **Test Additional Queries:**
   - `"high speed mode"` → Should find 6.6.2.1 with "HS200" subtitle
   - `"block read"` → Should find 6.6.7.1
   - `"bus initialization"` → Should find section 6.1

4. **Check Metadata:**
   - Total chunks should be ~355 (vs 1,061 before)
   - Average chunk size ~330 tokens
   - Subtitles should appear in results

### Step 6: Validate Results

Run a quick validation script:

```bash
# Check Qdrant collection
python -c "
from src.database.qdrant_client import QdrantVectorStore
vs = QdrantVectorStore()
info = vs.client.get_collection('protocol_specs')
print(f'Total vectors: {info.points_count}')
print(f'Collection status: {info.status}')
"
```

**Expected Output:**
```
Total vectors: 355
Collection status: green
```

---

## Configuration Options

### Page Offset (--page-offset)

The page offset is the difference between document page numbers (printed on pages) and PDF page numbers.

**Default**: 20 (for eMMC 5.1 spec)

**How to find offset**:
1. Open PDF in viewer
2. Look at TOC: note a section's page number (e.g., page 43)
3. Navigate to that page in PDF viewer
4. Check PDF page number (e.g., PDF page 63)
5. Offset = PDF page - TOC page = 63 - 43 = 20

**If offset is wrong, you'll see:**
- Empty content extraction warnings
- 0 subsections found
- Many chunks with no content

### Chunk Size Parameters

```bash
--chunk-size 350        # Target size (tokens)
--max-chunk-size 800    # Hard limit before splitting (tokens)
```

**Recommendations**:
- **Small chunks (200-400)**: Better for precise retrieval, more chunks
- **Medium chunks (400-600)**: Balanced approach (recommended)
- **Large chunks (600-800)**: More context, fewer chunks

**Trade-offs**:
- Smaller chunks: Better retrieval precision, less context
- Larger chunks: More context, potentially less precise

**Our choice**: 350 target, 800 max (good balance)

---

## Troubleshooting

### Issue 1: Import Error

**Error:**
```
ModuleNotFoundError: No module named 'src.ingestion.toc_chunker'
```

**Solution:**
```bash
# Ensure you're in the project root
cd /Users/xiaowang/Documents/Projects/storage-protocol-assistant

# Run from project root
python -m src.ingestion.ingest_spec_toc list
```

### Issue 2: Empty Chunks

**Symptom:** Many "No content extracted" warnings

**Causes:**
1. Wrong page offset
2. PDF extraction issues
3. Sections are appendices/tables

**Solution:**
```bash
# Try debugging page content
python scripts/debug_section_text.py

# Adjust page offset if needed
python src/ingestion/ingest_spec_toc.py ingest \
  --page-offset 15 \  # Try different offset
  ...
```

### Issue 3: Qdrant Connection Error

**Error:**
```
QdrantConnectionError: Connection refused
```

**Solution:**
```bash
# Check if Qdrant is running
docker-compose ps

# If not running, start services
docker-compose up -d qdrant

# Verify connection
curl http://localhost:6333/collections
```

### Issue 4: SQLite Lock Error

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
```bash
# Close any open database connections
# Restart the application
docker-compose restart app
```

### Issue 5: Too Many Oversized Chunks

**Symptom:** >10% of chunks exceed max_chunk_size

**Solution:**
```bash
# Reduce max_chunk_size
python src/ingestion/ingest_spec_toc.py ingest \
  --max-chunk-size 600 \  # Lower limit
  ...
```

---

## Comparison: Before vs After

### Metrics Comparison

| Metric | Old Chunker | TOC Chunker | Change |
|--------|-------------|-------------|--------|
| **Total Chunks** | 1,061 | 355 | -66% ⬇️ |
| **Avg Tokens/Chunk** | ~200 | ~330 | +65% ⬆️ |
| **Section Coverage** | 71.9% | 98.6% | +27% ⬆️ |
| **Subtitle Detection** | 0% | 63% | +63% ⬆️ |
| **Chunks >800 tokens** | Unknown | 3.4% | Controlled ✅ |
| **Empty Chunks** | Unknown | 37% | Filterable ✅ |

### Quality Improvements

**Before (Old Chunker):**
```
❌ Section 6.6.2.3 missing subtitle "HS400"
❌ Incomprehensible math formula titles
❌ Arbitrary chunk boundaries
❌ No section structure preservation
❌ Poor retrieval precision
```

**After (TOC Chunker):**
```
✅ Section 6.6.2.3 with "HS400" subtitle
✅ Clean, readable titles
✅ Semantic chunk boundaries
✅ Complete section structure
✅ Better retrieval with context
```

---

## Rollback Plan

If you need to revert to the old chunker:

### Option 1: Keep Both Documents

```bash
# Don't delete old document in Step 3
# Keep old doc_id for rollback

# To rollback: delete new document
python src/ingestion/ingest_spec.py delete --doc-id "emmc_v5.1_<new_hash>"
```

### Option 2: Re-ingest with Old Chunker

```bash
# Use original ingestion script
python src/ingestion/ingest_spec.py ingest \
  --file specs/emmc5.1-protocol-JESD84-B51.pdf \
  --protocol "eMMC" \
  --version "5.1" \
  --strategy "fast"
```

---

## Next Steps

After successful migration:

1. **Test Queries**
   - Run sample queries in UI
   - Verify subtitle detection
   - Check page citations

2. **Monitor Performance**
   - Query response time
   - Retrieval quality
   - User feedback

3. **Expand to Other Specs**
   - UFS specifications
   - SD card specifications
   - Other storage protocols

4. **Future Enhancements**
   - Table extraction (Camelot)
   - Diagram understanding (DeepSeek-VL2)
   - Cross-reference resolution

---

## FAQ

**Q: Why fewer chunks (355 vs 1,061)?**
A: TOC chunker creates semantic chunks aligned with document sections, not arbitrary splits. Each chunk has more context.

**Q: What happens to empty chunks (37%)?**
A: They're filtered out during ingestion (< 50 chars). Most are parent sections containing only subsections.

**Q: Can I adjust chunk sizes after ingestion?**
A: No, you need to re-ingest with different parameters. Chunk size is determined at ingestion time.

**Q: Does this work for all PDFs?**
A: Best for structured technical documents with TOC. May not work well for:
- Documents without TOC
- Scanned PDFs (OCR needed)
- Image-heavy documents

**Q: How long does ingestion take?**
A: ~2-3 minutes for eMMC 5.1 spec (258 pages):
- TOC extraction: ~3s
- Regex search: ~32s
- Content extraction: ~90s
- Embedding generation: ~30s

**Q: Can I run both chunkers side-by-side?**
A: Yes, but they need separate doc_ids. Use different version strings or protocols to distinguish.

---

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review test scripts: `scripts/test_toc_phase*.py`
3. Check logs: `docker-compose logs app`
4. Verify Qdrant: http://localhost:6333/dashboard

---

**Migration Status**: Ready for production use ✅
**Last Updated**: 2026-02-15
**Version**: 1.0.0
