from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from typing import Optional, List, Dict, Any
import uuid
import os
import logging
from pathlib import Path
import asyncio
import json
import time
from datetime import datetime

from ..config import settings
from ..api.models import (
    DocumentResponse,
    DocumentStatusResponse,
    DocumentStatus,
    QueryRequest,
    QueryResponse,
    ChunkInfo,
    DocumentMetadata,
    ProcessingStage
)
from ..api.dependencies import get_storage, get_embedding_model_instance, get_text_chunker
from ..document.extractor import extract_document
from ..storage.base import Chunk, BaseStorage
from ..embedding.models import EmbeddingModel

# Setup logging
logger = logging.getLogger("ragapi")

# Create router
router = APIRouter(prefix="/rag", tags=["rag"])


# Helper function to ensure document storage directory exists
def ensure_document_dir(conversation_id: Optional[str] = None) -> Path:
    """Ensure document directory exists and return its path."""
    base_dir = Path(settings.documents_path)
    
    if conversation_id:
        doc_dir = base_dir / conversation_id
    else:
        doc_dir = base_dir
        
    os.makedirs(doc_dir, exist_ok=True)
    return doc_dir


# Helper function to ensure embeddings directory exists
def ensure_embeddings_dir(conversation_id: Optional[str] = None) -> Path:
    """Ensure embeddings directory exists and return its path."""
    base_dir = Path(settings.embeddings_path)
    
    if conversation_id:
        emb_dir = base_dir / conversation_id
    else:
        emb_dir = base_dir
        
    os.makedirs(emb_dir, exist_ok=True)
    return emb_dir


# Add a function to update the processing status of a document
async def update_document_status(
    document_id: str,
    conversation_id: Optional[str],
    status: DocumentStatus,
    stage: ProcessingStage,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None
):
    """Update the processing status of a document and store it in a tracking file."""
    try:
        # Ensure the embedding directory exists
        emb_dir = ensure_embeddings_dir(conversation_id)
        
        # Create the status file path
        status_file = emb_dir / f"{document_id}_status.json"
        
        # Prepare the status data
        status_data = {
            "document_id": document_id,
            "conversation_id": conversation_id,
            "status": status,
            "processing_stage": stage,
            "last_updated": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        if error:
            status_data["error"] = error
            
        # Write the status to file
        with open(status_file, "w") as f:
            json.dump(status_data, f, indent=2)
            
        logger.info(f"Updated status for document {document_id}: {status} ({stage})")
        
    except Exception as e:
        logger.error(f"Failed to update status for document {document_id}: {str(e)}")


# Background task to process a document
async def process_document(
    document_id: str, 
    file_path: str, 
    conversation_id: Optional[str] = None,
    storage: Optional[BaseStorage] = None,
    embedding_model: Optional[EmbeddingModel] = None
):
    """Process a document in the background."""
    start_time = time.time()
    
    # Initialize status tracking
    await update_document_status(
        document_id=document_id,
        conversation_id=conversation_id,
        status=DocumentStatus.PROCESSING,
        stage=ProcessingStage.INITIALIZATION,
        metadata={"file_path": str(file_path)}
    )
    
    if storage is None:
        from ..api.dependencies import get_storage
        storage = await get_storage()
        
    if embedding_model is None:
        from ..api.dependencies import get_embedding_model_instance
        embedding_model = await get_embedding_model_instance()
    
    from ..document.chunker import get_chunker
    chunker = get_chunker(
        chunk_size=settings.chunk_size, 
        chunk_overlap=settings.chunk_overlap,
        use_semantic_chunking=settings.use_semantic_chunking
    )
    
    logger.info(f"Processing document {document_id} in background")
    
    result = {
        "success": False,
        "document_id": document_id,
        "conversation_id": conversation_id,
        "chunk_count": 0,
        "error": None,
        "stage": ProcessingStage.INITIALIZATION
    }
    
    try:
        # 1. Extract text from the document
        result["stage"] = ProcessingStage.TEXT_EXTRACTION
        await update_document_status(
            document_id=document_id,
            conversation_id=conversation_id,
            status=DocumentStatus.PROCESSING,
            stage=ProcessingStage.TEXT_EXTRACTION
        )
        
        document_data = await extract_document(file_path)
        text = document_data["text"]
        metadata = document_data["metadata"]
        
        # 2. Chunk the text
        result["stage"] = ProcessingStage.CHUNKING
        await update_document_status(
            document_id=document_id,
            conversation_id=conversation_id,
            status=DocumentStatus.PROCESSING,
            stage=ProcessingStage.CHUNKING,
            metadata={"text_length": len(text), **metadata}
        )
        
        chunks_data = chunker.split_text(text, document_id=document_id, metadata=metadata)
        
        # 3. Create chunk objects and generate embeddings
        result["stage"] = ProcessingStage.EMBEDDING
        await update_document_status(
            document_id=document_id,
            conversation_id=conversation_id,
            status=DocumentStatus.PROCESSING,
            stage=ProcessingStage.EMBEDDING,
            metadata={"chunk_count": len(chunks_data)}
        )
        
        chunks = []
        
        # Process chunks in batches to avoid memory issues
        batch_size = settings.embedding_batch_size
        for i in range(0, len(chunks_data), batch_size):
            batch = chunks_data[i:i+batch_size]
            
            # Extract texts for batch embedding
            texts = [c["text"] for c in batch]
            
            # Generate embeddings for the batch
            embeddings = await embedding_model.get_embeddings(texts)
            
            # Create chunk objects
            for j, chunk_data in enumerate(batch):
                chunk = Chunk(
                    text=chunk_data["text"],
                    embedding=embeddings[j],
                    metadata=chunk_data["metadata"],
                    document_id=document_id,
                )
                chunks.append(chunk)
        
        # 4. Store the chunks
        result["stage"] = ProcessingStage.STORAGE
        await update_document_status(
            document_id=document_id,
            conversation_id=conversation_id,
            status=DocumentStatus.PROCESSING,
            stage=ProcessingStage.STORAGE,
            metadata={"chunk_count": len(chunks)}
        )
        
        chunk_ids = await storage.add_chunks(chunks, conversation_id)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Mark as complete
        result["success"] = True
        result["chunk_count"] = len(chunk_ids)
        result["processing_time"] = processing_time
        
        await update_document_status(
            document_id=document_id,
            conversation_id=conversation_id,
            status=DocumentStatus.INDEXED,
            stage=ProcessingStage.COMPLETE,
            metadata={
                "chunk_count": len(chunk_ids),
                "processing_time": processing_time,
                **metadata
            }
        )
        
        logger.info(f"Document {document_id} processed: {len(chunk_ids)} chunks created and stored in {processing_time:.2f}s")
        return result
        
    except Exception as e:
        error_message = str(e)
        # Calculate processing time
        processing_time = time.time() - start_time
        
        logger.error(f"Error processing document {document_id} at stage '{result['stage']}': {error_message}")
        result["error"] = {
            "message": error_message,
            "type": type(e).__name__
        }
        result["processing_time"] = processing_time
        
        await update_document_status(
            document_id=document_id,
            conversation_id=conversation_id,
            status=DocumentStatus.FAILED,
            stage=result["stage"],
            error=result["error"],
            metadata={"processing_time": processing_time}
        )
        
        return result


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    process_async: bool = Form(False),
    storage: BaseStorage = Depends(get_storage),
    embedding_model: EmbeddingModel = Depends(get_embedding_model_instance)
):
    """Upload and process a document for RAG."""
    document_id = str(uuid.uuid4())
    
    try:
        # Ensure directory exists
        doc_dir = ensure_document_dir(conversation_id)
        
        # Generate a unique filename with the document ID as prefix
        filename = f"{document_id}-{file.filename}"
        file_path = doc_dir / filename
        
        # Save the file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        file_size = len(content)
        logger.info(f"File uploaded: {file.filename} -> {file_path} ({file_size} bytes)")
        
        # Schedule processing
        if process_async:
            background_tasks.add_task(
                process_document, 
                document_id=document_id, 
                file_path=str(file_path),
                conversation_id=conversation_id,
                storage=storage,
                embedding_model=embedding_model
            )
            status = DocumentStatus.PENDING
            message = "Document uploaded and queued for processing"
        else:
            # Process immediately
            try:
                process_result = await process_document(
                    document_id=document_id,
                    file_path=str(file_path),
                    conversation_id=conversation_id,
                    storage=storage,
                    embedding_model=embedding_model
                )
                
                if process_result["success"]:
                    status = DocumentStatus.INDEXED
                    message = f"Document uploaded and processed successfully: {process_result['chunk_count']} chunks created"
                else:
                    status = DocumentStatus.FAILED
                    error_info = process_result["error"] or {"message": "Unknown error", "type": "Unknown"}
                    message = f"Document processing failed at stage '{process_result['stage']}': {error_info['message']}"
            except Exception as e:
                status = DocumentStatus.FAILED
                message = f"Document processing failed: {str(e)}"
            
        return DocumentResponse(
            document_id=document_id,
            conversation_id=conversation_id,
            filename=file.filename,
            status=status,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")


@router.get("/documents/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str, 
    conversation_id: Optional[str] = None,
    storage: BaseStorage = Depends(get_storage)
):
    """Get processing status of a document."""
    try:
        # First, check if there's a status file
        emb_dir = ensure_embeddings_dir(conversation_id)
        status_file = emb_dir / f"{document_id}_status.json"
        
        if status_file.exists():
            # Read the status file
            with open(status_file, "r") as f:
                status_data = json.load(f)
            
            # Extract status information
            doc_status = status_data.get("status", DocumentStatus.PENDING)
            processing_stage = status_data.get("processing_stage", ProcessingStage.INITIALIZATION)
            last_updated = status_data.get("last_updated")
            error = status_data.get("error")
            meta = status_data.get("metadata", {})
            
            # Create metadata object
            metadata = DocumentMetadata(
                filename=meta.get("filename", "unknown"),
                file_size=meta.get("file_size", 0),
                mime_type=meta.get("mime_type"),
                page_count=meta.get("page_count"),
                chunk_count=meta.get("chunk_count", 0),
                created_at=datetime.fromisoformat(meta.get("created_at", datetime.now().isoformat())),
                status=DocumentStatus(doc_status),
                processing_stage=ProcessingStage(processing_stage) if processing_stage else None,
                last_updated=datetime.fromisoformat(last_updated) if last_updated else None,
                error=error,
                processing_time=meta.get("processing_time")
            )
            
            return DocumentStatusResponse(
                document_id=document_id,
                conversation_id=conversation_id,
                status=DocumentStatus(doc_status),
                metadata=metadata
            )
        
        # Fall back to checking storage
        documents = await storage.list_documents(conversation_id)
        
        # Find the document with matching ID
        for doc in documents:
            if doc["document_id"] == document_id:
                # Convert the document info to our response model
                metadata = DocumentMetadata(
                    filename=doc["metadata"].get("filename", "unknown"),
                    file_size=doc["metadata"].get("file_size", 0),
                    mime_type=doc["metadata"].get("mime_type"),
                    page_count=doc["metadata"].get("page_count"),
                    chunk_count=doc.get("chunk_count", 0),
                    created_at=doc.get("created_at"),
                    status=DocumentStatus.INDEXED,
                    processing_stage=ProcessingStage.COMPLETE
                )
                
                return DocumentStatusResponse(
                    document_id=document_id,
                    conversation_id=conversation_id,
                    status=DocumentStatus.INDEXED,
                    metadata=metadata
                )
                
        # If document not found
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
    except Exception as e:
        logger.error(f"Error getting document status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting document status: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str, 
    conversation_id: Optional[str] = None,
    storage: BaseStorage = Depends(get_storage)
):
    """Delete a document and its embeddings."""
    try:
        # First, delete any source files
        doc_dir = ensure_document_dir(conversation_id)
        source_deleted = False
        
        # Look for any file with the document_id prefix
        for file_path in doc_dir.glob(f"{document_id}-*"):
            file_path.unlink()
            logger.info(f"Deleted source file {file_path}")
            source_deleted = True
            
        # Then, delete all chunks and embeddings
        deleted_count = await storage.delete_document(document_id, conversation_id)
        
        if deleted_count == 0 and not source_deleted:
            logger.warning(f"No files or chunks found for document ID {document_id}")
            return {"message": f"No files or chunks found for document ID {document_id}"}
            
        return {"message": f"Document {document_id} and its embeddings deleted successfully ({deleted_count} chunks)"}
        
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    query_request: QueryRequest,
    storage: BaseStorage = Depends(get_storage),
    embedding_model: EmbeddingModel = Depends(get_embedding_model_instance)
):
    """Query the document store and return relevant chunks."""
    try:
        # Generate embedding for the query
        query_embeddings = await embedding_model.get_embeddings([query_request.query])
        query_embedding = query_embeddings[0]
        
        # Set defaults
        top_k = query_request.top_k or settings.default_top_k
        
        # Search for similar chunks
        chunks = await storage.search_chunks(
            query_embedding=query_embedding,
            top_k=top_k,
            conversation_id=query_request.conversation_id,
            filters=query_request.filters
        )
        
        # Convert to response model
        chunk_infos = []
        for chunk in chunks:
            score = chunk.metadata.get("score", 0.0) if chunk.metadata else 0.0
            
            chunk_infos.append(ChunkInfo(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                text=chunk.text,
                metadata=chunk.metadata,
                score=score
            ))
            
        return QueryResponse(
            query=query_request.query,
            chunks=chunk_infos,
            total_chunks_found=len(chunk_infos)
        )
        
    except Exception as e:
        logger.error(f"Error querying documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying documents: {str(e)}")
