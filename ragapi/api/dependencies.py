import logging
from typing import Optional

from ..config import settings
from ..document.chunker import TextChunker, get_chunker
from ..embedding.models import EmbeddingModel, get_embedding_model
from ..storage.base import BaseStorage
from ..storage.providers.filesystem import FilesystemStorage

logger = logging.getLogger("ragapi.dependencies")

# Keep singletons to avoid reinitializing
_storage: Optional[BaseStorage] = None
_embedding_model: Optional[EmbeddingModel] = None


async def get_storage() -> BaseStorage:
    """
    Get a configured storage instance.

    Returns:
        A BaseStorage implementation.
    """
    global _storage

    if _storage is None:
        _storage = FilesystemStorage()
        await _storage.initialize()

    return _storage


async def get_embedding_model_instance() -> EmbeddingModel:
    """
    Get a configured embedding model based on settings.

    Returns:
        An EmbeddingModel implementation.
    """
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = get_embedding_model()
        await _embedding_model.initialize()

    return _embedding_model


def get_text_chunker() -> TextChunker:
    """
    Get a configured text chunker.

    Returns:
        A TextChunker.
    """
    return get_chunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        use_semantic_chunking=settings.use_semantic_chunking
    )
