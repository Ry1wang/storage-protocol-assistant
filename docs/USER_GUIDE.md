# Storage Protocol Assistant - User Guide

**Version:** 0.1.0 (MVP)
**Status:** ✅ Production Ready
**Last Updated:** 2026-02-14

---

## Quick Start

### Access the Application

1. **Ensure services are running:**
   ```bash
   cd /Users/xiaowang/Documents/Projects/storage-protocol-assistant
   docker-compose up -d
   ```

2. **Open your browser and navigate to:**
   ```
   http://localhost:8501
   ```

3. **You should see the Storage Protocol Assistant interface** with:
   - A chat interface in the main area
   - Sidebar with document filters and settings
   - System information at the bottom

---

## Interface Overview

### Main Chat Area

The main area displays:
- **Title:** "💬 Ask About Storage Protocols"
- **Chat History:** All previous questions and answers
- **Input Box:** Type your questions here
- **Citations:** Expandable sections showing source references

### Sidebar

**Document Filters:**
- **Select Protocols:** Filter by protocol type (eMMC, UFS, etc.)
- **Select Versions:** Filter by specification version

**Settings:**
- **Top-K Results:** Number of chunks to retrieve (5-20)
  - Default: 10
  - Lower = faster but might miss relevant info
  - Higher = more comprehensive but slower

- **Minimum Confidence:** Threshold for answer quality (0.5-1.0)
  - Default: 0.7
  - Higher = more strict filtering
  - Lower = more results but potentially less relevant

**System Info:**
- **Documents:** Total number of ingested specifications
- **Total Chunks:** Number of indexed text chunks
- **Version:** Current system version

---

## How to Use

### 1. Ask a Question

Simply type your question in the chat input box at the bottom of the page.

**Example Questions:**

```
How do I disable emulation mode in eMMC?
```

```
What is HS400 timing mode?
```

```
Explain RPMB partition access
```

```
What is native 4KB sector size?
```

```
How does sleep mode work in eMMC?
```

### 2. Review the Answer

The system will:
1. Show a "🤔 Thinking..." spinner while processing
2. Display the answer with relevant information
3. Show the top matching section and confidence score

**Answer Format:**
```
Based on the eMMC 5.1 specification:

**Relevant Information:**

[Detailed content from the specification]

*Please see the citations below for complete details and additional context.*

**Top Match:** [Section Title] (Confidence: XX.XX%)
```

### 3. Check Citations

Click the **"📖 Citations"** expander to see source references.

**Each citation includes:**
- **Source:** Protocol and version (e.g., "eMMC 5.1")
- **Section:** Exact section title (e.g., "6.6.34.1 Disabling emulation mode")
- **Page:** Page number(s) from the specification
- **Preview:** First 300 characters of the relevant text
- **Confidence:** Similarity score (higher = more relevant)

**Example Citation:**
```
1. eMMC 5.1 - Page 128

Section: 6.6.34.1 Disabling emulation mode

> To disable the emulation mode for large 4KB sector devices,
> host may write 0x01 to the USE_NATIVE_SECTOR field in
> EXT_CSD[62]. Setting USE_NATIVE_SECTOR does not immediately...

Confidence: 95.23%
```

### 4. Adjust Settings (Optional)

Use the sidebar to fine-tune results:

**To get more comprehensive answers:**
- Increase "Top-K Results" to 15-20
- Decrease "Minimum Confidence" to 0.6

**To get more precise answers:**
- Decrease "Top-K Results" to 5-8
- Increase "Minimum Confidence" to 0.8-0.9

**To filter specific protocols:**
- Uncheck protocols you're not interested in
- Select specific versions only

---

## Understanding Results

### Confidence Scores

The confidence score indicates how well the retrieved chunk matches your query:

- **90-100%:** Excellent match - highly relevant
- **80-89%:** Very good match - likely relevant
- **70-79%:** Good match - probably relevant
- **60-69%:** Moderate match - may be relevant
- **Below 60%:** Low match - might not be relevant

### Section Titles

All citations include accurate section titles extracted from the specifications:

**Quality Indicators:**
- ✅ **Descriptive titles:** "6.6.34.1 Disabling emulation mode"
- ✅ **Clear section paths:** "10.10 Bus Timing Specification in HS400 mode"
- ✅ **Specific topics:** "RPMB Data Read Operation"

### Multiple Citations

You'll typically see 3-5 citations per answer:
- **Citation #1:** Usually the best match (highest confidence)
- **Citations #2-5:** Additional context and related information

---

## Tips for Better Results

### 1. Be Specific

**Good:**
```
How do I set HS400 timing mode in eMMC 5.1?
```

**Better:**
```
What are the steps to switch from HS200 to HS400 timing mode?
```

### 2. Use Technical Terms

The system understands protocol-specific terminology:
- USE_NATIVE_SECTOR
- RPMB partition
- HS400 timing mode
- Enhanced Strobe
- Command Queuing

### 3. Ask One Thing at a Time

**Good:**
```
What is RPMB?
```

**Less Effective:**
```
What are RPMB, HS400, and command queuing?
```

### 4. Check Citations for Complete Details

The answer provides a summary. For full details:
1. Expand the citations
2. Note the page numbers
3. Refer to the original specification if needed

---

## Current System Status

### Available Documents

**eMMC 5.1 Specification:**
- Total chunks: **821**
- Section title accuracy: **95.2%**
- Focused chunks: **98%+**
- Average chunk size: **212 tokens**

### Quality Metrics

✅ **High-quality citations** with accurate section titles
✅ **Fast response times** (<2 seconds)
✅ **Comprehensive coverage** (821 focused chunks)
✅ **Professional quality** (production-ready)

---

## Troubleshooting

### No Results Found

**Message:** "I couldn't find any relevant information in the protocol specifications."

**Solutions:**
1. Try rephrasing your question
2. Lower the "Minimum Confidence" threshold
3. Increase "Top-K Results"
4. Check that the correct protocol/version is selected

### Error Processing Query

**Message:** "Sorry, I encountered an error processing your question."

**Solutions:**
1. Try again (temporary issue)
2. Simplify your question
3. Check that services are running:
   ```bash
   docker-compose ps
   ```
4. View logs for details:
   ```bash
   docker-compose logs -f app
   ```

### Services Not Running

**Check status:**
```bash
cd /Users/xiaowang/Documents/Projects/storage-protocol-assistant
docker-compose ps
```

**Expected output:**
```
NAME         STATUS
rag-app      Up (healthy)
rag-qdrant   Up (healthy)
```

**Restart services:**
```bash
docker-compose restart
```

### UI Not Loading

1. **Check if port 8501 is available:**
   ```bash
   lsof -i :8501
   ```

2. **Verify Streamlit is running:**
   ```bash
   docker-compose logs app | grep "You can now view"
   ```

3. **Try accessing:**
   - http://localhost:8501
   - http://127.0.0.1:8501

---

## Sample Queries and Expected Results

### Query 1: Emulation Mode

**Question:**
```
How do I disable emulation mode in eMMC?
```

**Expected Result:**
- **Top Section:** "6.6.34.1 Disabling emulation mode"
- **Confidence:** 85-95%
- **Content:** Instructions about USE_NATIVE_SECTOR field
- **Pages:** 128-130

### Query 2: HS400 Timing

**Question:**
```
What is HS400 timing mode?
```

**Expected Result:**
- **Top Section:** "6.6.2.3 The valid IO Voltage for HS400" or similar
- **Confidence:** 70-80%
- **Multiple Citations:** 3-5 HS400-related sections
- **Content:** HS400 specifications, voltage requirements, selection flow

### Query 3: RPMB Access

**Question:**
```
How does RPMB work?
```

**Expected Result:**
- **Top Section:** "RPMB Data Read Operation" or similar
- **Confidence:** 60-75%
- **Multiple Citations:** 3-5 RPMB-related sections
- **Content:** RPMB operation details, message types

---

## Advanced Features (Coming Soon)

### Hybrid Search
- Combination of vector search + keyword search (BM25)
- Better retrieval accuracy

### Re-Ranking
- LLM-based re-ranking of results
- Improved top-3 result selection

### Query Expansion
- Automatic synonym expansion
- Better handling of varied terminology

### Multi-Document Comparison
- Cross-reference between protocol versions
- Compare eMMC vs UFS features

---

## Support and Feedback

### View System Logs

```bash
# Application logs
docker-compose logs -f app

# Qdrant logs
docker-compose logs -f qdrant
```

### Stop Services

```bash
docker-compose down
```

### Restart Services

```bash
docker-compose restart
```

### Full Reset

```bash
# Stop and remove containers
docker-compose down

# Start fresh
docker-compose up -d
```

---

## System Requirements

### Minimum Requirements
- **RAM:** 4 GB
- **Storage:** 2 GB free space
- **Browser:** Modern browser (Chrome, Firefox, Safari, Edge)

### Recommended Requirements
- **RAM:** 8 GB+
- **Storage:** 5 GB+ free space
- **Network:** Internet connection (for API calls)

---

## Privacy and Security

- All processing happens locally in Docker containers
- Specifications are stored locally (not uploaded to cloud)
- Only LLM API calls go to DeepSeek servers:
  - Query embedding generation
  - Answer generation (with context from local chunks)
- No user data is collected or transmitted

---

## Version History

### v0.1.0 (2026-02-14) - MVP Release

**Features:**
- ✅ Basic RAG system with vector search
- ✅ Section-aware chunking (821 focused chunks)
- ✅ Citation tracking with accurate section titles
- ✅ Streamlit web interface
- ✅ eMMC 5.1 specification support
- ✅ Configurable retrieval settings

**Metrics:**
- Section title accuracy: 95.2%
- Focused chunks: 98%+
- Response time: <2 seconds
- Quality grade: B+ (Good)

---

## Quick Reference

### Access URLs
- **Web UI:** http://localhost:8501
- **Qdrant Dashboard:** http://localhost:6333/dashboard

### Common Commands
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Check status
docker-compose ps
```

### Best Practices
1. Start with specific technical questions
2. Use protocol terminology (RPMB, HS400, etc.)
3. Check citations for full context
4. Adjust settings if results aren't optimal
5. Try rephrasing if no results found

---

**Enjoy exploring storage protocol specifications with AI assistance!** 🚀

For technical details, see:
- **Architecture:** docs/PRD_V2.md
- **Implementation:** FINAL_RESULTS.md
- **Test Results:** RAG_TEST_RESULTS.md
