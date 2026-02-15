# Title-Number-Based Chunking Strategy - Detailed Analysis

**Date:** 2026-02-14
**Status:** Analysis Only (No Code Changes Yet)

---

## Problems Identified

### Problem 1: Missing Title Content

**Chunk ID:** `0490e4c3-b740-4996-b767-9b1fb8b03958`

**Current State:**
```
Section Title: "6.6.2.3 The valid IO Voltage for HS400 is 1.8 V or 1.2 V for VCCQ"
Page: 46

Text Content:
JEDEC Standard No. 84-B51 Page 46

6.6.2.3 The valid IO Voltage for HS400 is 1.8 V or 1.2 V for VCCQ.

"HS400" timing mode selection    ← SUBTITLE MISSING FROM TITLE!

The bus width is set to only DDR 8bit in HS400 mode.
...
```

**Root Cause:**
- The PDF has a **hierarchical structure**: Section 6.6.2.3 contains a subtitle
- Section number: `6.6.2.3`
- Main title: `The valid IO Voltage for HS400 is 1.8 V or 1.2 V for VCCQ`
- **Subtitle**: `"HS400" timing mode selection` (NOT captured in metadata!)

**Impact:**
- Users searching for "HS400 timing mode selection" won't find this chunk easily
- The section title is incomplete/misleading
- Semantic search quality is degraded

---

### Problem 2: Incomprehensible/Wrong Titles

**Chunk ID:** `0385db67-5c51-4d09-b767-1cfd4deb4073`

**Current State:**
```
Section Title: "+ CORRECTLY_PRG_SECTORS_NUM_0 * 2"    ← CLEARLY WRONG!
Section Path: "Bit[1:0]: OUTSTANDING > + CORRECTLY_PRG_SECTORS_NUM_0 * 2"
Page: 206

Text Content:
Number of correctly programmed sectors =
[CORRECTLY_PRG_SECTORS_NUM_3 * 2^24 + ...]

7.4.35 INI_TIMEOUT_AP [241]    ← ACTUAL SECTION NUMBER!
This register indicates the maximum initialization timeout...
```

**Root Cause:**
- PDF parser **misidentified a formula as a section title**
- The actual section is `7.4.35 INI_TIMEOUT_AP [241]`
- The parser picked up math notation (`+ CORRECTLY_PRG_SECTORS_NUM_0 * 2`) as the title
- This happens because the PDF structure is ambiguous (bold text, formatting, etc.)

**Impact:**
- Completely wrong metadata
- Impossible to cite correctly
- Breaks user trust
- Section hierarchy is corrupted

---

## Current Chunking Strategy Analysis

### How It Works Now

**Section-Aware Chunking (Current Implementation):**

1. **Parse PDF** → Extract elements with Unstructured.io
2. **Detect sections** → Look for elements with `category='Title'`
3. **Track section changes** → When section number changes at boundary level (e.g., 6.6.34 → 6.6.35)
4. **Split chunks** → Force split at major section boundaries
5. **Post-process** → Use LLM to correct bad titles (92.7% → 95.2% accuracy)

**Current Configuration:**
```python
CHUNKING_STRATEGY = "section_aware"
CHUNK_SIZE = 350 tokens (target)
MIN_CHUNK_SIZE = 100 tokens
MAX_CHUNK_SIZE = 800 tokens
SECTION_BOUNDARY_LEVELS = 3  # Split at 6.6.34 level
```

### Problems with Current Approach

#### 1. **Relies on PDF Parser Quality**
- Unstructured.io sometimes misidentifies titles
- Bold text, formulas, table headers get labeled as "Title"
- No way to validate if extracted title is correct

#### 2. **Heuristic-Based Section Detection**
- Looks for patterns like `6.6.2.3` in text
- But can't distinguish between:
  - Real section header: `6.6.2.3 The valid IO Voltage...`
  - Reference: `See section 6.6.2.3 for details`
  - Table cell: `6.6.2.3` in a specs table

#### 3. **Post-Processing Limitations**
- LLM correction helps (95.2% accuracy)
- But it's expensive ($0.04/doc) and not 100% accurate
- Can't fix problems that aren't in the text (like missing subtitles)

#### 4. **Mixed Content Still Possible**
- Chunks can still contain:
  - Section 6.6.2.3 title
  - Section 6.6.2.3 subtitle (not in metadata!)
  - Part of 6.6.2.4 content (if not split properly)

---

## Proposed: Title-Number-Based Chunking

### Core Idea

**Chunk STRICTLY by section numbers, not by heuristics or PDF structure.**

### How It Would Work

#### Step 1: Extract ALL Section Numbers from Text

Scan the entire PDF text and extract EVERY occurrence of section numbers:

```python
import re

# Pattern for section numbers
section_pattern = r'\b(\d+\.\d+(?:\.\d+)*)\s+([A-Z].*?)(?=\n|$)'

# Example matches:
# "6.6.2.3 The valid IO Voltage for HS400"
# "7.4.35 INI_TIMEOUT_AP [241]"
# "10.10.3 HS400 Device Command Output Timing"
```

#### Step 2: Build Section Hierarchy

Create a complete map of the document structure:

```python
sections = {
    '6': {'title': 'Device Command Set', 'start_page': 50, 'end_page': 150},
    '6.6': {'title': 'HS400 Mode', 'start_page': 60, 'end_page': 70},
    '6.6.2': {'title': 'HS400 Configuration', 'start_page': 65, 'end_page': 68},
    '6.6.2.3': {'title': 'The valid IO Voltage for HS400...', 'start_page': 66, 'end_page': 67},
    '7': {'title': 'Extended CSD Register', 'start_page': 151, 'end_page': 250},
    '7.4': {'title': 'Register Fields', 'start_page': 180, 'end_page': 220},
    '7.4.35': {'title': 'INI_TIMEOUT_AP [241]', 'start_page': 206, 'end_page': 207},
}
```

#### Step 3: Split Text by Section Boundaries

Extract text for each section number:

```python
def extract_section_content(pdf_text, section_number, sections_map):
    """
    Extract all text between section X.Y.Z and the next section at the same level.

    Example:
    - Section 6.6.2.3 → Extract until 6.6.2.4 or 6.6.3 or 6.7
    - Section 7.4.35 → Extract until 7.4.36 or 7.5
    """
    start_marker = f"{section_number} {sections_map[section_number]['title']}"
    next_section = get_next_section_at_same_or_higher_level(section_number, sections_map)
    end_marker = f"{next_section} {sections_map[next_section]['title']}"

    # Extract text between markers
    content = extract_text_between(pdf_text, start_marker, end_marker)

    return {
        'section_number': section_number,
        'section_title': sections_map[section_number]['title'],
        'content': content,
        'pages': sections_map[section_number]['pages']
    }
```

#### Step 4: Handle Subtitles Within Sections

Detect subtitles (like "HS400" timing mode selection) within sections:

```python
def detect_subtitles(section_content):
    """
    Look for quoted text or bold headers that appear to be subtitles.

    Example:
    "HS400" timing mode selection
    '''Enhanced Strobe mode'''
    **Important Note**
    """
    subtitle_patterns = [
        r'"([^"]+)"',  # Quoted text
        r"'''([^']+)'''",  # Triple-quoted
        r'\*\*([^\*]+)\*\*',  # Bold markdown
    ]

    subtitles = []
    for pattern in subtitle_patterns:
        matches = re.findall(pattern, section_content)
        subtitles.extend(matches)

    return subtitles
```

#### Step 5: Create Chunks with Complete Metadata

```python
chunk = {
    'section_number': '6.6.2.3',
    'section_title': 'The valid IO Voltage for HS400 is 1.8 V or 1.2 V for VCCQ',
    'subtitles': ['"HS400" timing mode selection'],  # NEW!
    'content': '...',
    'pages': [66, 67],
    'section_path': 'Chapter 6 > 6.6 HS400 Mode > 6.6.2 HS400 Configuration > 6.6.2.3',
    'section_level': 3,  # NEW!
    'parent_section': '6.6.2',  # NEW!
}
```

---

## Comparison: Current vs. Proposed

### Current Approach (Section-Aware with Heuristics)

#### Pros ✅
- Works with existing PDF parser (Unstructured.io)
- Fast implementation (already done)
- 95.2% accuracy after LLM correction
- Handles most common cases well

#### Cons ❌
- **Relies on PDF parser quality** (can misidentify titles)
- **Can't detect subtitles** (missing content like "HS400" timing mode selection)
- **Requires expensive post-processing** ($0.04/doc for LLM correction)
- **Heuristic-based** (section detection can fail)
- **Mixed content still possible** (~2% chunks)

### Proposed Approach (Title-Number-Based)

#### Pros ✅
- **100% accurate section boundaries** (based on actual section numbers in text)
- **Captures subtitles** (can detect quoted/bold text within sections)
- **No LLM correction needed** (titles extracted directly from document)
- **Deterministic** (same input → same output always)
- **Complete metadata** (section level, parent, hierarchy)
- **No mixed content** (each chunk = exactly one section)

#### Cons ❌
- **More complex implementation** (requires custom PDF text extraction)
- **Assumption dependency**: Assumes section numbers are **always** present in text
- **Edge cases**: What if section numbers are in tables/figures only?
- **Subtitle detection might fail** (not all subtitles are quoted or bold)
- **Longer development time** (need to build custom parser)
- **May create very small chunks** (some sections are only 1-2 sentences)

---

## Deep Dive: Proposed Implementation Strategy

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     PDF Document                                 │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Full Text Extraction (pdfplumber or PyMuPDF)           │
│  - Extract ALL text with page numbers                           │
│  - Preserve formatting metadata (bold, size, etc.)               │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Section Number Detection                               │
│  - Regex: r'\b(\d+\.\d+(?:\.\d+)*)\s+([A-Z].*?)(?=\n|$)'       │
│  - Build section map: {number: {title, pages, level}}           │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Hierarchy Construction                                 │
│  - Build tree: 6 → 6.6 → 6.6.2 → 6.6.2.3                       │
│  - Identify parent-child relationships                          │
│  - Detect section levels (1, 2, 3, 4, etc.)                    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Content Extraction                                     │
│  - For each section: extract text until next section            │
│  - Include everything between section markers                   │
│  - Track page numbers for each section                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: Subtitle Detection (Optional)                          │
│  - Look for quoted text: "HS400" timing mode selection          │
│  - Look for bold/italic headers within section                  │
│  - Add to metadata                                              │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 6: Chunk Size Validation                                  │
│  - If section > MAX_SIZE: split within section                  │
│  - If section < MIN_SIZE: consider merging with next subsection │
│  - Preserve section boundaries                                  │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 7: Chunk Creation                                         │
│  - Create one chunk per section (or subsection)                 │
│  - Include complete metadata                                    │
│  - Generate embeddings                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Example Output

**Section 6.6.2.3:**
```python
{
    'chunk_id': 'uuid-...',
    'section_number': '6.6.2.3',
    'section_title': 'The valid IO Voltage for HS400 is 1.8 V or 1.2 V for VCCQ',
    'subtitles': ['"HS400" timing mode selection'],
    'section_level': 3,
    'section_path': 'Chapter 6 > 6.6 HS400 Mode > 6.6.2 HS400 Configuration > 6.6.2.3',
    'parent_section': '6.6.2',
    'child_sections': [],  # No children
    'pages': [66, 67],
    'text': 'The valid IO Voltage for HS400 is 1.8 V or 1.2 V for VCCQ.\n\n"HS400" timing mode selection\n\nThe bus width is set to only DDR 8bit in HS400 mode...',
    'tokens': 450,
    'doc_id': 'eMMC_5_1_...',
    'protocol': 'eMMC',
    'version': '5.1',
}
```

**Section 7.4.35:**
```python
{
    'chunk_id': 'uuid-...',
    'section_number': '7.4.35',
    'section_title': 'INI_TIMEOUT_AP [241]',
    'subtitles': [],
    'section_level': 3,
    'section_path': 'Chapter 7 > 7.4 Register Fields > 7.4.35',
    'parent_section': '7.4',
    'child_sections': [],
    'pages': [206],
    'text': 'This register indicates the maximum initialization timeout during the first power up after successful partitioning of an e•MMC device...',
    'tokens': 180,
    'doc_id': 'eMMC_5_1_...',
    'protocol': 'eMMC',
    'version': '5.1',
}
```

---

## Key Questions to Answer

### 1. Are Section Numbers Always Present?

**Need to verify:**
- Do ALL sections in eMMC spec have numbered headings?
- Are there any sections with only text headings (no numbers)?
- Are section numbers consistently formatted?

**Test approach:**
```python
# Scan entire PDF for section number patterns
# Check if coverage is 100% or if there are gaps
```

### 2. How to Handle Edge Cases?

**Edge Case 1: Figures and Tables**
```
Figure 6-1: HS400 Selection Flow Diagram
Table 7-5: Register Field Descriptions
```
- These have numbers but aren't sections
- Need to filter out: `Figure X-Y`, `Table X-Y`

**Edge Case 2: Section References**
```
"See section 6.6.2.3 for more details"
```
- This is a reference, not a section header
- Need context detection (is it at start of line? Is text capitalized?)

**Edge Case 3: Appendices**
```
Appendix A: Command Set Overview
Appendix B.2.5: CQE Architecture
```
- Different numbering scheme
- Need to handle letter prefixes

**Edge Case 4: Very Small Sections**
```
6.6.2.3.1 Note
This is important.
```
- Only 1 sentence
- Should we merge with parent or keep separate?

### 3. Subtitle Detection Reliability

**Quoted Text:**
```
"HS400" timing mode selection   ✅ Easy to detect
```

**Bold/Italic:**
```
**Important Note**   ⚠️ Harder (needs formatting metadata)
```

**Implied Subtitles:**
```
HS400 Configuration Parameters   ❌ Hard to detect (no quotes, no special formatting)
```

**Question:** Is subtitle detection essential, or can we rely on full-text search?

### 4. Chunk Size Constraints

**Problem:** Some sections might be:
- **Too large** (>800 tokens) → Need to split within section
- **Too small** (<100 tokens) → Maybe merge with parent or sibling

**Options:**
1. **Strict**: One chunk per section, regardless of size
2. **Flexible**: Split large sections, merge small ones
3. **Hierarchical**: Use section levels to decide (level 3+ = always split, level 1-2 = merge if small)

---

## Feasibility Analysis

### Technical Feasibility: ✅ **HIGH**

**Required Tools:**
- **PDF Text Extraction**: `pdfplumber` or `PyMuPDF` (mature, reliable)
- **Regex**: Built-in Python (for section number detection)
- **Tree Building**: Standard algorithms (easy to implement)

**Complexity:**
- Medium (3-5 days implementation + testing)
- Lower than current LLM correction approach
- More deterministic and maintainable

### Quality Improvement: ✅ **VERY HIGH**

**Expected Improvements:**
1. **Section Title Accuracy**: 95.2% → **100%** (no misidentification)
2. **Subtitle Capture**: 0% → **60-80%** (quoted subtitles)
3. **Mixed Content**: <2% → **0%** (perfect boundaries)
4. **Cost**: $0.04/doc → **$0.00** (no LLM correction needed)

### Data Coverage: ⚠️ **UNKNOWN (NEEDS VALIDATION)**

**Critical Question:** Are section numbers present in **100%** of content?

**Validation Steps:**
1. Extract all text from eMMC 5.1 spec
2. Find all section numbers
3. Check coverage:
   - Are there pages without section numbers?
   - Are there sections with only descriptive titles (no numbers)?
4. Manual review of edge cases

### Implementation Risk: ⚠️ **MEDIUM**

**Risks:**
1. **Assumption failure**: If section numbers aren't 100% present, approach fails
2. **Edge cases**: Figures, tables, references might get misidentified
3. **Subtitle detection**: May not capture all subtitles (60-80% expected)
4. **Development time**: 3-5 days implementation + testing

**Mitigation:**
1. **Validate assumptions first** (scan PDF, check coverage)
2. **Build robust filters** (for figures, tables, references)
3. **Accept imperfect subtitle detection** (60-80% is still better than 0%)
4. **Incremental development** (build, test, iterate)

---

## Recommendation

### Phase 1: Validation (1 day)

**Goal:** Determine if title-number-based approach is viable

**Tasks:**
1. Extract full text from eMMC 5.1 spec
2. Find all section numbers using regex
3. Calculate coverage:
   - How many pages have section numbers?
   - Are there gaps in numbering?
   - How many sections vs. total content?
4. Manual review of 20-30 random pages
5. Check edge cases (figures, tables, appendices)

**Decision Criteria:**
- If coverage ≥ 95% → **PROCEED** with implementation
- If coverage 80-95% → **HYBRID** approach (title-numbers where available, fallback to current method)
- If coverage < 80% → **STAY** with current approach + improvements

### Phase 2: Implementation (3-4 days)

**If validation passes:**

1. **Build section extractor** (1 day)
   - Full text extraction with page numbers
   - Section number detection (regex)
   - Hierarchy construction

2. **Build chunker** (1 day)
   - Extract content for each section
   - Handle size constraints
   - Create metadata

3. **Add subtitle detection** (0.5 days)
   - Quoted text detection
   - Bold/italic detection (if possible)

4. **Testing** (1 day)
   - Test with eMMC 5.1 spec
   - Compare with current approach
   - Verify edge cases

5. **Integration** (0.5 days)
   - Update ingestion pipeline
   - Re-ingest eMMC 5.1 spec
   - Validate quality

### Phase 3: Quality Comparison (0.5 days)

**Compare:**
- Current approach (821 chunks, 95.2% accuracy)
- Title-number approach (??? chunks, ???% accuracy)

**Metrics:**
- Section title accuracy
- Subtitle capture rate
- Mixed content rate
- Chunk count
- Average chunk size
- User query results (same queries, compare relevance)

---

## Alternative: Hybrid Approach

**If pure title-number approach has gaps:**

### Hybrid Strategy

1. **Primary**: Use title-number extraction where section numbers are present (80-95% of content)
2. **Fallback**: Use current section-aware approach for content without section numbers (5-20%)
3. **Best of both**: Combine strengths, minimize weaknesses

**Example:**
```python
def chunk_document(pdf_path):
    # Try title-number extraction first
    title_chunks = extract_by_section_numbers(pdf_path)

    # Find gaps (content not covered by section numbers)
    gaps = find_uncovered_content(pdf_path, title_chunks)

    # Use current approach for gaps
    gap_chunks = section_aware_chunking(gaps)

    # Merge both
    all_chunks = title_chunks + gap_chunks

    return all_chunks
```

---

## Conclusion

### Summary

**Title-Number-Based Chunking is:**
- ✅ **Technically feasible** (medium complexity)
- ✅ **High quality potential** (100% accuracy possible)
- ✅ **Cost effective** ($0 vs. $0.04/doc)
- ⚠️ **Needs validation** (check section number coverage)
- ⚠️ **Medium risk** (depends on assumption validity)

### Next Steps

1. **Validate assumptions** (1 day)
   - Extract all section numbers from eMMC 5.1 spec
   - Check coverage and gaps
   - Manual review of edge cases

2. **Make decision** (based on validation results)
   - If ≥95% coverage → Implement full title-number approach
   - If 80-95% coverage → Implement hybrid approach
   - If <80% coverage → Improve current approach instead

3. **Proceed with implementation** (3-4 days)
   - Build section extractor
   - Build new chunker
   - Test and validate
   - Compare quality

### Expected Outcome

**If successful:**
- 821 chunks → 900-1000 chunks (more granular, one per section)
- 95.2% accuracy → **100% accuracy** (no misidentified titles)
- 0% subtitles → **60-80% subtitles** captured
- $0.04/doc → **$0.00** (no LLM correction)
- <2% mixed content → **0% mixed content**

**Total transformation:**
- From: Heuristic-based, 95.2% accuracy, needs LLM correction
- To: Deterministic, 100% accuracy, no correction needed

---

**Status:** Analysis complete, awaiting validation decision

**Recommendation:** **VALIDATE FIRST, then decide on implementation approach**
