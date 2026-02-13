"""Test configuration and utilities."""

import pytest
from src.utils.config import Settings


def test_settings_defaults():
    """Test that settings have sensible defaults."""
    # This will fail without a .env file, but that's expected
    # Just testing the structure
    assert Settings.model_config["env_file"] == ".env"
    assert Settings.model_config["case_sensitive"] == False


def test_settings_structure():
    """Test settings class structure."""
    # Verify key fields exist
    fields = Settings.model_fields
    assert "deepseek_api_key" in fields
    assert "qdrant_url" in fields
    assert "embedding_model" in fields
    assert "top_k" in fields
