from typing import List, Dict, Any, Optional, Tuple
import re
import logging
import nltk
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Download necessary NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """
    A chunk of text from a document with associated metadata.
    """
    text: str
    metadata: Dict[str, Any]


class ChunkingStrategy(ABC):
    """
    Abstract base class for document chunking strategies.
    """
    
    @abstractmethod
    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks according to the strategy.
        """
        pass


class SimpleChunkingStrategy(ChunkingStrategy):
    """
    Simple chunking strategy that splits text by fixed chunk size with optional overlap.
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, separator: str = "\n"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
    
    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into fixed-size chunks with optional overlap.
        
        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Metadata to attach to each chunk
            
        Returns:
            List of dictionaries, each containing 'text' and 'metadata' keys
        """
        if not text:
            return []
            
        metadata = metadata or {}
        chunks = []
        
        # Split by separator if provided
        segments = text.split(self.separator) if self.separator else [text]
        segments = [seg for seg in segments if seg.strip()]
        
        # If no segments after splitting, just use the original text
        if not segments:
            segments = [text]
        
        # Initialize current chunk
        current_chunk = []
        current_size = 0
        
        for segment in segments:
            segment = segment.strip() + self.separator
            segment_size = len(segment)
            
            # If a single segment is larger than chunk_size, split it directly
            if segment_size > self.chunk_size:
                # First, add any existing chunk if it's not empty
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["total_chunks"] = 0  # Placeholder, will update later
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })
                    current_chunk = []
                    current_size = 0
                
                # Then split the large segment
                for i in range(0, len(segment), self.chunk_size - self.chunk_overlap):
                    chunk_text = segment[i:i + self.chunk_size]
                    if chunk_text:
                        chunk_metadata = metadata.copy()
                        chunk_metadata["chunk_index"] = len(chunks)
                        chunk_metadata["total_chunks"] = 0  # Placeholder
                        chunk_metadata["is_large_segment"] = True
                        chunk_metadata["segment_index"] = i // (self.chunk_size - self.chunk_overlap)
                        chunks.append({
                            "text": chunk_text,
                            "metadata": chunk_metadata
                        })
            
            # Normal case: add segment to current chunk if it fits
            elif current_size + segment_size <= self.chunk_size:
                current_chunk.append(segment)
                current_size += segment_size
            
            # If current segment doesn't fit, finalize current chunk and start a new one
            else:
                # Add current chunk to list if not empty
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["total_chunks"] = 0  # Placeholder
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })
                
                # Start a new chunk with overlap
                overlap_size = 0
                overlap_chunks = []
                
                # Add overlapping segments from the previous chunk
                for previous_segment in reversed(current_chunk):
                    if overlap_size + len(previous_segment) <= self.chunk_overlap:
                        overlap_chunks.insert(0, previous_segment)
                        overlap_size += len(previous_segment)
                    else:
                        break
                
                current_chunk = overlap_chunks + [segment]
                current_size = sum(len(seg) for seg in current_chunk)
            
        # Add the last chunk if not empty
        if current_chunk:
            chunk_text = "".join(current_chunk)
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadata["total_chunks"] = 0  # Placeholder
            chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })
        
        # Update total_chunks in metadata for all chunks
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)
        
        logger.info(f"Created {len(chunks)} chunks using simple chunking strategy")
        return chunks


class SemanticChunkingStrategy(ChunkingStrategy):
    """
    Advanced chunking strategy that respects semantic boundaries like paragraphs, 
    sentences, and headings.
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.heading_pattern = re.compile(r'^#+\s+.+$|^.+\n[=\-]{2,}$', re.MULTILINE)
        
    def is_heading(self, text: str) -> bool:
        """Check if a text segment is a heading."""
        # Check for Markdown style headings or underlined headings
        return bool(self.heading_pattern.match(text))
    
    def get_segment_importance(self, segment: str) -> int:
        """
        Assign importance scores to different types of segments.
        Higher scores mean the segment is more important to keep intact.
        """
        segment = segment.strip()
        
        # Headings are most important
        if self.is_heading(segment):
            return 100
            
        # Lists, code blocks, etc. are important
        if segment.startswith(('- ', '* ', '1. ', '```', '>', '|')):
            return 80
            
        # Longer paragraphs are generally important
        if len(segment) > 200:
            return 60
            
        # Shorter paragraphs
        if len(segment) > 100:
            return 40
            
        # Default importance
        return 20
    
    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text based on semantic boundaries like paragraphs, sentences, and headings.
        
        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Metadata to attach to each chunk
            
        Returns:
            List of dictionaries, each containing 'text' and 'metadata' keys
        """
        if not text:
            return []
            
        metadata = metadata or {}
        chunks = []
        
        # First split by paragraphs (double newlines)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        if not paragraphs:
            return []
        
        current_chunk = []
        current_size = 0
        current_segment_types = set()
        
        for para_idx, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            para_size = len(paragraph)
            
            # Determine segment type
            is_heading = self.is_heading(paragraph)
            segment_type = "heading" if is_heading else "paragraph"
            
            # If a heading is encountered, try to start a new chunk unless the current chunk is empty
            if is_heading and current_chunk and current_size > 0:
                # Add current chunk to list
                chunk_text = "\n\n".join(current_chunk)
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = len(chunks)
                chunk_metadata["total_chunks"] = 0  # Placeholder
                chunk_metadata["segment_types"] = list(current_segment_types)
                chunks.append({
                    "text": chunk_text,
                    "metadata": chunk_metadata
                })
                
                # Reset current chunk
                current_chunk = []
                current_size = 0
                current_segment_types = set()
            
            # If paragraph is very large, split it by sentences
            if para_size > self.chunk_size:
                if current_chunk:
                    # Add current chunk first
                    chunk_text = "\n\n".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["total_chunks"] = 0  # Placeholder
                    chunk_metadata["segment_types"] = list(current_segment_types)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })
                
                # Split large paragraph by sentences
                sentences = nltk.sent_tokenize(paragraph)
                current_chunk = []
                current_size = 0
                current_segment_types = set()
                chunk_para = ""
                
                for sentence in sentences:
                    if len(chunk_para) + len(sentence) + 1 <= self.chunk_size:
                        if chunk_para:
                            chunk_para += " " + sentence
                        else:
                            chunk_para = sentence
                    else:
                        # Add completed paragraph chunk
                        if chunk_para:
                            current_chunk.append(chunk_para)
                            current_segment_types.add("paragraph_split")
                            
                            # If adding this split paragraph would exceed chunk size, create a new chunk
                            if current_size + len(chunk_para) > self.chunk_size:
                                chunk_text = "\n\n".join(current_chunk[:-1])  # Exclude the last added paragraph
                                chunk_metadata = metadata.copy()
                                chunk_metadata["chunk_index"] = len(chunks)
                                chunk_metadata["total_chunks"] = 0  # Placeholder
                                chunk_metadata["segment_types"] = list(current_segment_types)
                                chunk_metadata["split_type"] = "sentence"
                                chunks.append({
                                    "text": chunk_text,
                                    "metadata": chunk_metadata
                                })
                                
                                # New chunk starts with the last paragraph
                                current_chunk = [current_chunk[-1]]
                                current_size = len(current_chunk[-1])
                                current_segment_types = {"paragraph_split"}
                            else:
                                current_size += len(chunk_para)
                        
                        # Start new paragraph with this sentence
                        chunk_para = sentence
                
                # Add any remaining partial paragraph
                if chunk_para:
                    current_chunk.append(chunk_para)
                    current_segment_types.add("paragraph_split")
                    current_size += len(chunk_para)
            
            # Normal case: add paragraph to current chunk if it fits
            elif current_size + (2 if current_chunk else 0) + para_size <= self.chunk_size:
                current_chunk.append(paragraph)
                current_segment_types.add(segment_type)
                current_size += (2 if len(current_chunk) > 1 else 0) + para_size  # Add 2 for "\n\n" if not first segment
            
            # If current paragraph doesn't fit, finalize current chunk and start a new one
            else:
                # Add current chunk to list
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["total_chunks"] = 0  # Placeholder
                    chunk_metadata["segment_types"] = list(current_segment_types)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })
                
                # Start a new chunk with this paragraph
                current_chunk = [paragraph]
                current_segment_types = {segment_type}
                current_size = para_size
        
        # Add the last chunk if not empty
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadata["total_chunks"] = 0  # Placeholder
            chunk_metadata["segment_types"] = list(current_segment_types)
            chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })
        
        # Update total_chunks in metadata for all chunks
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)
        
        logger.info(f"Created {len(chunks)} chunks using semantic chunking strategy")
        return chunks


class TextChunker:
    """
    Text chunking utility that creates chunks from documents 
    using the specified chunking strategy.
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, separator: str = "\n", use_semantic_chunking: bool = False):
        """
        Initialize the text chunker.
        
        Args:
            chunk_size: Maximum size of each chunk
            chunk_overlap: Overlap between consecutive chunks
            separator: String to split text by before chunking (e.g., newline)
            use_semantic_chunking: Whether to use semantic chunking strategy
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
        
        if use_semantic_chunking:
            self.strategy = SemanticChunkingStrategy(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        else:
            self.strategy = SimpleChunkingStrategy(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator=separator)
    
    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks using the selected strategy.
        
        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Metadata to attach to each chunk
            
        Returns:
            List of dictionaries, each containing 'text' and 'metadata' keys
        """
        return self.strategy.split_text(text, document_id, metadata)


def get_chunker(chunk_size: int = 512, chunk_overlap: int = 50, use_semantic_chunking: bool = False) -> TextChunker:
    """
    Get a TextChunker instance with the specified parameters.
    
    Args:
        chunk_size: Maximum size of each chunk
        chunk_overlap: Overlap between consecutive chunks
        use_semantic_chunking: Whether to use semantic chunking
        
    Returns:
        TextChunker instance
    """
    return TextChunker(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap,
        use_semantic_chunking=use_semantic_chunking
    )
