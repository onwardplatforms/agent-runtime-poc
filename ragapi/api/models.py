from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class DocumentStatus(str, Enum):
    """Status of a document in the processing pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """Metadata about a processed document."""
    filename: str
    file_size: int
    mime_type: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: DocumentStatus = DocumentStatus.PENDING
    error: Optional[str] = None
    
    model_config = ConfigDict(
        extra="allow"  # Allow extra fields in metadata
    )


class DocumentResponse(BaseModel):
    """Response after uploading a document."""
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: Optional[str] = None
    filename: str
    status: DocumentStatus
    message: str


class DocumentStatusResponse(BaseModel):
    """Response for document status check."""
    document_id: str
    conversation_id: Optional[str] = None
    status: DocumentStatus
    metadata: DocumentMetadata
    

class ChunkInfo(BaseModel):
    """Information about a text chunk."""
    chunk_id: str
    document_id: str
    text: str
    metadata: Dict[str, Any]
    score: Optional[float] = None


class QueryRequest(BaseModel):
    """Request for querying the document store."""
    query: str
    conversation_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    top_k: int = 5


class QueryResponse(BaseModel):
    """Response for a document query."""
    query: str
    chunks: List[ChunkInfo]
    total_chunks_found: int
