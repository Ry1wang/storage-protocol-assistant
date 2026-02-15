"""Factory for creating chunker instances based on configuration."""

from typing import Union

from .chunker import SemanticChunker, SimpleChunker
from .section_aware_chunker import SectionAwareChunker, HybridChunker
from ..utils.config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


def create_chunker(
    strategy: str = None,
    chunk_size: int = None,
    chunk_overlap: int = None,
    **kwargs
) -> Union[SimpleChunker, SemanticChunker, SectionAwareChunker, HybridChunker]:
    """
    Create a chunker instance based on strategy.

    Args:
        strategy: Chunking strategy ("simple", "semantic", "section_aware", "hybrid")
                 Defaults to settings.chunking_strategy
        chunk_size: Target chunk size in tokens (defaults to settings.chunk_size)
        chunk_overlap: Chunk overlap in tokens (defaults to settings.chunk_overlap)
        **kwargs: Additional arguments passed to chunker constructor

    Returns:
        Chunker instance

    Examples:
        >>> # Use default strategy from config
        >>> chunker = create_chunker()

        >>> # Override strategy
        >>> chunker = create_chunker(strategy="section_aware")

        >>> # Custom parameters
        >>> chunker = create_chunker(
        ...     strategy="section_aware",
        ...     chunk_size=400,
        ...     min_chunk_size=150
        ... )
    """
    strategy = strategy or settings.chunking_strategy
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    logger.info(f"Creating chunker: strategy={strategy}, size={chunk_size}, overlap={chunk_overlap}")

    if strategy == "simple":
        return SimpleChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            **kwargs
        )

    elif strategy == "semantic":
        return SemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            **kwargs
        )

    elif strategy == "section_aware":
        return SectionAwareChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=kwargs.get("min_chunk_size", settings.min_chunk_size),
            max_chunk_size=kwargs.get("max_chunk_size", settings.max_chunk_size),
            section_boundary_levels=kwargs.get(
                "section_boundary_levels",
                settings.section_boundary_levels
            ),
            **{k: v for k, v in kwargs.items() if k not in [
                "min_chunk_size", "max_chunk_size", "section_boundary_levels"
            ]}
        )

    elif strategy == "hybrid":
        return HybridChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=kwargs.get("min_chunk_size", settings.min_chunk_size),
            max_chunk_size=kwargs.get("max_chunk_size", settings.max_chunk_size),
            section_boundary_levels=kwargs.get(
                "section_boundary_levels",
                settings.section_boundary_levels
            ),
            allow_compound_titles=kwargs.get(
                "allow_compound_titles",
                settings.allow_compound_titles
            ),
            **{k: v for k, v in kwargs.items() if k not in [
                "min_chunk_size", "max_chunk_size", "section_boundary_levels",
                "allow_compound_titles"
            ]}
        )

    else:
        raise ValueError(
            f"Unknown chunking strategy: {strategy}. "
            f"Valid options: simple, semantic, section_aware, hybrid"
        )


def get_default_chunker() -> Union[SimpleChunker, SemanticChunker, SectionAwareChunker, HybridChunker]:
    """
    Get chunker with default settings from configuration.

    Returns:
        Configured chunker instance
    """
    return create_chunker()
