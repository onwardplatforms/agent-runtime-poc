import os
import logging
import numpy as np
from typing import List, Dict, Any, Optional
import aiohttp
import json

from ..models import EmbeddingModel
from ...config import settings

logger = logging.getLogger("ragapi.embedding.openai")

class OpenAIEmbedding(EmbeddingModel):
    """Embedding model using OpenAI's embeddings API."""
    
    def __init__(self, model_name: str = "text-embedding-3-small"):
        """
        Initialize the OpenAI embedding model.
        
        Args:
            model_name: Name of the OpenAI embedding model to use
                        Options: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
        """
        self.model_name = model_name
        self._embedding_dim = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }.get(model_name, 1536)  # Default to 1536 if model not known
        
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY environment variable is not set")
    
    async def initialize(self) -> None:
        """Initialize the embedding model."""
        # Check if API key is available
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set the OPENAI_API_KEY environment variable.")
            
        logger.info(f"Initialized OpenAI embedding model: {self.model_name} with dimension: {self._embedding_dim}")
    
    async def create_session(self):
        """Create an aiohttp ClientSession - extracted for testability."""
        return aiohttp.ClientSession()
    
    async def get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for a list of texts using OpenAI API.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings as numpy arrays
        """
        if not self.api_key:
            await self.initialize()
            
        if not texts:
            return []
            
        try:
            # Use OpenAI API to get embeddings
            embeddings = []
            
            # Process in chunks of 20 to avoid rate limits and large payloads
            chunk_size = 20
            for i in range(0, len(texts), chunk_size):
                chunk = texts[i:i+chunk_size]
                
                # Make the API request
                async with await self.create_session() as session:
                    endpoint = "https://api.openai.com/v1/embeddings"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                    data = {
                        "input": chunk,
                        "model": self.model_name
                    }
                    
                    logger.debug(f"Sending request to OpenAI for {len(chunk)} texts")
                    
                    async with session.post(endpoint, headers=headers, json=data) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"OpenAI API error: {response.status} - {error_text}")
                            raise Exception(f"OpenAI API error: {response.status} - {error_text}")
                            
                        json_response = await response.json()
                        
                        # Extract embeddings from response
                        for item in json_response.get("data", []):
                            embedding = np.array(item["embedding"], dtype=np.float32)
                            embeddings.append(embedding)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings with OpenAI: {str(e)}")
            raise
    
    @property
    def embedding_dim(self) -> int:
        """Get the dimension of the embeddings."""
        return self._embedding_dim 