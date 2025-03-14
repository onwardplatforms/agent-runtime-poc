from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TextSegment(BaseModel):
    """
    Represents a segment of text with its type and metadata.
    Used for semantic chunking analysis.
    """
    text: str
    segment_type: str = "paragraph"  # paragraph, heading, list, etc.
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def __len__(self) -> int:
        """Return the length of the text segment."""
        return len(self.text)


class DocumentChunk(BaseModel):
    """
    Represents a chunk of a document with its text and metadata.
    """
    text: str
    document_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def __len__(self) -> int:
        """Return the length of the chunk text."""
        return len(self.text)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the chunk to a dictionary."""
        return {
            "text": self.text,
            "document_id": self.document_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        """Create a DocumentChunk from a dictionary."""
        return cls(
            text=data["text"],
            document_id=data["document_id"],
            metadata=data.get("metadata", {})
        ) 