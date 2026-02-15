# TOC + Regex Hybrid Chunking - Implementation Plan

**Date:** 2026-02-14
**Status:** Ready for Implementation
**Timeline:** 3-4 days
**Goal:** Achieve 99%+ coverage with 100% accuracy, $0 cost

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PDF Document                                 │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: TOC Extraction                                             │
│  - Extract TOC pages (5-19, 22)                                      │
│  - Parse section numbers, titles, page numbers                       │
│  - Result: 351 TOC entries                                           │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: TOC Preprocessing                                          │
│  - Sort by section number (fix 3 out-of-order)                      │
│  - Infer 49 missing parent sections                                  │
│  - Calculate page ranges (start/end for each section)                │
│  - Flag 4 long sections (>10 pages)                                  │
│  - Result: 400 complete entries (351 + 49 inferred)                  │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: Bounded Regex Search                                      │
│  - For each TOC section, search within page range                    │
│  - Find subsections (e.g., 6.6.2.1, 6.6.2.2, 6.6.2.3)               │
│  - Validate ascending order                                          │
│  - Result: +150-200 subsections found                                │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4: Content Extraction                                         │
│  - For each section/subsection, extract text                         │
│  - Detect subtitles (quoted text, bold headers)                      │
│  - Build complete metadata                                           │
│  - Result: 550-600 sections with content                             │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 5: Intelligent Truncation                                     │
│  - Check token count for each section                                │
│  - If >800 tokens: split by subsections/paragraphs/sentences         │
│  - Preserve parent-child relationships                                │
│  - Result: All chunks ≤800 tokens                                    │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 6: Chunk Creation & Embedding                                 │
│  - Generate embeddings (local, free)                                 │
│  - Store in Qdrant with complete metadata                            │
│  - Result: 600-700 high-quality chunks                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
src/ingestion/
├── toc_chunker.py                    # NEW - Main TOC + Regex hybrid chunker
│   ├── TOCExtractor                  # Extract TOC from PDF
│   ├── TOCPreprocessor              # Sort, infer parents, calculate ranges
│   ├── BoundedRegexSearcher         # Find subsections within page ranges
│   ├── ContentExtractor             # Extract text for each section
│   └── IntelligentTruncator         # Handle long sections
│
├── toc_based_chunker.py              # NEW - Wrapper class
│   └── TOCBasedChunker              # Main interface (replaces SemanticChunker)
│
├── chunker_factory.py                # MODIFIED - Add toc_based strategy
│
├── ingest_spec.py                    # MODIFIED - Use toc_based by default
│
└── section_aware_chunker.py          # KEEP - Fallback for non-TOC docs

scripts/
├── test_toc_chunking.py              # NEW - Test suite
├── compare_chunking_approaches.py    # NEW - Compare old vs new
└── validate_chunks.py                # NEW - Quality validation

.env.example                           # MODIFIED - Add CHUNKING_STRATEGY=toc_based
```

---

## Implementation Phases

### **Phase 1: TOC Extractor (Day 1, 4-6 hours)**

**Goal:** Extract and parse TOC entries from PDF

**Files:**
- `src/ingestion/toc_chunker.py` (new)

**Components:**

#### 1.1 TOCExtractor Class

```python
class TOCExtractor:
    """Extract Table of Contents from PDF."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.toc_pages = []
        self.toc_entries = []

    def find_toc_pages(self) -> List[int]:
        """
        Find pages containing TOC.

        Heuristics:
        - Contains "Contents" header
        - Has many page numbers (........ 45)
        - Has section number patterns (6.6.2 Title)
        """
        # Implementation from test_toc_extraction.py
        pass

    def extract_toc_entries(self) -> List[Dict]:
        """
        Extract TOC entries from identified pages.

        Patterns to match:
        1. "6.6.2 Title ........ 65"
        2. "7.4.35 INI_TIMEOUT_AP [241] ... 206"

        Returns:
        List of {
            'section_number': '6.6.2',
            'section_title': 'HS400 Configuration',
            'page_number': 65,
            'level': 3,
            'toc_page': 5
        }
        """
        # Implementation from test_toc_extraction.py
        pass

    def extract(self) -> List[Dict]:
        """Main method: find TOC pages and extract entries."""
        self.toc_pages = self.find_toc_pages()
        self.toc_entries = self.extract_toc_entries()
        return self.toc_entries
```

**Testing:**
```python
# Test with eMMC 5.1 spec
extractor = TOCExtractor('specs/emmc5.1-protocol-JESD84-B51.pdf')
entries = extractor.extract()

assert len(entries) == 351, "Should extract 351 entries"
assert entries[0]['section_number'] == '5.2'
assert entries[0]['section_title'] == 'Memory Addressing'
```

---

### **Phase 2: TOC Preprocessor (Day 1, 2-3 hours)**

**Goal:** Clean, sort, and enhance TOC entries

**Components:**

#### 2.1 TOCPreprocessor Class

```python
class TOCPreprocessor:
    """Preprocess TOC entries: sort, infer parents, calculate ranges."""

    def sort_entries(self, entries: List[Dict]) -> List[Dict]:
        """Sort by section number (fix out-of-order)."""
        return sorted(entries, key=lambda e: self._parse_section_number(e['section_number']))

    def _parse_section_number(self, section_num: str) -> Tuple:
        """Parse for proper sorting: '6.6.2' -> (6, 6, 2)"""
        parts = section_num.replace('Appendix ', '').strip('.').split('.')
        return tuple(int(p) if p.isdigit() else 999 for p in parts)

    def infer_missing_parents(self, entries: List[Dict]) -> List[Dict]:
        """
        Create synthetic entries for missing parents.

        Example:
        If we have 5.3.1, 5.3.2, 5.3.3 but not 5.3:
        - Create 5.3 entry
        - Title: '[Inferred] Bus Protocol and Modes' (from children)
        - Page: Same as first child (5.3.1)
        """
        existing = {e['section_number']: e for e in entries}
        synthetic = []

        for entry in entries:
            parts = entry['section_number'].split('.')

            for i in range(1, len(parts)):
                parent_num = '.'.join(parts[:i])

                if parent_num not in existing:
                    # Find first child
                    children = [e for e in entries
                               if e['section_number'].startswith(parent_num + '.')]

                    if children:
                        first_child = min(children, key=lambda x: x['section_number'])

                        synthetic.append({
                            'section_number': parent_num,
                            'section_title': f'[Inferred]',
                            'page_number': first_child['page_number'],
                            'level': len(parent_num.split('.')),
                            'inferred': True
                        })

                        existing[parent_num] = synthetic[-1]

        return entries + synthetic

    def calculate_page_ranges(self, entries: List[Dict]) -> List[Dict]:
        """
        Calculate start/end page for each section.

        Section X starts at its page and ends at (next section's page - 1).
        """
        sorted_entries = sorted(entries, key=lambda e: e['page_number'])

        for i, entry in enumerate(sorted_entries):
            entry['page_start'] = entry['page_number']

            # End page is next section's start - 1
            if i + 1 < len(sorted_entries):
                entry['page_end'] = sorted_entries[i + 1]['page_number'] - 1
            else:
                entry['page_end'] = 352  # End of document

        return entries

    def flag_long_sections(self, entries: List[Dict], threshold: int = 10) -> List[Dict]:
        """Flag sections spanning >threshold pages."""
        for entry in entries:
            page_count = entry['page_end'] - entry['page_start'] + 1
            entry['is_long'] = page_count > threshold
            entry['page_count'] = page_count

        return entries

    def process(self, entries: List[Dict]) -> List[Dict]:
        """Main preprocessing pipeline."""
        entries = self.sort_entries(entries)
        entries = self.infer_missing_parents(entries)
        entries = self.calculate_page_ranges(entries)
        entries = self.flag_long_sections(entries)
        return entries
```

**Testing:**
```python
preprocessor = TOCPreprocessor()
processed = preprocessor.process(raw_toc_entries)

assert len(processed) == 400, "Should have 351 + 49 inferred = 400"
assert all('page_start' in e for e in processed), "All should have page ranges"
assert sum(e['is_long'] for e in processed) == 4, "Should flag 4 long sections"
```

---

### **Phase 3: Bounded Regex Searcher (Day 2, 4-6 hours)**

**Goal:** Find subsections within each TOC section's page range

**Components:**

#### 3.1 BoundedRegexSearcher Class

```python
class BoundedRegexSearcher:
    """Search for subsections within bounded page ranges."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def find_subsections(self, parent_section: Dict) -> List[Dict]:
        """
        Find all subsections within parent's page range.

        Example:
        parent_section = {
            'section_number': '6.6.2',
            'page_start': 43,
            'page_end': 47
        }

        Search pages 43-47 for:
        - 6.6.2.1 [title]
        - 6.6.2.2 [title]
        - 6.6.2.3 [title]
        - etc.
        """
        parent_num = parent_section['section_number']
        start_page = parent_section['page_start']
        end_page = parent_section['page_end']

        # Extract text from page range
        text = self._extract_page_range(start_page, end_page)

        # Pattern for subsections
        # Escape dots: 6.6.2 -> 6\.6\.2
        escaped_parent = re.escape(parent_num)
        pattern = rf'{escaped_parent}\.(\d+)\s+([A-Z][^\n]{{5,200}}?)(?=\n|$)'

        subsections = []
        matches = re.finditer(pattern, text, re.MULTILINE)

        for match in matches:
            subsection_num = f"{parent_num}.{match.group(1)}"
            subsection_title = match.group(2).strip()

            # Clean title
            subsection_title = re.sub(r'\s*\.{2,}\s*\d+\s*$', '', subsection_title)
            subsection_title = re.sub(r'\s{2,}', ' ', subsection_title)

            # Find page number (line-by-line search)
            page_num = self._find_page_number(subsection_num, start_page, end_page)

            subsections.append({
                'section_number': subsection_num,
                'section_title': subsection_title,
                'page_number': page_num,
                'level': len(subsection_num.split('.')),
                'parent': parent_num
            })

        # Validate ascending order
        subsections = self._validate_order(subsections)

        return subsections

    def _extract_page_range(self, start_page: int, end_page: int) -> str:
        """Extract text from a range of pages."""
        import pdfplumber

        text_parts = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in range(start_page, end_page + 1):
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"[PAGE {page_num}]\n{text}\n")

        return '\n'.join(text_parts)

    def _find_page_number(self, section_num: str, start_page: int, end_page: int) -> int:
        """Find which page a section appears on."""
        import pdfplumber

        pattern = re.escape(section_num)

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in range(start_page, end_page + 1):
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    text = page.extract_text()

                    if text and re.search(rf'\b{pattern}\b', text):
                        return page_num

        return start_page  # Default to parent's start page

    def _validate_order(self, subsections: List[Dict]) -> List[Dict]:
        """Validate that subsections are in ascending numerical order."""
        if not subsections:
            return subsections

        # Sort by section number
        sorted_subs = sorted(subsections, key=lambda s: int(s['section_number'].split('.')[-1]))

        # Check for gaps or out-of-order
        for i in range(len(sorted_subs) - 1):
            current_num = int(sorted_subs[i]['section_number'].split('.')[-1])
            next_num = int(sorted_subs[i + 1]['section_number'].split('.')[-1])

            if next_num != current_num + 1:
                # Gap detected - log warning
                pass

        return sorted_subs

    def search_all(self, toc_entries: List[Dict]) -> List[Dict]:
        """Search for subsections in all TOC entries."""
        all_subsections = []

        for entry in toc_entries:
            # Skip inferred entries
            if entry.get('inferred'):
                continue

            # Search for subsections
            subsections = self.find_subsections(entry)

            if subsections:
                all_subsections.extend(subsections)

        return all_subsections
```

**Testing:**
```python
searcher = BoundedRegexSearcher('specs/emmc5.1-protocol-JESD84-B51.pdf')

# Test specific section
parent = {
    'section_number': '6.6.2',
    'page_start': 43,
    'page_end': 47
}

subsections = searcher.find_subsections(parent)

# Should find 6.6.2.1, 6.6.2.2, 6.6.2.3, etc.
assert any(s['section_number'] == '6.6.2.3' for s in subsections), "Should find 6.6.2.3"

# Check subtitle detection
section_6_6_2_3 = next(s for s in subsections if s['section_number'] == '6.6.2.3')
# Will implement subtitle detection in Phase 4
```

---

### **Phase 4: Content Extractor (Day 2, 3-4 hours)**

**Goal:** Extract text content and detect subtitles for each section

**Components:**

#### 4.1 ContentExtractor Class

```python
class ContentExtractor:
    """Extract content for each section with subtitle detection."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract_section_content(self, section: Dict, next_section: Dict = None) -> str:
        """
        Extract text content for a section.

        Start: section['page_start'] or section['page_number']
        End: next_section['page_number'] - 1 or section['page_end']
        """
        start_page = section.get('page_start', section['page_number'])

        if next_section:
            end_page = next_section['page_number'] - 1
        else:
            end_page = section.get('page_end', start_page)

        # Extract text
        text = self._extract_pages(start_page, end_page)

        # Find section start in text
        section_num = section['section_number']
        section_title = section['section_title']

        # Pattern: "6.6.2.3 The valid IO Voltage..."
        pattern = rf'{re.escape(section_num)}\s+{re.escape(section_title)}'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            # Start from section header
            text = text[match.start():]

        # If there's a next section, cut off before it starts
        if next_section:
            next_pattern = rf'{re.escape(next_section["section_number"])}\s+'
            next_match = re.search(next_pattern, text)
            if next_match:
                text = text[:next_match.start()]

        return text.strip()

    def detect_subtitles(self, content: str) -> List[str]:
        """
        Detect subtitles within content.

        Patterns:
        1. Quoted text: "HS400" timing mode selection
        2. Bold/emphasized: **Important Note**
        3. Standalone capitalized lines
        """
        subtitles = []

        # Pattern 1: Quoted text
        quoted = re.findall(r'"([^"]{5,100})"', content)
        subtitles.extend(quoted)

        # Pattern 2: Lines that look like headers
        # (All caps, short, followed by content)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()

            # Check if it's a potential subtitle
            if 5 <= len(line) <= 100:
                if line[0].isupper() and not line.endswith(('.', ',', ';')):
                    # Check if next line exists and starts lowercase (likely content)
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and next_line[0].islower():
                            subtitles.append(line)

        # Deduplicate
        subtitles = list(dict.fromkeys(subtitles))

        return subtitles[:5]  # Max 5 subtitles

    def _extract_pages(self, start_page: int, end_page: int) -> str:
        """Extract text from page range."""
        import pdfplumber

        text_parts = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in range(start_page, end_page + 1):
                if page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

        return '\n\n'.join(text_parts)

    def extract_all_content(self, sections: List[Dict]) -> List[Dict]:
        """Extract content for all sections."""
        sorted_sections = sorted(sections, key=lambda s: s['page_number'])

        for i, section in enumerate(sorted_sections):
            # Get next section
            next_section = sorted_sections[i + 1] if i + 1 < len(sorted_sections) else None

            # Extract content
            content = self.extract_section_content(section, next_section)
            section['text'] = content

            # Detect subtitles
            subtitles = self.detect_subtitles(content)
            section['subtitles'] = subtitles

        return sections
```

**Testing:**
```python
extractor = ContentExtractor('specs/emmc5.1-protocol-JESD84-B51.pdf')

section = {
    'section_number': '6.6.2.3',
    'section_title': 'The valid IO Voltage for HS400...',
    'page_number': 66
}

content = extractor.extract_section_content(section)
subtitles = extractor.detect_subtitles(content)

assert '"HS400" timing mode selection' in subtitles, "Should detect subtitle"
```

---

### **Phase 5: Intelligent Truncator (Day 3, 4-6 hours)**

**Goal:** Handle long sections by splitting intelligently

**Components:**

#### 5.1 IntelligentTruncator Class

```python
class IntelligentTruncator:
    """Split long sections intelligently."""

    def __init__(self, max_tokens: int = 800, min_tokens: int = 100):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens

    def count_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars)."""
        return len(text) // 4

    def needs_splitting(self, section: Dict) -> bool:
        """Check if section needs to be split."""
        tokens = self.count_tokens(section['text'])
        return tokens > self.max_tokens

    def split_section(self, section: Dict, subsections: List[Dict] = None) -> List[Dict]:
        """
        Split long section into multiple chunks.

        Strategy:
        1. If subsections exist: split by subsections
        2. Else: split by paragraphs
        3. Else: split by sentences
        """
        text = section['text']
        tokens = self.count_tokens(text)

        # Strategy 1: Split by subsections (best)
        if subsections and len(subsections) > 1:
            return self._split_by_subsections(section, subsections)

        # Strategy 2: Split by paragraphs
        chunks = self._split_by_paragraphs(section)

        if all(self.count_tokens(c['text']) <= self.max_tokens for c in chunks):
            return chunks

        # Strategy 3: Split by sentences
        return self._split_by_sentences(section)

    def _split_by_subsections(self, parent: Dict, subsections: List[Dict]) -> List[Dict]:
        """Split by subsections (ideal)."""
        chunks = []

        for i, subsection in enumerate(subsections):
            chunk = {
                'section_number': subsection['section_number'],
                'section_title': subsection['section_title'],
                'parent_section': parent['section_number'],
                'text': subsection['text'],
                'pages': subsection.get('pages', [subsection['page_number']]),
                'level': subsection['level'],
                'chunk_index': f"{i+1}/{len(subsections)}"
            }
            chunks.append(chunk)

        return chunks

    def _split_by_paragraphs(self, section: Dict) -> List[Dict]:
        """Split by paragraph boundaries."""
        text = section['text']
        paragraphs = re.split(r'\n\n+', text)

        chunks = []
        current_chunk = ''
        chunk_index = 1

        for para in paragraphs:
            test_chunk = current_chunk + '\n\n' + para if current_chunk else para
            tokens = self.count_tokens(test_chunk)

            if tokens <= self.max_tokens:
                current_chunk = test_chunk
            else:
                # Save current chunk
                if current_chunk:
                    chunks.append({
                        'section_number': section['section_number'],
                        'section_title': section['section_title'],
                        'parent_section': section.get('parent'),
                        'text': current_chunk.strip(),
                        'pages': section.get('pages', [section['page_number']]),
                        'level': section['level'],
                        'chunk_index': f"{chunk_index}/{len(paragraphs)}"  # Approximate
                    })
                    chunk_index += 1

                # Start new chunk with current paragraph
                current_chunk = para

        # Add last chunk
        if current_chunk:
            chunks.append({
                'section_number': section['section_number'],
                'section_title': section['section_title'],
                'parent_section': section.get('parent'),
                'text': current_chunk.strip(),
                'pages': section.get('pages', [section['page_number']]),
                'level': section['level'],
                'chunk_index': f"{chunk_index}/{chunk_index}"
            })

        return chunks

    def _split_by_sentences(self, section: Dict) -> List[Dict]:
        """Split by sentence boundaries (last resort)."""
        # Similar to paragraphs but split on '. '
        text = section['text']
        sentences = re.split(r'\.\s+', text)

        # Same logic as _split_by_paragraphs
        # ... implementation similar to above
        pass

    def process_all(self, sections: List[Dict]) -> List[Dict]:
        """Process all sections, splitting long ones."""
        final_chunks = []

        for section in sections:
            if self.needs_splitting(section):
                # Split into multiple chunks
                split_chunks = self.split_section(section)
                final_chunks.extend(split_chunks)
            else:
                # Keep as single chunk
                final_chunks.append(section)

        return final_chunks
```

---

### **Phase 6: Main TOCBasedChunker (Day 3, 2-3 hours)**

**Goal:** Integrate all components into a single chunker class

**File:** `src/ingestion/toc_based_chunker.py`

```python
class TOCBasedChunker:
    """
    Main TOC + Regex hybrid chunker.

    Integrates:
    - TOCExtractor
    - TOCPreprocessor
    - BoundedRegexSearcher
    - ContentExtractor
    - IntelligentTruncator
    """

    def __init__(
        self,
        chunk_size: int = 350,
        max_chunk_size: int = 800,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, pdf_path: str) -> List[Dict]:
        """
        Main chunking pipeline.

        Returns chunks with metadata:
        {
            'section_number': '6.6.2.3',
            'section_title': 'The valid IO Voltage for HS400...',
            'subtitles': ['"HS400" timing mode selection'],
            'text': '...',
            'pages': [66, 67],
            'level': 4,
            'parent_section': '6.6.2',
            'chunk_index': '1/1'  # If not split
        }
        """
        # Phase 1: Extract TOC
        print("Phase 1: Extracting TOC...")
        extractor = TOCExtractor(pdf_path)
        toc_entries = extractor.extract()
        print(f"  ✓ Extracted {len(toc_entries)} TOC entries")

        # Phase 2: Preprocess TOC
        print("Phase 2: Preprocessing TOC...")
        preprocessor = TOCPreprocessor()
        processed_entries = preprocessor.process(toc_entries)
        print(f"  ✓ Processed {len(processed_entries)} entries (incl. {len(processed_entries) - len(toc_entries)} inferred)")

        # Phase 3: Find subsections
        print("Phase 3: Finding subsections with bounded regex...")
        searcher = BoundedRegexSearcher(pdf_path)
        subsections = searcher.search_all(processed_entries)
        print(f"  ✓ Found {len(subsections)} subsections")

        # Combine TOC + subsections
        all_sections = processed_entries + subsections

        # Phase 4: Extract content
        print("Phase 4: Extracting content and detecting subtitles...")
        content_extractor = ContentExtractor(pdf_path)
        sections_with_content = content_extractor.extract_all_content(all_sections)
        print(f"  ✓ Extracted content for {len(sections_with_content)} sections")

        # Phase 5: Intelligent truncation
        print("Phase 5: Applying intelligent truncation...")
        truncator = IntelligentTruncator(
            max_tokens=self.max_chunk_size,
            min_tokens=self.min_chunk_size
        )
        final_chunks = truncator.process_all(sections_with_content)
        print(f"  ✓ Created {len(final_chunks)} final chunks")

        return final_chunks
```

---

### **Phase 7: Integration (Day 4, 2-3 hours)**

**Goal:** Integrate with existing ingestion pipeline

**Files to modify:**

#### 7.1 `src/ingestion/chunker_factory.py`

```python
def create_chunker(strategy=None, **kwargs):
    """Create chunker based on strategy."""

    strategy = strategy or settings.chunking_strategy

    if strategy == "toc_based":
        from src.ingestion.toc_based_chunker import TOCBasedChunker
        return TOCBasedChunker(
            chunk_size=kwargs.get("chunk_size", settings.chunk_size),
            max_chunk_size=kwargs.get("max_chunk_size", settings.max_chunk_size),
            min_chunk_size=kwargs.get("min_chunk_size", settings.min_chunk_size)
        )
    elif strategy == "section_aware":
        # ... existing code
        pass
    # ... etc
```

#### 7.2 `.env` configuration

```bash
# Chunking Strategy
CHUNKING_STRATEGY=toc_based  # NEW DEFAULT

# Chunk Sizes
CHUNK_SIZE=350
MAX_CHUNK_SIZE=800
MIN_CHUNK_SIZE=100
```

#### 7.3 Update `src/ingestion/ingest_spec.py`

```python
# Use factory to get chunker (automatically uses toc_based if configured)
chunker = get_default_chunker()

# Chunk document
chunks = chunker.chunk_document(pdf_path)

# Store in Qdrant (existing code)
# ...
```

---

### **Phase 8: Testing & Validation (Day 4, 3-4 hours)**

**Goal:** Comprehensive testing and quality validation

#### 8.1 Unit Tests

```python
# tests/test_toc_chunker.py

def test_toc_extraction():
    """Test TOC extraction."""
    extractor = TOCExtractor('specs/emmc5.1-protocol-JESD84-B51.pdf')
    entries = extractor.extract()

    assert len(entries) == 351
    assert entries[0]['section_number'] == '5.2'

def test_toc_preprocessing():
    """Test TOC preprocessing."""
    # ... test sorting, parent inference, page ranges

def test_bounded_regex_search():
    """Test subsection finding."""
    # ... test that 6.6.2.3 is found within 6.6.2's range

def test_content_extraction():
    """Test content extraction and subtitle detection."""
    # ... verify subtitles are detected

def test_intelligent_truncation():
    """Test long section splitting."""
    # ... verify sections >800 tokens are split correctly
```

#### 8.2 Integration Test

```python
def test_full_pipeline():
    """Test complete chunking pipeline."""
    chunker = TOCBasedChunker()
    chunks = chunker.chunk_document('specs/emmc5.1-protocol-JESD84-B51.pdf')

    # Coverage
    assert len(chunks) >= 550, "Should have 550-700 chunks"

    # Quality checks
    section_6_6_2_3 = next((c for c in chunks if c['section_number'] == '6.6.2.3'), None)
    assert section_6_6_2_3 is not None, "Should find section 6.6.2.3"
    assert '"HS400" timing mode selection' in section_6_6_2_3['subtitles'], "Should detect subtitle"

    section_7_4_35 = next((c for c in chunks if c['section_number'] == '7.4.35'), None)
    assert section_7_4_35 is not None, "Should find section 7.4.35"
    assert section_7_4_35['section_title'] == 'INI_TIMEOUT_AP [241]', "Should have correct title"

    # Token size checks
    for chunk in chunks:
        tokens = len(chunk['text']) // 4
        assert tokens <= 800, f"Chunk {chunk['section_number']} exceeds max tokens"
```

#### 8.3 Comparison Test

```python
def test_compare_approaches():
    """Compare TOC-based vs current approach."""

    # Old approach
    old_chunker = SectionAwareChunker()
    old_chunks = old_chunker.chunk_document(pdf_path)

    # New approach
    new_chunker = TOCBasedChunker()
    new_chunks = new_chunker.chunk_document(pdf_path)

    print(f"Old: {len(old_chunks)} chunks, New: {len(new_chunks)} chunks")

    # Quality comparison
    # ... check section title accuracy, subtitle capture, etc.
```

---

## Timeline

### Day 1 (6-9 hours)
- **Morning (4-6h):** TOCExtractor implementation
- **Afternoon (2-3h):** TOCPreprocessor implementation
- **Testing:** Unit tests for Phases 1-2

### Day 2 (7-10 hours)
- **Morning (4-6h):** BoundedRegexSearcher implementation
- **Afternoon (3-4h):** ContentExtractor implementation
- **Testing:** Unit tests for Phases 3-4

### Day 3 (6-9 hours)
- **Morning (4-6h):** IntelligentTruncator implementation
- **Afternoon (2-3h):** TOCBasedChunker integration
- **Testing:** Integration tests

### Day 4 (5-7 hours)
- **Morning (2-3h):** Integration with existing pipeline
- **Afternoon (3-4h):** Comprehensive testing and validation
- **Re-ingestion:** Run on eMMC 5.1 spec, compare results

**Total: 24-35 hours (3-4 days)**

---

## Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Coverage** | ≥99% | Count pages with sections / 352 |
| **Chunk count** | 550-700 | len(chunks) |
| **Section title accuracy** | 100% | Manual review of 50 random chunks |
| **Subtitle capture** | ≥60% | Check for quoted text in subtitles field |
| **Token size compliance** | 100% | All chunks ≤800 tokens |
| **Problematic chunks fixed** | 2/2 | Check 6.6.2.3 and 7.4.35 specifically |
| **Cost** | $0 | No LLM API calls |

---

## Rollback Plan

If TOC-based approach fails:

1. **Keep current approach** (95.2% accuracy is still good)
2. **Fix specific problematic chunks** manually (2 chunks)
3. **Improve LLM correction** prompts for better quality

**Risk:** Low - validation showed 98.6% TOC coverage, so approach is viable

---

## Next Steps

**Ready to start implementation?**

**Option A:** Start implementing Phase 1 (TOCExtractor) now
**Option B:** Review implementation plan, make adjustments
**Option C:** Start with a prototype/proof-of-concept first
**Option D:** Something else?

I can begin coding immediately if you're ready!
