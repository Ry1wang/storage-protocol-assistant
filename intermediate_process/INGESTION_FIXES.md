# Ingestion Pipeline - Issues Fixed ✅

## Problem Summary

When trying to run `make ingest FILE=/app/specs/emmc5.1-protocol-JESD84-B51.pdf PROTOCOL=eMMC VERSION=5.1`, several errors were encountered and resolved.

## Issues Encountered & Solutions

### Issue 1: Module Not Found
**Error:**
```
No module named src.ingestion.ingest_spec
```

**Root Cause:** Docker container was built before the ingestion module files were created.

**Solution:** Rebuilt the Docker image to include the new ingestion code:
```bash
docker-compose build app
docker-compose up -d app
```

---

### Issue 2: OpenCV Missing GL Dependencies
**Error:**
```
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

**Root Cause:** The `unstructured[pdf]` library depends on OpenCV, which by default requires OpenGL libraries for GUI support. These libraries weren't installed in the slim Docker image.

**Solution:**
1. Installed `opencv-python-headless` instead of the GUI version
2. Modified Dockerfile to uninstall `opencv-python` and keep only `opencv-python-headless`

```dockerfile
# Uninstall GUI version of OpenCV and install headless version
RUN pip uninstall -y opencv-python && \
    pip install --no-cache-dir opencv-python-headless
```

---

### Issue 3: NumPy Version Incompatibility
**Error:**
```
ImportError: Numba needs NumPy 2.3 or less. Got NumPy 2.4.
```

**Root Cause:** The `numba` library (required by `unstructured`) doesn't support NumPy 2.4+.

**Solution:** Pinned NumPy to a compatible version in `requirements.txt`:
```
numpy>=1.26.4,<2.3  # Numba compatibility
```

---

## Files Modified

### 1. `Dockerfile`
**Changes:**
- Removed Tsinghua mirror replacement (was causing network issues)
- Removed unnecessary OpenGL libraries
- Added OpenCV headless installation after requirements

**Final Dockerfile changes:**
```dockerfile
# Install system dependencies (simplified)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    poppler-utils \
    libmagic-dev \
    tesseract-ocr \
    curl \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Uninstall GUI version of OpenCV and install headless version
RUN pip uninstall -y opencv-python && \
    pip install --no-cache-dir opencv-python-headless
```

### 2. `requirements.txt`
**Changes:**
- Updated NumPy version constraint to ensure Numba compatibility

```diff
- numpy==1.26.4
+ numpy>=1.26.4,<2.3  # Numba compatibility
```

---

## Verification

After all fixes, the ingestion pipeline works successfully:

```bash
$ make ingest FILE=/app/specs/emmc5.1-protocol-JESD84-B51.pdf PROTOCOL=eMMC VERSION=5.1

✓ Document ingested successfully!
  Document ID: eMMC_5_1_a272493d
  Protocol: eMMC v5.1

# Ingestion Stats:
- Extracted: 9371 elements from PDF
- Created: 382 semantic chunks
- Total Pages: 352
- Processing time: ~35 seconds
```

```bash
$ make list

Found 1 document(s):
----------------------------------------------------------------------------------------------------
Protocol        Version    Title                          Pages    Chunks   Uploaded
----------------------------------------------------------------------------------------------------
eMMC            5.1        emmc5.1-protocol-JESD84-B51    352      382      2026-02-14 05:06:44
----------------------------------------------------------------------------------------------------
```

**Qdrant Verification:**
- 382 vectors successfully stored in `protocol_specs` collection
- View at: http://localhost:6333/dashboard

---

## Key Takeaways

1. **Docker Rebuild Required:** Any time new Python code is added, rebuild the Docker image
2. **OpenCV in Containers:** Always use `opencv-python-headless` for headless environments
3. **Dependency Compatibility:** Pin versions carefully when using libraries with strict requirements (like Numba)
4. **Testing Strategy:** Test imports before running full pipeline

---

## Commands Reference

### Rebuild and Test
```bash
# Rebuild Docker image
docker-compose build app

# Restart container
docker-compose up -d app

# Test module import
docker-compose exec app python -c "import src.ingestion.ingest_spec; print('✓ OK')"

# Ingest a document
make ingest FILE=/app/specs/your_file.pdf PROTOCOL=ProtocolName VERSION=X.Y

# List documents
make list

# View logs
docker-compose logs -f app
```

### Troubleshooting
```bash
# Check installed packages
docker-compose exec app pip list | grep opencv
docker-compose exec app pip list | grep numpy

# Check Qdrant
docker-compose exec app python -c "from src.database.qdrant_client import QdrantVectorStore; vs = QdrantVectorStore(); print(vs.client.count('protocol_specs'))"

# Shell access
make shell
```

---

## Status

✅ **All Issues Resolved**
- PDF parsing: Working
- Chunking: Working
- Embedding generation: Working
- Vector storage: Working
- Metadata storage: Working

The ingestion pipeline is now fully operational and ready for use!

---

**Date Fixed:** 2026-02-14
**Fixed By:** Claude Code Assistant
**Test Document:** emmc5.1-protocol-JESD84-B51.pdf (352 pages, 382 chunks)
