# Section Title Extraction Issues & Solutions

## Problem Summary

The current section title extraction has **3 major issues**:

### Issue 1: Figure/Table Captions as Section Titles ❌
```
Current behavior:
section_title: "Figure 20 — e•MMC state diagram (boot mode)"

Expected:
section_title: "6.3.3 Boot operation"
```

**Root Cause:** Unstructured.io classifies figure/table captions as `Title` elements, and our parser blindly accepts all titles.

### Issue 2: Short/Meaningless Titles ❌
```
Examples found in your eMMC spec:
- "1b"
- "4KB"
- "CMD0"
- "RW1C"
- "Tables"
```

**Root Cause:** No validation on title quality or length.

### Issue 3: Incomplete/Overly Long Titles ❌
```
Too short: "1b"
Too long: "NORMAL(Field) PRE_SOLDERING_WRITES PRE_SOLDERING_POST_WRITES AUTO_PRE_SOLDERING Reserved..."
```

**Root Cause:** No content-based filtering or cleaning.

## Impact on RAG System

### Citation Quality Degraded
```
❌ Current:
"According to eMMC spec, section 'Figure 20', page 49..."

✅ Should be:
"According to eMMC spec, section 6.3.3 (Boot Operation), page 49..."
```

### Context Loss
```
Chunk with section_title = "4KB"
↓
User asks: "What is this about?"
↓
System cannot provide meaningful section context
```

### Retrieval Confusion
```
Query: "boot operation states"
Chunk 1: section = "6.3.3 Boot operation" ✅ Good
Chunk 2: section = "Figure 20" ❌ Misleading
```

## Analysis of Your eMMC Document

From the 382 chunks ingested, here's the breakdown:

### Title Quality Distribution
```
Good Section Titles:  ~25 unique (~40% of chunks)
  ✅ "6.6.21 Sleep (CMD5)"
  ✅ "6.3.3 Boot operation"
  ✅ "B.2.6 Queue-Barrier Tasks"

Figure Captions: ~15 unique (~25% of chunks)
  ❌ "Figure 20 — e•MMC state diagram"
  ❌ "Figure B.111 — Command Queuing HCI"
  ❌ "Figure 45 — Block write command timing"

Table References: ~8 unique (~15% of chunks)
  ❌ "Table 76 — Device Types"
  ❌ "Table 139 — Extended CSD revisions"
  ❌ "Tables"

Short/Meaningless: ~12 unique (~20% of chunks)
  ❌ "1b", "4KB", "CMD0", "RW1C"
```

**Impact:** ~60% of chunks have suboptimal section titles!

## Root Cause Analysis

### Current Implementation (pdf_parser.py, lines 83-96)

```python
# Update section tracking for headings
if isinstance(element, Title):
    current_section = element.text  # ❌ No validation!
    level = self._estimate_heading_level(element.text)  # ❌ Crude heuristic

    # Update hierarchy
    if level == 1:
        section_hierarchy = [element.text]
    # ...
```

**Problems:**
1. ✅ Detects all `Title` elements
2. ❌ No filtering of figure/table captions
3. ❌ No validation of title quality
4. ❌ Level estimation based only on text length
5. ❌ No section number recognition

### What Unstructured.io Returns

The library classifies these as `Title`:
- ✅ Actual headings: "6.3.3 Boot operation"
- ❌ Figure captions: "Figure 20 — State diagram"
- ❌ Table titles: "Table 76 — Device Types"
- ❌ Generic labels: "Tables", "Figures"
- ❌ Random text: "1b", "4KB"

**We must filter these!**

## Solution: Intelligent Section Title Extraction

I've created `pdf_parser_improved.py` with a **3-layer validation** approach:

### Layer 1: Exclusion Patterns
```python
EXCLUDE_PATTERNS = [
    r'^Figure\s+\d+',       # Figure 20, Figure B.111
    r'^Table\s+\d+',        # Table 76, Table 139
    r'^Figures?$',          # "Figure", "Figures"
    r'^Tables?$',           # "Table", "Tables"
    r'^Contents?$',         # Table of contents
    r'^Page\s+\d+',         # Page numbers
    r'^Reserved',           # Reserved fields
    r'^\w{1,3}$',           # Very short (1-3 chars)
]
```

### Layer 2: Section Pattern Recognition
```python
SECTION_PATTERNS = [
    r'^\d+\.\d+\.?\d*\s+\w+',   # "6.3.3 Boot operation" ✅
    r'^[A-Z]\.\d+\.?\d*\s+\w+', # "B.2.6 Queue-Barrier" ✅
    r'^Chapter\s+\d+',          # "Chapter 4" ✅
    r'^Appendix\s+[A-Z]',       # "Appendix B" ✅
    r'^Section\s+\d+',          # "Section 4" ✅
]
```

### Layer 3: Quality Heuristics
```python
def _is_valid_section_title(text: str) -> bool:
    # Length check
    if len(text) < 3 or len(text) > 120:
        return False

    # Must have letters
    if not any(c.isalpha() for c in text):
        return False

    # Not too many words (>15 suggests paragraph, not heading)
    if len(text.split()) > 15:
        return False

    # Match against patterns...
```

## Before vs After Comparison

### Example 1: Boot Operation Section

**Before (Current):**
```
Element: Title("Figure 20 — e•MMC state diagram (boot mode)")
↓
section_title: "Figure 20 — e•MMC state diagram (boot mode)" ❌
section_path: "6.3.3 Boot operation > Figure 20..." ❌

Citation: "eMMC spec, Figure 20, page 49" ❌ Wrong!
```

**After (Improved):**
```
Element: Title("Figure 20 — e•MMC state diagram (boot mode)")
↓
Validation: Matches r'^Figure\s+\d+' → REJECTED
Keep last valid section: "6.3.3 Boot operation" ✅
↓
section_title: "6.3.3 Boot operation" ✅
section_path: "Chapter 6 > Boot Operations > 6.3.3 Boot operation" ✅

Citation: "eMMC spec, Section 6.3.3 (Boot operation), page 49" ✅ Correct!
```

### Example 2: Command Queuing

**Before:**
```
section_title: "Figure B.111 — Command Queuing HCI General Architecture" ❌
```

**After:**
```
Element: Title("Figure B.111...")
Validation: Excluded (figure caption)
↓
Retain: "B.2.6 Queue-Barrier Tasks" ✅
```

### Example 3: Short Noise

**Before:**
```
section_title: "1b" ❌
section_title: "4KB" ❌
section_title: "CMD0" ❌
```

**After:**
```
Validation: Length < 3 or no alphanumeric pattern → REJECTED
↓
Retain last valid section ✅
```

## Implementation Strategy

### Option 1: Replace Current Parser ⚠️
```bash
# Backup current
mv src/ingestion/pdf_parser.py src/ingestion/pdf_parser_old.py

# Use improved version
mv src/ingestion/pdf_parser_improved.py src/ingestion/pdf_parser.py

# Rebuild and re-ingest
docker-compose build app
make ingest FILE=/app/specs/emmc5.1-protocol-JESD84-B51.pdf ...
```

**Pros:** Clean break, immediate improvement
**Cons:** Requires re-ingesting all documents

### Option 2: Side-by-Side Comparison (Recommended)
```python
# Test both parsers
from src.ingestion.pdf_parser import PDFParser
from src.ingestion.pdf_parser_improved import ImprovedPDFParser

old_parser = PDFParser()
new_parser = ImprovedPDFParser()

old_elements = old_parser.parse_pdf("spec.pdf")
new_elements = new_parser.parse_pdf("spec.pdf")

# Compare section title quality
compare_section_titles(old_elements, new_elements)
```

**Pros:** Risk-free testing, can compare quality
**Cons:** Requires test harness

### Option 3: Gradual Migration
1. Keep current parser for existing docs
2. Use improved parser for new ingestions
3. Eventually re-ingest all with improved parser

## Configuration Options

The improved parser can be configured:

```python
# In .env or config
EXCLUDE_FIGURE_CAPTIONS=true
EXCLUDE_TABLE_CAPTIONS=true
MIN_SECTION_TITLE_LENGTH=5
MAX_SECTION_TITLE_LENGTH=100
REQUIRE_SECTION_NUMBERS=false  # Strict: only numbered sections
```

## Testing & Validation

### Test Suite for Section Titles

```python
# tests/test_section_titles.py

def test_excludes_figure_captions():
    parser = ImprovedPDFParser()
    is_valid, _ = parser._is_valid_section_title("Figure 20 — State diagram")
    assert not is_valid

def test_accepts_numbered_sections():
    parser = ImprovedPDFParser()
    is_valid, info = parser._is_valid_section_title("6.3.3 Boot operation")
    assert is_valid
    assert info['level'] == 3  # Section level

def test_rejects_short_noise():
    parser = ImprovedPDFParser()
    assert not parser._is_valid_section_title("1b")[0]
    assert not parser._is_valid_section_title("4KB")[0]
```

### Quality Metrics

After re-ingesting with improved parser:

```
Expected improvements:
- Valid section titles: 40% → 85%+
- Figure captions as titles: 25% → 0%
- Meaningless titles: 20% → <5%
- Citation accuracy: Moderate → High
```

## Post-Ingestion Fixes

If you don't want to re-ingest, you can **post-process** existing chunks:

```python
from qdrant_client import QdrantClient

client = QdrantClient(url='http://qdrant:6333')

# Get all points
points = client.scroll(
    collection_name='protocol_specs',
    limit=1000,
    with_payload=True
)

# Fix section titles
for point in points[0]:
    section = point.payload.get('section_title', '')

    # Detect and fix figure captions
    if section.startswith('Figure'):
        # Extract section from path or set to None
        path = point.payload.get('section_path', '')
        if ' > ' in path:
            # Get parent section from path
            parent = path.split(' > ')[-2]
            point.payload['section_title'] = parent

    # Update point
    client.upsert(
        collection_name='protocol_specs',
        points=[point]
    )
```

**Warning:** This is a workaround. Better to re-ingest with improved parser.

## Recommendations

### Short Term (Quick Fix)
1. ✅ Keep current ingestion
2. ✅ Document the limitation
3. ✅ Use section_path when section_title is unreliable
4. ✅ Post-process specific problematic titles

### Medium Term (Recommended)
1. ✅ Test improved parser on sample documents
2. ✅ Compare quality metrics (old vs new)
3. ✅ Re-ingest eMMC spec with improved parser
4. ✅ Validate citation quality improves

### Long Term (Production)
1. ✅ Add section title quality scoring
2. ✅ Implement machine learning-based section detection
3. ✅ Add user feedback loop for title corrections
4. ✅ Consider hierarchical document models (DocLing, Marker)

## Alternative Approaches

### Approach 1: Regex-Based Post-Processing
```python
def clean_section_title(title: str) -> str:
    # Remove figure/table prefixes
    title = re.sub(r'^(Figure|Table)\s+\d+\s*[—-]\s*', '', title)

    # Extract section number if present
    match = re.match(r'^(\d+\.\d+\.?\d*)\s+(.+)', title)
    if match:
        return f"{match.group(1)} {match.group(2)}"

    return title
```

### Approach 2: Use Alternative PDF Parser
- **PyMuPDF (fitz):** Better structure detection
- **PDFMiner.six:** Detailed text extraction
- **Marker:** ML-based PDF to Markdown with structure
- **DocLing:** IBM's document understanding library

### Approach 3: Manual Section Mapping
For critical specs, maintain a manual mapping:
```python
SECTION_OVERRIDES = {
    "emmc_5.1": {
        (page=49, text_starts_with="Figure 20"): "6.3.3 Boot operation",
        (page=319, text_starts_with="Figure B.111"): "B.2.6 Queue-Barrier Tasks",
    }
}
```

## Summary

**Current State:**
- ❌ 60% of chunks have suboptimal section titles
- ❌ Figure/table captions used as section titles
- ❌ Short meaningless titles ("1b", "4KB")
- ❌ Citations reference wrong sections

**Improved Parser Benefits:**
- ✅ Pattern-based filtering (figures, tables excluded)
- ✅ Section number recognition (6.3.3, B.2.6)
- ✅ Quality validation (length, content checks)
- ✅ Better citation accuracy

**Action Items:**
1. Review `pdf_parser_improved.py`
2. Test on sample document
3. Compare section title quality
4. Decide: re-ingest or post-process?
5. Update production pipeline

---

**Files:**
- Current: `src/ingestion/pdf_parser.py`
- Improved: `src/ingestion/pdf_parser_improved.py`
- Tests: `tests/test_section_titles.py` (to be created)
- Analysis: This document
