"""Shared test fixtures for the Storage Protocol Assistant test suite."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.models.schemas import DocumentChunk, ChunkMetadata, DocumentMetadata


# ---------------------------------------------------------------------------
# Sample chunk data representing an eMMC specification
# ---------------------------------------------------------------------------

SAMPLE_CHUNKS = [
    # CSD Register (factual/definition)
    {
        "chunk_id": "csd_1",
        "text": (
            "The Card-Specific Data (CSD) register provides information on how to "
            "access the card contents. The CSD contains fields such as TAAC, NSAC, "
            "TRAN_SPEED, and data read/write access time parameters."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [45],
        "section_title": "CSD Register",
        "section_path": "7.1 CSD Register",
        "chunk_type": "text",
    },
    # TAAC field
    {
        "chunk_id": "taac_1",
        "text": (
            "The TAAC (data read access time-1) field defines the asynchronous part "
            "of the data access time. TAAC contains a time unit and a multiplier "
            "value for calculating the data read access time."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [46],
        "section_title": "TAAC Field",
        "section_path": "7.1.1 TAAC",
        "chunk_type": "text",
    },
    # Boot partition
    {
        "chunk_id": "boot_part_1",
        "text": (
            "The boot partition size is defined by the BOOT_SIZE_MULT field in "
            "EXT_CSD register. Each boot partition has a size of 128KB * BOOT_SIZE_MULT. "
            "The maximum boot partition size is 128KB * 255 = 32640KB."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [50],
        "section_title": "Boot Partition",
        "section_path": "6.3.1 Boot Partition Size",
        "chunk_type": "text",
    },
    # RPMB (definition/comparison)
    {
        "chunk_id": "rpmb_1",
        "text": (
            "Replay Protected Memory Block (RPMB) is an authenticated and replay "
            "protected data storage partition. RPMB uses HMAC SHA-256 for authentication "
            "and a write counter to prevent replay attacks."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [80],
        "section_title": "RPMB",
        "section_path": "6.6.22 RPMB",
        "chunk_type": "text",
    },
    # Regular partitions (for comparison with RPMB)
    {
        "chunk_id": "partitions_1",
        "text": (
            "Regular user data partitions provide standard read/write access without "
            "authentication. Unlike RPMB, regular partitions do not have replay "
            "protection or HMAC-based security mechanisms."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [75],
        "section_title": "User Data Partitions",
        "section_path": "6.6.1 User Data Area",
        "chunk_type": "text",
    },
    # HS200 mode (comparison/specification)
    {
        "chunk_id": "hs200_1",
        "text": (
            "HS200 mode operates at up to 200MHz with single data rate (SDR), "
            "achieving 200MB/s throughput on an 8-bit bus. HS200 requires 1.8V "
            "signaling voltage for high-speed operation."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [30],
        "section_title": "HS200",
        "section_path": "6.6.2 HS200",
        "chunk_type": "text",
    },
    # HS400 mode
    {
        "chunk_id": "hs400_1",
        "text": (
            "HS400 mode operates at 200MHz with dual data rate (DDR), achieving "
            "400MB/s throughput. HS400 requires the device to first enter HS200 mode "
            "before switching to HS400. The voltage requirement is 1.8V."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [31],
        "section_title": "HS400",
        "section_path": "6.6.3 HS400",
        "chunk_type": "text",
    },
    # CMD1 timing (specification)
    {
        "chunk_id": "timing_1",
        "text": (
            "CMD1 timing: The device shall respond within 1ms after CMD1 is sent. "
            "The busy signal (DAT0 low) may last up to 1 second during the "
            "initialization process. The host shall wait for busy to clear."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [60],
        "section_title": "Command Timing",
        "section_path": "10.2 Command Timing",
        "chunk_type": "text",
    },
    # Voltage requirements
    {
        "chunk_id": "voltage_1",
        "text": (
            "The eMMC device supports two voltage ranges: 2.7V-3.6V for normal "
            "operation and 1.70V-1.95V for low-voltage signaling. The I/O voltage "
            "for HS200 and HS400 modes must be in the 1.70V-1.95V range."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [25],
        "section_title": "Voltage Requirements",
        "section_path": "5.1 Voltage Requirements",
        "chunk_type": "text",
    },
    # Boot operation (procedural)
    {
        "chunk_id": "boot_1",
        "text": (
            "Boot operation sequence: 1) Assert CMD line low for at least 74 clock "
            "cycles, 2) Send CMD0 to reset, 3) Send CMD1 with voltage window, "
            "4) Wait for device ready, 5) Read boot data from boot partition."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [100],
        "section_title": "Boot Mode",
        "section_path": "6.3 Boot Mode",
        "chunk_type": "text",
    },
    # Device initialization (procedural)
    {
        "chunk_id": "init_1",
        "text": (
            "Device initialization steps: Step 1: Send CMD0 (GO_IDLE_STATE). "
            "Step 2: Send CMD1 with OCR (voltage window). Step 3: Wait for "
            "busy bit to clear. Step 4: Send CMD2 to get CID. Step 5: Send CMD3 "
            "to assign RCA."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [55],
        "section_title": "Initialization",
        "section_path": "9.1 Device Initialization",
        "chunk_type": "text",
    },
    # RPMB enable procedure
    {
        "chunk_id": "rpmb_proc_1",
        "text": (
            "To enable RPMB: 1) Write the authentication key to RPMB using the "
            "authenticated data write sequence, 2) Verify key programming via "
            "authenticated read, 3) The write counter starts at 0 after key "
            "programming. Prerequisites: Device must be initialized."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [82],
        "section_title": "RPMB Setup",
        "section_path": "6.6.22.1 RPMB Key Programming",
        "chunk_type": "text",
    },
    # HS400 configuration procedure
    {
        "chunk_id": "hs400_proc_1",
        "text": (
            "To configure HS400 mode: 1) Initialize device, 2) Switch to HS200 "
            "mode by writing to EXT_CSD, 3) Perform HS200 tuning, 4) Switch to "
            "HS400 by changing bus timing in EXT_CSD, 5) Verify with a read operation."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [32],
        "section_title": "HS400 Configuration",
        "section_path": "6.6.3.1 HS400 Configuration",
        "chunk_type": "text",
    },
    # Boot troubleshooting
    {
        "chunk_id": "boot_err_1",
        "text": (
            "Boot failure causes: incorrect boot partition configuration via "
            "BOOT_CONFIG in EXT_CSD, voltage out of range for the selected mode, "
            "clock frequency exceeding device capability, or corrupted boot data."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [102],
        "section_title": "Boot Troubleshooting",
        "section_path": "6.3.5 Boot Troubleshooting",
        "chunk_type": "text",
    },
    # Initialization errors
    {
        "chunk_id": "init_err_1",
        "text": (
            "Initialization error conditions: No response to CMD1 indicates device "
            "not present or voltage mismatch. Timeout on busy signal suggests device "
            "malfunction. CRC errors during CMD2/CMD3 indicate communication issues."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [57],
        "section_title": "Initialization Errors",
        "section_path": "9.3 Error Handling",
        "chunk_type": "text",
    },
    # Command timeout debugging
    {
        "chunk_id": "cmd_timeout_1",
        "text": (
            "Command timeout debugging: Check clock frequency matches device capability. "
            "Verify voltage levels. Ensure DAT0 is not held low by another device. "
            "Monitor CMD line for proper signaling. Check host controller timeout settings."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [110],
        "section_title": "Timeout Debugging",
        "section_path": "12.1 Command Timeout",
        "chunk_type": "text",
    },
    # CSD definition expansion
    {
        "chunk_id": "csd_def_1",
        "text": (
            "CSD stands for Card-Specific Data. It is a 128-bit register that "
            "stores device configuration parameters including maximum data transfer "
            "rate, supported command classes, and card capacity."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [44],
        "section_title": "CSD Definition",
        "section_path": "7.1 CSD Register",
        "chunk_type": "text",
    },
    # Packed commands definition
    {
        "chunk_id": "packed_cmd_1",
        "text": (
            "Packed commands allow the host to group multiple read or write commands "
            "into a single packed command sequence, reducing protocol overhead and "
            "improving throughput for small block transfers."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [90],
        "section_title": "Packed Commands",
        "section_path": "6.6.30 Packed Commands",
        "chunk_type": "text",
    },
    # SDR/DDR (comparison)
    {
        "chunk_id": "sdr_ddr_1",
        "text": (
            "Single data rate (SDR) transfers data on one clock edge, while dual "
            "data rate (DDR) transfers on both rising and falling edges, doubling "
            "throughput at the same clock frequency. DDR52 achieves 52MB/s at 52MHz."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [28],
        "section_title": "Data Rate Modes",
        "section_path": "6.6.1 SDR and DDR",
        "chunk_type": "text",
    },
    # Maximum HS400 frequency
    {
        "chunk_id": "hs400_freq_1",
        "text": (
            "The maximum clock frequency for HS400 mode is 200MHz. At 200MHz with "
            "dual data rate on an 8-bit bus, the maximum throughput is 400MB/s. "
            "The minimum frequency for HS400 is 0MHz (clock can stop)."
        ),
        "doc_id": "emmc_51",
        "page_numbers": [33],
        "section_title": "HS400 Frequency",
        "section_path": "6.6.3.2 HS400 Clock",
        "chunk_type": "text",
    },
    # Extra doc for multi-doc testing
    {
        "chunk_id": "ufs_1",
        "text": (
            "UFS uses a serial interface with MIPI UniPro and M-PHY. "
            "It supports full duplex communication unlike eMMC which is half duplex."
        ),
        "doc_id": "ufs_31",
        "page_numbers": [10],
        "section_title": "UFS Architecture",
        "section_path": "1.1 UFS Architecture",
        "chunk_type": "text",
    },
]


def _make_search_result(chunk: dict, score: float = 0.8) -> dict:
    """Convert a sample chunk dict to a search result dict."""
    return {
        "chunk_id": chunk["chunk_id"],
        "text": chunk["text"],
        "doc_id": chunk["doc_id"],
        "page_numbers": chunk["page_numbers"],
        "section_title": chunk["section_title"],
        "section_path": chunk["section_path"],
        "score": score,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chunks():
    """Return the full list of sample eMMC chunks."""
    return [dict(c) for c in SAMPLE_CHUNKS]


@pytest.fixture
def sample_emmc_chunks():
    """Return only eMMC doc chunks (doc_id='emmc_51')."""
    return [dict(c) for c in SAMPLE_CHUNKS if c["doc_id"] == "emmc_51"]


@pytest.fixture
def sample_document_chunks():
    """Return sample chunks as DocumentChunk models."""
    chunks = []
    for c in SAMPLE_CHUNKS[:5]:
        meta = ChunkMetadata(
            doc_id=c["doc_id"],
            chunk_id=c["chunk_id"],
            page_numbers=c["page_numbers"],
            section_title=c["section_title"],
            section_path=c["section_path"],
            chunk_type=c.get("chunk_type", "text"),
        )
        chunks.append(DocumentChunk(text=c["text"], metadata=meta))
    return chunks


@pytest.fixture
def sample_doc_metadata():
    """Return a sample DocumentMetadata instance."""
    return DocumentMetadata(
        doc_id="emmc_51",
        title="eMMC Specification v5.1",
        protocol="eMMC",
        version="5.1",
        file_path="/specs/emmc_5.1.pdf",
        uploaded_at=datetime(2026, 1, 15, 10, 0, 0),
        total_pages=250,
        total_chunks=20,
        is_active=True,
    )


@pytest.fixture
def mock_vector_store():
    """QdrantVectorStore with a mocked Qdrant client."""
    with patch("src.database.qdrant_client.QdrantClient") as mock_qc, \
         patch("src.database.qdrant_client.SentenceTransformer") as mock_st:

        # Embedding model mock
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)
        mock_st.return_value = mock_model

        # Qdrant client mock - collection exists
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "protocol_specs"
        mock_client.get_collections.return_value = MagicMock(
            collections=[mock_collection]
        )
        mock_qc.return_value = mock_client

        from src.database.qdrant_client import QdrantVectorStore
        store = QdrantVectorStore()

        yield store


@pytest.fixture
def mock_sqlite_client(tmp_path):
    """SQLiteClient backed by in-memory or temp-file DB."""
    db_path = str(tmp_path / "test_metadata.db")
    with patch("src.database.sqlite_client.settings") as mock_settings:
        mock_settings.database_path = db_path
        from src.database.sqlite_client import SQLiteClient
        client = SQLiteClient(db_path=db_path)
        yield client


@pytest.fixture
def mock_deepseek_client():
    """DeepSeekClient with mocked API calls."""
    with patch("src.utils.deepseek_client.settings") as mock_settings:
        mock_settings.deepseek_api_key = "test-api-key"

        from src.utils.deepseek_client import DeepSeekClient
        with patch.object(DeepSeekClient, "__init__", lambda self, *a, **kw: None):
            client = DeepSeekClient.__new__(DeepSeekClient)
            client.api_key = "test-api-key"
            client.client = MagicMock()
            yield client


@pytest.fixture
def mock_classify_response():
    """Factory for mock classify_query responses."""
    def _make(category="factual", confidence=1.0):
        return {
            "category": category,
            "confidence": confidence,
            "reasoning": f"Classified as '{category}'",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "latency": 0.5,
            },
        }
    return _make


@pytest.fixture
def mock_generate_response():
    """Factory for mock generate_answer responses."""
    def _make(answer="According to [1], the value is 3.3V.", model="deepseek-reasoner"):
        return {
            "answer": answer,
            "model": model,
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 200,
                "total_tokens": 700,
            },
            "latency": 2.0,
        }
    return _make


@pytest.fixture
def search_results():
    """Provide pre-built search results from sample chunks."""
    return [
        _make_search_result(SAMPLE_CHUNKS[0], 0.85),
        _make_search_result(SAMPLE_CHUNKS[1], 0.78),
        _make_search_result(SAMPLE_CHUNKS[2], 0.72),
        _make_search_result(SAMPLE_CHUNKS[3], 0.68),
        _make_search_result(SAMPLE_CHUNKS[4], 0.60),
    ]
