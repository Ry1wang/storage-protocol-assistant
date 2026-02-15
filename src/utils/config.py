"""Configuration management for the RAG system."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    deepseek_api_key: str = Field(..., alias="DEEPSEEK_API_KEY")

    # Qdrant Configuration
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")

    # Database Configuration
    database_path: str = Field(default="./data/metadata.db", alias="DATABASE_PATH")

    # Model Configuration
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL"
    )
    llm_model: str = Field(default="deepseek-reasoner", alias="LLM_MODEL")
    fast_model: str = Field(default="deepseek-chat", alias="FAST_MODEL")

    # Retrieval Configuration
    top_k: int = Field(default=10, alias="TOP_K")
    min_similarity: float = Field(default=0.7, alias="MIN_SIMILARITY")
    chunk_size: int = Field(default=350, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=30, alias="CHUNK_OVERLAP")

    # Chunking Strategy Configuration
    chunking_strategy: str = Field(default="section_aware", alias="CHUNKING_STRATEGY")  # Options: "simple", "semantic", "section_aware", "hybrid"
    min_chunk_size: int = Field(default=100, alias="MIN_CHUNK_SIZE")
    max_chunk_size: int = Field(default=800, alias="MAX_CHUNK_SIZE")
    section_boundary_levels: int = Field(default=3, alias="SECTION_BOUNDARY_LEVELS")  # How many section levels to respect (e.g., 3 = 6.6.34)
    allow_compound_titles: bool = Field(default=True, alias="ALLOW_COMPOUND_TITLES")

    # Application Configuration
    app_port: int = Field(default=8501, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
