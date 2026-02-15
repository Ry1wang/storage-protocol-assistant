# Intermediate Process Documentation & Debug Scripts

This directory contains debugging scripts, investigation documents, and intermediate development artifacts that were created during the development and debugging of the TOC-based chunking system.

## Directory Structure

```
intermediate_process/
├── scripts/          # Debugging and investigation scripts
├── docs/            # Investigation and debugging documentation
└── *.md             # Process summaries and investigation results
```

## Purpose

These files document the development journey, debugging processes, and intermediate solutions that led to the final production implementation. They are preserved for:

1. **Historical Reference**: Understanding how problems were identified and solved
2. **Learning Resource**: Examples of debugging techniques and investigation approaches
3. **Audit Trail**: Complete record of the development process
4. **Future Debugging**: Reference material if similar issues arise

## Contents Overview

### Debugging Scripts (`scripts/`)

- **analyze_toc_entries.py** - Analyzes TOC extraction edge cases
- **correct_sections.py** - Script for correcting section titles using LLM
- **debug_section_text.py** - Extracts and displays raw PDF content for debugging
- **validate_sections.py** - Validates section coverage and accuracy
- **validate_title_number_approach.py** - Alternative validation approach

### Investigation Documentation (`docs/`)

- **CHUNKING_EXAMPLES.md** - Examples of chunking issues and solutions
- **CHUNKING_IMPROVEMENTS.md** - Documentation of chunking improvements
- **CHUNKING_STRATEGY.md** - Analysis of different chunking strategies
- **LLM_SECTION_CORRECTION.md** - LLM-based correction approach documentation
- **SECTION_AWARE_CHUNKING_GUIDE.md** - Guide for section-aware chunking
- **SECTION_TITLE_ISSUES.md** - Investigation of section title problems
- **SECTION_VALIDATION.md** - Section validation methodology

### Process Documentation (Root)

- **CHUNKING_ANALYSIS.md** - Comprehensive chunking analysis
- **CORRECTION_RESULTS.md** - Results from section correction experiments
- **DEPLOYMENT_COMPLETE.md** - Deployment completion record
- **FINAL_RESULTS.md** - Final test results before production
- **IMPLEMENTATION_PLAN.md** - Step-by-step implementation plan
- **INGESTION_COMPLETE.md** - Ingestion process completion record
- **INGESTION_FIXES.md** - Documentation of ingestion fixes
- **PROBLEM_INVESTIGATION_SUMMARY.md** - Summary of problem investigation
- **PROJECT_SUMMARY.md** - Interim project summary
- **RAG_TEST_RESULTS.md** - RAG system test results (80.7% score)
- **REINGEST_RESULTS.md** - Results from re-ingestion tests
- **SECTION_CORRECTION_QUICKSTART.md** - Quick start for section correction
- **SECTION_QA_SUMMARY.md** - Section quality assurance summary
- **SETUP_STATUS.md** - Initial setup status
- **TITLE_NUMBER_VALIDATION_REPORT.md** - Validation report for title extraction
- **TOC_EDGE_CASE_ANALYSIS.md** - Edge case analysis for TOC extraction
- **TOC_EDGE_CASE_SUMMARY.md** - Summary of TOC edge cases
- **TOC_EXTRACTION_TEST_REPORT.md** - TOC extraction test results

## Not for Production Use

**Important**: These scripts and documents are not part of the production system. They were used during development and debugging. For production usage, refer to:

- **Production Documentation**: See root-level `README.md`, `USER_GUIDE.md`
- **Deployment Guide**: See `DEPLOYMENT_CHECKLIST.md`, `MIGRATION_GUIDE.md`
- **Technical Reference**: See `TOC_CHUNKER_SUMMARY.md`, `TOC_CHUNKER_QUICKSTART.md`
- **Testing**: See `scripts/test_*.py` (in main scripts directory)

## Key Learnings

The development process documented here revealed several critical insights:

1. **TOC-based chunking** dramatically improved section coverage (71.9% → 98.6%)
2. **Subtitle detection** using multiple patterns achieved 63% accuracy
3. **Hierarchical section paths** require complete TOC lookup, not just active chunks
4. **Inferred section titles** should not be extracted from random page content
5. **Score thresholds** in vector search need careful tuning (default 0.7 was too high)

## Timeline

- **Initial Setup**: Feb 12, 2026
- **Problem Investigation**: Feb 13-14, 2026
- **TOC Chunker Development**: Feb 14-15, 2026
- **Final Fixes & Testing**: Feb 15, 2026
- **RAG Test Score**: 80.7% (GOOD ⭐⭐)

---

**Status**: Archived for reference
**Last Updated**: February 15, 2026
