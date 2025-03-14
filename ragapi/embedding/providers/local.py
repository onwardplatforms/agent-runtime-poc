import logging
import numpy as np
from typing import List, Dict, Any, Optional

from ..models import EmbeddingModel
from ...config import settings

logger = logging.getLogger("ragapi.embedding.local")

class SentenceTransformerEmbedding(EmbeddingModel):
    """Embedding model using SentenceTransformers."""
    
    def __init__(self, model_name: str = None):
        """
        Initialize the SentenceTransformer embedding model.
        
        Args:
            model_name: Name of the SentenceTransformer model to use
        """
        self.model_name = model_name or settings.embedding_model
        self.model = None
        self._embedding_dim = None
    
    async def initialize(self) -> None:
        """Initialize the embedding model."""
        try:
            # Import here to avoid dependency if not using this model
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            
            # Get embedding dimension by embedding a test string
            test_embedding = self.model.encode(["test"])
            self._embedding_dim = test_embedding.shape[1]
            
            logger.info(f"Initialized embedding model with dimension: {self._embedding_dim}")
        except ImportError:
            logger.error("SentenceTransformers not installed. Please install with 'pip install sentence-transformers'")
            raise
        except Exception as e:
            logger.error(f"Error initializing embedding model: {str(e)}")
            raise
    
    async def get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a list of texts."""
        if not self.model:
            await self.initialize()
            
        try:
            # Encode all texts at once for efficiency
            embeddings = self.model.encode(texts)
            
            # Convert to list of numpy arrays
            return [embedding for embedding in embeddings]
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    @property
    def embedding_dim(self) -> int:
        """Get the dimension of the embeddings."""
        if self._embedding_dim is None:
            raise ValueError("Model not initialized. Call initialize() first.")
        return self._embedding_dim
