from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
import numpy as np
import logging
import os
from pathlib import Path

from ..config import settings

logger = logging.getLogger("ragapi.embedding")


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the embedding model."""
        pass
    
    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings as numpy arrays
        """
        pass
    
    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Get the dimension of the embeddings."""
        pass


def get_embedding_model() -> EmbeddingModel:
    """
    Get the configured embedding model based on settings.
    
    Returns:
        An initialized embedding model
    """
    embedding_provider = os.environ.get("RAG_EMBEDDING_PROVIDER", "local").lower()
    
    if embedding_provider == "openai":
        # Use OpenAI embeddings if specified
        from .providers.openai import OpenAIEmbedding
        openai_model = os.environ.get("RAG_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        logger.info(f"Using OpenAI embedding provider with model: {openai_model}")
        return OpenAIEmbedding(model_name=openai_model)
    else:
        # Default to local SentenceTransformers
        from .providers.local import SentenceTransformerEmbedding
        logger.info(f"Using local SentenceTransformer embedding provider with model: {settings.embedding_model}")
        return SentenceTransformerEmbedding(model_name=settings.embedding_model)
