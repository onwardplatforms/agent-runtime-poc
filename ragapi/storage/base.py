from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import uuid
import numpy as np
from datetime import datetime


class Chunk:
    """A chunk of text with its embedding and metadata."""
    def __init__(
        self,
        text: str,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ):
        self.chunk_id = chunk_id or str(uuid.uuid4())
        self.document_id = document_id
        self.text = text
        self.embedding = embedding
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        
    def dict(self, include_embedding: bool = False) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
        if include_embedding and self.embedding is not None:
            result["embedding"] = self.embedding.tolist()
        return result


class BaseStorage(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage."""
        pass
        
    @abstractmethod
    async def add_chunks(
        self, chunks: List[Chunk], conversation_id: Optional[str] = None
    ) -> List[str]:
        """
        Add chunks to the storage.
        
        Args:
            chunks: List of chunks to add
            conversation_id: Optional conversation ID
            
        Returns:
            List of chunk IDs that were added
        """
        pass
        
    @abstractmethod
    async def get_chunk(
        self, chunk_id: str, conversation_id: Optional[str] = None
    ) -> Optional[Chunk]:
        """
        Get a chunk by ID.
        
        Args:
            chunk_id: The ID of the chunk to retrieve
            conversation_id: Optional conversation ID
            
        Returns:
            The chunk if found, None otherwise
        """
        pass
        
    @abstractmethod
    async def search_chunks(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        conversation_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Search for chunks by similarity to the query embedding.
        
        Args:
            query_embedding: The query embedding to search for
            top_k: Number of results to return
            conversation_id: Optional conversation ID
            filters: Optional metadata filters
            
        Returns:
            List of chunks, ordered by similarity
        """
        pass
        
    @abstractmethod
    async def delete_document(
        self, document_id: str, conversation_id: Optional[str] = None
    ) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: The document ID to delete
            conversation_id: Optional conversation ID
            
        Returns:
            Number of chunks deleted
        """
        pass
        
    @abstractmethod
    async def list_documents(
        self, conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all documents.
        
        Args:
            conversation_id: Optional conversation ID
            
        Returns:
            List of document metadata
        """
        pass
