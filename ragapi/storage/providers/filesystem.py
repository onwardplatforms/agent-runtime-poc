import os
import json
import numpy as np
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
import logging
import shutil
from datetime import datetime
import pickle
import uuid

from ...config import settings
from ...storage.base import BaseStorage, Chunk

logger = logging.getLogger("ragapi.storage.filesystem")


class FilesystemStorage(BaseStorage):
    """Storage backend using the filesystem to store embeddings and metadata."""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the filesystem storage.
        
        Args:
            base_dir: Base directory for embeddings. If None, uses the configured embeddings_path.
        """
        self.base_dir = Path(base_dir or settings.embeddings_path)
        self.index = {}  # In-memory index for quick access
        
    async def initialize(self) -> None:
        """Initialize the storage."""
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Initialized filesystem storage at {self.base_dir}")
        
        # Load any existing indexes
        await self._load_indexes()
        
    async def _load_indexes(self) -> None:
        """Load existing indexes from the filesystem."""
        # Check all conversation directories
        for conv_dir in self.base_dir.glob("*"):
            if not conv_dir.is_dir():
                continue
                
            # Try to load the index file for this conversation
            index_path = conv_dir / "index.json"
            if index_path.exists():
                try:
                    with open(index_path, "r") as f:
                        conv_index = json.load(f)
                        conversation_id = conv_dir.name
                        self.index[conversation_id] = conv_index
                        logger.info(f"Loaded index for conversation {conversation_id} with {len(conv_index)} entries")
                except Exception as e:
                    logger.error(f"Error loading index from {index_path}: {str(e)}")
        
        # Also load the root index
        root_index_path = self.base_dir / "index.json"
        if root_index_path.exists():
            try:
                with open(root_index_path, "r") as f:
                    root_index = json.load(f)
                    self.index[None] = root_index
                    logger.info(f"Loaded root index with {len(root_index)} entries")
            except Exception as e:
                logger.error(f"Error loading root index: {str(e)}")
                
    async def _save_index(self, conversation_id: Optional[str] = None) -> None:
        """Save the index to the filesystem."""
        if conversation_id:
            index_dir = self.base_dir / conversation_id
        else:
            index_dir = self.base_dir
            
        os.makedirs(index_dir, exist_ok=True)
        
        index_path = index_dir / "index.json"
        try:
            conv_index = self.index.get(conversation_id, {})
            with open(index_path, "w") as f:
                json.dump(conv_index, f, indent=2)
            logger.info(f"Saved index to {index_path}")
        except Exception as e:
            logger.error(f"Error saving index to {index_path}: {str(e)}")
            
    def _get_chunk_path(self, chunk_id: str, conversation_id: Optional[str] = None) -> Path:
        """Get the path for a chunk file."""
        if conversation_id:
            return self.base_dir / conversation_id / f"{chunk_id}.pickle"
        else:
            return self.base_dir / f"{chunk_id}.pickle"
            
    async def add_chunks(
        self, chunks: List[Chunk], conversation_id: Optional[str] = None
    ) -> List[str]:
        """Add chunks to the storage."""
        if not chunks:
            return []
            
        # Initialize if needed
        if not os.path.exists(self.base_dir):
            await self.initialize()
            
        # Ensure we have an index for this conversation
        if conversation_id not in self.index:
            self.index[conversation_id] = {}
            
        # Ensure directory exists
        if conversation_id:
            chunk_dir = self.base_dir / conversation_id
        else:
            chunk_dir = self.base_dir
            
        os.makedirs(chunk_dir, exist_ok=True)
        
        # Save each chunk
        chunk_ids = []
        for chunk in chunks:
            # Save the chunk to a pickle file
            chunk_path = self._get_chunk_path(chunk.chunk_id, conversation_id)
            
            try:
                with open(chunk_path, "wb") as f:
                    pickle.dump(chunk, f)
                    
                # Update the index
                self.index[conversation_id][chunk.chunk_id] = {
                    "document_id": chunk.document_id,
                    "path": str(chunk_path),
                    "created_at": datetime.now().isoformat(),
                    "metadata": chunk.metadata,
                }
                
                chunk_ids.append(chunk.chunk_id)
                
            except Exception as e:
                logger.error(f"Error saving chunk {chunk.chunk_id}: {str(e)}")
                
        # Save the updated index
        await self._save_index(conversation_id)
        
        logger.info(f"Added {len(chunk_ids)} chunks to storage")
        return chunk_ids
        
    async def get_chunk(
        self, chunk_id: str, conversation_id: Optional[str] = None
    ) -> Optional[Chunk]:
        """Get a chunk by ID."""
        # Check if the chunk exists in our index
        conv_index = self.index.get(conversation_id, {})
        if chunk_id not in conv_index:
            logger.warning(f"Chunk {chunk_id} not found in index for conversation {conversation_id}")
            return None
            
        # Get the chunk path
        chunk_path = Path(conv_index[chunk_id]["path"])
        
        try:
            with open(chunk_path, "rb") as f:
                chunk = pickle.load(f)
            return chunk
        except Exception as e:
            logger.error(f"Error loading chunk {chunk_id}: {str(e)}")
            return None
            
    async def search_chunks(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        conversation_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """Search for chunks by similarity to the query embedding."""
        # Initialize results
        results = []
        
        # Get the relevant index
        conv_index = self.index.get(conversation_id, {})
        
        # Load all chunks and compute similarity
        for chunk_id, chunk_info in conv_index.items():
            # Apply filters if provided
            if filters and not self._matches_filters(chunk_info, filters):
                continue
                
            # Load the chunk
            chunk = await self.get_chunk(chunk_id, conversation_id)
            if not chunk or chunk.embedding is None:
                continue
                
            # Compute similarity
            similarity = self._compute_similarity(query_embedding, chunk.embedding)
            
            # Add to results with the similarity score
            chunk.metadata["score"] = float(similarity)
            results.append((chunk, similarity))
            
        # Sort by similarity (descending) and take top_k
        results.sort(key=lambda x: x[1], reverse=True)
        top_results = [chunk for chunk, _ in results[:top_k]]
        
        logger.info(f"Found {len(top_results)} chunks matching query")
        return top_results
        
    def _compute_similarity(self, query_embedding: np.ndarray, chunk_embedding: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        # Normalize embeddings for cosine similarity
        query_norm = np.linalg.norm(query_embedding)
        chunk_norm = np.linalg.norm(chunk_embedding)
        
        if query_norm == 0 or chunk_norm == 0:
            return 0.0
            
        return np.dot(query_embedding, chunk_embedding) / (query_norm * chunk_norm)
        
    def _matches_filters(self, chunk_info: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if a chunk matches the given filters."""
        metadata = chunk_info.get("metadata", {})
        
        for key, value in filters.items():
            # Special handling for document_id which may be at the chunk_info level
            if key == "document_id" and "document_id" in chunk_info:
                if chunk_info["document_id"] != value:
                    return False
            
            # Check in metadata
            elif key in metadata and metadata[key] != value:
                return False
                
        return True
        
    async def delete_document(
        self, document_id: str, conversation_id: Optional[str] = None
    ) -> int:
        """Delete all chunks for a document."""
        # Get the relevant index
        conv_index = self.index.get(conversation_id, {})
        
        # Find all chunks for this document
        document_chunks = []
        for chunk_id, chunk_info in conv_index.items():
            if chunk_info.get("document_id") == document_id:
                document_chunks.append(chunk_id)
                
        # Delete each chunk
        deleted_count = 0
        for chunk_id in document_chunks:
            chunk_path = Path(conv_index[chunk_id]["path"])
            try:
                # Delete the chunk file
                if chunk_path.exists():
                    os.remove(chunk_path)
                    
                # Remove from index
                del conv_index[chunk_id]
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Error deleting chunk {chunk_id}: {str(e)}")
                
        # Save the updated index if we deleted anything
        if deleted_count > 0:
            await self._save_index(conversation_id)
            
        logger.info(f"Deleted {deleted_count} chunks for document {document_id}")
        return deleted_count
        
    async def list_documents(
        self, conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all documents."""
        # Get the relevant index
        conv_index = self.index.get(conversation_id, {})
        
        # Get unique document IDs
        document_ids = set()
        for chunk_info in conv_index.values():
            doc_id = chunk_info.get("document_id")
            if doc_id:
                document_ids.add(doc_id)
                
        # Compile document information
        documents = []
        for doc_id in document_ids:
            doc_chunks = [
                chunk_id for chunk_id, info in conv_index.items()
                if info.get("document_id") == doc_id
            ]
            
            # Use metadata from the first chunk
            if doc_chunks:
                first_chunk_info = conv_index[doc_chunks[0]]
                metadata = first_chunk_info.get("metadata", {})
                
                documents.append({
                    "document_id": doc_id,
                    "chunk_count": len(doc_chunks),
                    "metadata": metadata,
                    "created_at": first_chunk_info.get("created_at"),
                })
                
        logger.info(f"Listed {len(documents)} documents for conversation {conversation_id}")
        return documents
