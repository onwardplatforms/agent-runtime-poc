import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ...config import settings
from ..base import BaseStorage, Chunk

logger = logging.getLogger("ragapi.storage.filesystem")


class FilesystemStorage(BaseStorage):
    """Storage backend using the filesystem to store embeddings and metadata."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the filesystem storage.

        Args:
            base_dir: Base directory for embeddings. If None, uses the configured embeddings_path.
        """
        self.base_dir = Path(base_dir or settings.embeddings_path).resolve()
        self.indexes: Dict[str, Dict[str, Any]] = {}  # In-memory index for quick access

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the storage by creating the base directory and loading existing indexes."""
        try:
            # Create the base directory if it doesn't exist
            os.makedirs(self.base_dir, exist_ok=True)

            # Load existing indexes
            await self._load_indexes()

            return {"status": "initialized", "base_dir": str(self.base_dir)}
        except Exception as e:
            logger.error(f"Error initializing filesystem storage: {str(e)}")
            raise

    async def _load_indexes(self) -> None:
        """Load existing conversation indexes from the filesystem."""
        for item in os.listdir(self.base_dir):
            try:
                index_path = self.base_dir / item / "index.json"
                if index_path.exists():
                    with open(index_path, "r") as f:
                        conversation_id = None if item == "default" else item
                        self.indexes[conversation_id or "default"] = json.load(f)
                        logger.info(f"Loaded index for conversation {conversation_id or 'default'}")
            except Exception as e:
                logger.error(f"Error loading index for {item}: {str(e)}")

    async def _save_index(self, conversation_id: Optional[str] = None) -> None:
        """Save an index to the filesystem."""
        # Use "default" as the key when conversation_id is None
        conv_key = conversation_id or "default"

        # Get the index for this conversation
        conv_index = self.indexes.get(conv_key, {})

        # Create the conversation directory if it doesn't exist
        conv_dir = self.base_dir / conv_key
        os.makedirs(conv_dir, exist_ok=True)

        # Save the index file
        index_path = conv_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(conv_index, f, indent=2)

        logger.debug(f"Saved index for conversation {conv_key} with {len(conv_index)} entries")

    def _get_chunk_path(self, chunk_id: str, conversation_id: Optional[str] = None) -> Path:
        """Get the path to a chunk file."""
        # Use "default" as the directory when conversation_id is None
        conv_key = conversation_id or "default"
        return self.base_dir / conv_key / f"{chunk_id}.pkl"

    async def add_chunks(
        self, chunks: List[Chunk], conversation_id: Optional[str] = None
    ) -> List[str]:
        """Add chunks to the storage."""
        # Use "default" as the key when conversation_id is None
        conv_key = conversation_id or "default"

        # Make sure the index for this conversation exists
        if conv_key not in self.indexes:
            self.indexes[conv_key] = {}

        # Make sure the directory for this conversation exists
        conv_dir = self.base_dir / conv_key
        os.makedirs(conv_dir, exist_ok=True)

        if not chunks:
            return []

        # Initialize if needed
        if not os.path.exists(self.base_dir):
            await self.initialize()

        # Save each chunk
        chunk_ids = []
        for chunk in chunks:
            # Save the chunk to a pickle file
            chunk_path = self._get_chunk_path(chunk.chunk_id, conversation_id)

            try:
                with open(chunk_path, "wb") as f:
                    pickle.dump(chunk, f)

                # Update the index
                self.indexes[conv_key][chunk.chunk_id] = {
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
        """Get a chunk from the storage."""
        # Use "default" as the key when conversation_id is None
        conv_key = conversation_id or "default"

        # Check if the chunk exists in the index
        if conv_key not in self.indexes or chunk_id not in self.indexes[conv_key]:
            logger.warning(f"Chunk {chunk_id} not found in conversation {conv_key}")
            return None

        # Get the chunk path
        chunk_path = self._get_chunk_path(chunk_id, conversation_id)
        if not chunk_path.exists():
            logger.warning(f"Chunk file {chunk_path} not found")
            return None

        # Load the chunk
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
        """Search for chunks by embedding similarity."""
        # Use "default" as the key when conversation_id is None
        conv_key = conversation_id or "default"

        # Check if we have an index for this conversation
        if conv_key not in self.indexes or not self.indexes[conv_key]:
            logger.warning(f"No index for conversation {conv_key}")
            return []

        # Initialize results
        results = []

        # Get the relevant index
        conv_index = self.indexes[conv_key]

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
        """Delete a document and all its chunks."""
        # Use "default" as the key when conversation_id is None
        conv_key = conversation_id or "default"

        # Check if we have an index for this conversation
        if conv_key not in self.indexes:
            logger.warning(f"No index for conversation {conv_key}")
            return 0

        # Find all chunks for this document
        chunk_ids_to_delete = []
        for chunk_id, chunk_info in list(self.indexes[conv_key].items()):
            if chunk_info.get('document_id') == document_id:
                chunk_ids_to_delete.append(chunk_id)

        # Delete the chunks
        deleted_count = 0
        for chunk_id in chunk_ids_to_delete:
            # Remove from index
            self.indexes[conv_key].pop(chunk_id, None)

            # Delete the file
            chunk_path = self._get_chunk_path(chunk_id, conversation_id)
            if chunk_path.exists():
                try:
                    os.remove(chunk_path)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting chunk file {chunk_path}: {str(e)}")

        # Save the updated index
        await self._save_index(conversation_id)

        logger.info(f"Deleted document {document_id} with {deleted_count} chunks")
        return deleted_count

    async def list_documents(
        self, conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all documents in the storage."""
        # Use "default" as the key when conversation_id is None
        conv_key = conversation_id or "default"

        # Check if we have an index for this conversation
        if conv_key not in self.indexes:
            logger.warning(f"No index for conversation {conv_key}")
            return []

        # Collect unique document IDs and their metadata
        documents = {}
        for chunk_info in self.indexes[conv_key].values():
            doc_id = chunk_info.get("document_id")
            if not doc_id:
                continue

            if doc_id not in documents:
                # Extract metadata from the chunk
                metadata = chunk_info.get("metadata", {})
                documents[doc_id] = {
                    "document_id": doc_id,
                    "filename": metadata.get("filename", "unknown"),
                    "file_size": metadata.get("file_size", 0),
                    "mime_type": metadata.get("mime_type", "application/octet-stream"),
                    "chunk_count": 0,
                    "created_at": metadata.get("created_at", datetime.now().isoformat()),
                }

            # Increment chunk count
            documents[doc_id]["chunk_count"] += 1

        return list(documents.values())

    async def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the storage."""
        # Count documents and chunks across all conversations
        total_documents = 0
        total_chunks = 0
        total_size = 0

        # Get list of all conversation directories (subdirectories of base_dir)
        conversations = [d for d in self.base_dir.glob("*") if d.is_dir()]
        conversations.append(self.base_dir)  # Include the base dir for documents without conversation_id

        for conv_dir in conversations:
            # Count chunks in this conversation
            conversation_id = conv_dir.name if conv_dir != self.base_dir else None
            if conversation_id in self.indexes:
                total_chunks += len(self.indexes[conversation_id])

            # Calculate storage size
            for path in conv_dir.glob("**/*"):
                if path.is_file():
                    total_size += path.stat().st_size

            # Count unique document IDs
            document_ids = set()
            if conversation_id in self.indexes:
                for chunk_data in self.indexes[conversation_id].values():
                    if "document_id" in chunk_data:
                        document_ids.add(chunk_data["document_id"])
            total_documents += len(document_ids)

        return {
            "backend_type": "filesystem",
            "document_count": total_documents,
            "chunk_count": total_chunks,
            "size": total_size,
            "location": str(self.base_dir),
            "conversations": len(conversations) - 1  # Exclude the base dir
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the storage."""
        try:
            # Check if base directory exists and is writable
            if not self.base_dir.exists():
                return {
                    "status": "unhealthy",
                    "message": f"Base directory {self.base_dir} does not exist",
                    "details": {"error": "missing_directory"}
                }

            # Try to write a test file
            test_file = self.base_dir / ".health_check"
            try:
                with open(test_file, "w") as f:
                    f.write("health check")
                test_file.unlink()  # Remove the test file
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "message": f"Cannot write to base directory: {str(e)}",
                    "details": {"error": "write_permission", "exception": str(e)}
                }

            # Check if indexes are loaded
            if not self.indexes:
                return {
                    "status": "warning",
                    "message": "No indexes loaded",
                    "details": {"warning": "no_indexes"}
                }

            # Get basic storage info
            storage_info = await self.get_storage_info()

            return {
                "status": "healthy",
                "message": "Filesystem storage is operational",
                "details": storage_info
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "details": {"error": "health_check_exception", "exception": str(e)}
            }
