#!/usr/bin/env python
"""
Test script to test the RAG API document chunking and see any errors
"""

import os
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_test")

# Add the ragapi package to the path if needed
ragapi_path = Path(".").resolve()
if str(ragapi_path) not in sys.path:
    sys.path.append(str(ragapi_path))

from ragapi.document.extractor import extract_document
from ragapi.document.chunker import get_chunker
from ragapi.config import settings

async def test_rag_chunking():
    """Test the document extraction and chunking to see if there are any errors."""
    # Path to the file we want to test - using absolute path to avoid any directory issues
    workspace_root = Path(__file__).resolve().parent
    file_path = workspace_root / ".data/documents/d8aa8702-24e2-475d-a0c0-8068cd70a319/5028aecf-c79c-47db-a441-8e7322ba7275-Common%20Checkout%20Payment%20Receipt.pdf"
    
    # Create chunker
    chunker = get_chunker(
        chunk_size=settings.chunk_size, 
        chunk_overlap=settings.chunk_overlap,
        use_semantic_chunking=settings.use_semantic_chunking
    )
    
    try:
        # 1. Extract text from the document
        print(f"Extracting text from {file_path}")
        document_data = await extract_document(str(file_path))
        text = document_data["text"]
        metadata = document_data["metadata"]
        
        print(f"Successfully extracted text from document")
        print(f"Metadata: {metadata}")
        print(f"Text length: {len(text)} characters")
        print(f"Text preview: {text[:200]}...")
        
        # 2. Chunk the text
        print(f"\nChunking text with settings: chunk_size={settings.chunk_size}, chunk_overlap={settings.chunk_overlap}, use_semantic_chunking={settings.use_semantic_chunking}")
        chunks = chunker.split_text(text, document_id="test", metadata=metadata)
        
        print(f"Successfully chunked text into {len(chunks)} chunks")
        
        # 3. Print chunk information
        for i, chunk in enumerate(chunks[:3]):  # Print the first 3 chunks
            print(f"\nChunk {i+1}/{len(chunks)}:")
            print(f"  Size: {len(chunk.text)} characters")
            print(f"  Metadata: {chunk.metadata}")
            print(f"  Text preview: {chunk.text[:100]}...")
        
        if len(chunks) > 3:
            print(f"\n... and {len(chunks) - 3} more chunks")
        
        print("\nRAG Text extraction and chunking completed successfully")
        
    except Exception as e:
        print(f"Error during chunking test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_rag_chunking()) 