from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger("ragapi.chunker")


class TextChunker:
    """Splits text into chunks with optional overlap."""
    
    def __init__(
        self, 
        chunk_size: int = 512, 
        chunk_overlap: int = 50,
        separator: str = "\n"
    ):
        """
        Initialize the text chunker.
        
        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            separator: Character(s) to use for splitting text
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
    
    def split_text(
        self, 
        text: str, 
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks.
        
        Args:
            text: The text to split
            document_id: Optional document ID to include in chunk metadata
            metadata: Additional metadata to include with each chunk
            
        Returns:
            List of dictionaries containing chunk text and metadata
        """
        if not text:
            logger.warning("Empty text provided to chunker")
            return []
            
        metadata = metadata or {}
        chunks = []
        
        # Split text by separator
        segments = text.split(self.separator)
        
        current_chunk = []
        current_size = 0
        
        for segment in segments:
            # Skip empty segments
            if not segment.strip():
                continue
                
            segment_size = len(segment)
            
            # If adding this segment would exceed the chunk size and we already have content,
            # store the current chunk and start a new one
            if current_size + segment_size > self.chunk_size and current_chunk:
                chunk_text = self.separator.join(current_chunk)
                chunk_data = {
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "document_id": document_id,
                        "chunk_size": len(chunk_text),
                        "chunk_index": len(chunks)
                    }
                }
                chunks.append(chunk_data)
                
                # Start new chunk with overlap
                overlap_size = 0
                new_chunk = []
                
                # Add segments from the end of the previous chunk for overlap
                for overlap_segment in reversed(current_chunk):
                    overlap_size += len(overlap_segment)
                    new_chunk.insert(0, overlap_segment)
                    
                    if overlap_size >= self.chunk_overlap:
                        break
                        
                current_chunk = new_chunk
                current_size = sum(len(seg) for seg in current_chunk)
                
            # If the segment itself is larger than chunk_size, we need to split it
            if segment_size > self.chunk_size:
                # If we have anything in the current chunk, store it first
                if current_chunk:
                    chunk_text = self.separator.join(current_chunk)
                    chunk_data = {
                        "text": chunk_text,
                        "metadata": {
                            **metadata,
                            "document_id": document_id,
                            "chunk_size": len(chunk_text),
                            "chunk_index": len(chunks)
                        }
                    }
                    chunks.append(chunk_data)
                    current_chunk = []
                    current_size = 0
                
                # Split the large segment into smaller pieces
                for i in range(0, segment_size, self.chunk_size - self.chunk_overlap):
                    chunk_text = segment[i:i + self.chunk_size]
                    if len(chunk_text) < self.chunk_size / 4:  # Skip very small leftover chunks
                        continue
                        
                    chunk_data = {
                        "text": chunk_text,
                        "metadata": {
                            **metadata,
                            "document_id": document_id,
                            "chunk_size": len(chunk_text),
                            "chunk_index": len(chunks)
                        }
                    }
                    chunks.append(chunk_data)
            else:
                # Add segment to current chunk
                current_chunk.append(segment)
                current_size += segment_size
        
        # Add any remaining text as the final chunk
        if current_chunk:
            chunk_text = self.separator.join(current_chunk)
            chunk_data = {
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "document_id": document_id,
                    "chunk_size": len(chunk_text),
                    "chunk_index": len(chunks)
                }
            }
            chunks.append(chunk_data)
            
        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks
        

def get_chunker(chunk_size: int = 512, chunk_overlap: int = 50) -> TextChunker:
    """
    Get a text chunker with the specified parameters.
    
    Args:
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        
    Returns:
        A TextChunker instance
    """
    return TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
