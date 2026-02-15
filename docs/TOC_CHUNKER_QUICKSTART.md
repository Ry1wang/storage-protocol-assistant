# TOC-Based Chunker - Quick Start Guide

**Status**: ✅ Production Ready
**Use Case**: Technical documents with table of contents (protocol specs, standards, manuals)

---

## 🚀 Quick Usage

### Re-ingest eMMC 5.1 Spec (Recommended)

```bash
# 1. Delete old document (find doc_id with 'list' command)
python src/ingestion/ingest_spec_toc.py list
python src/ingestion/ingest_spec_toc.py delete --doc-id "emmc_v5.1_<hash>"

# 2. Ingest with new TOC chunker
python src/ingestion/ingest_spec_toc.py ingest \
  --file specs/emmc5.1-protocol-JESD84-B51.pdf \
  --protocol "eMMC" \
  --version "5.1"

# 3. Verify
streamlit run app.py
# Search: "HS400 timing mode"
# Expected: Section 6.6.2.3 with subtitle "HS400"
```

---

## 📊 What You Get

**Before (Old Chunker):**
- 1,061 chunks
- ~200 tokens/chunk
- 71.9% section coverage
- 0% subtitle detection
- ❌ Section 6.6.2.3 missing "HS400" subtitle

**After (TOC Chunker):**
- 355 chunks (-66%)
- ~330 tokens/chunk (+65%)
- 98.6% section coverage (+27%)
- 63% subtitle detection (+63%)
- ✅ Section 6.6.2.3 with "HS400" subtitle

---

## 🎯 Key Features

1. **TOC Extraction** - Extracts 351 sections from table of contents
2. **Bounded Regex Search** - Finds 44 additional subsections not in TOC
3. **Subtitle Detection** - Detects subtitles in 63% of sections
4. **Intelligent Truncation** - Splits long sections with context overlap
5. **Section-Aware** - Preserves document structure

---

## 🔧 Configuration

### Basic (Recommended)
```bash
python src/ingestion/ingest_spec_toc.py ingest \
  --file path/to/spec.pdf \
  --protocol "eMMC" \
  --version "5.1"
```

### Advanced
```bash
python src/ingestion/ingest_spec_toc.py ingest \
  --file path/to/spec.pdf \
  --protocol "eMMC" \
  --version "5.1" \
  --page-offset 20 \         # Document page vs PDF page offset
  --chunk-size 350 \         # Target chunk size (tokens)
  --max-chunk-size 800       # Maximum before splitting (tokens)
```

---

## 📝 Testing

All phases tested and validated:

```bash
# Test individual phases
python scripts/test_toc_phase1.py  # TOC extraction
python scripts/test_toc_phase2.py  # Regex search
python scripts/test_toc_phase3.py  # Content extraction
python scripts/test_toc_phase4.py  # Truncation
python scripts/test_toc_phase5.py  # Full pipeline

# All tests should pass ✅
```

---

## 🐛 Troubleshooting

### Issue: Empty chunks warning
**Solution**: Check page offset, try `--page-offset 15` or `--page-offset 25`

### Issue: Import error
**Solution**: Run from project root: `cd /Users/xiaowang/Documents/Projects/storage-protocol-assistant`

### Issue: Qdrant connection error
**Solution**: `docker-compose up -d qdrant && sleep 5`

---

## 📚 Documentation

- **Full Summary**: `TOC_CHUNKER_SUMMARY.md` (comprehensive overview)
- **Migration Guide**: `MIGRATION_GUIDE.md` (step-by-step instructions)
- **Implementation Plan**: `IMPLEMENTATION_PLAN.md` (development roadmap)
- **Analysis**: `CHUNKING_ANALYSIS.md` (detailed analysis)

---

## ✅ Success Criteria

- [x] Section 6.6.2.3 has "HS400" subtitle
- [x] 98.6% section coverage
- [x] 63% subtitle detection rate
- [x] 96.6% chunks within 800 tokens
- [x] All 5 phases tested and passing

---

**Status**: Production Ready ✅
**Last Updated**: 2026-02-15
**Next**: Re-ingest eMMC 5.1 spec and validate in UI
