#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys

async def direct_rag_query(query, conversation_id, top_k=5):
    """Send a direct query to the RAG API."""
    print(f"Sending direct query to RAG API: '{query}' for conversation: {conversation_id}")
    
    try:
        # Prepare the request payload
        payload = {
            "query": query,
            "top_k": top_k,
            "conversation_id": conversation_id
        }
        
        # Call the RAG API directly
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:5005/rag/query",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error: {response.status} - {error_text}")
                    return None
                
                data = await response.json()
                return data
    except Exception as e:
        print(f"Exception: {e}")
        return None

async def list_documents(conversation_id=None):
    """List documents in the RAG API."""
    try:
        url = "http://localhost:5005/rag/documents"
        if conversation_id:
            url += f"?conversation_id={conversation_id}"
            
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error listing documents: {response.status} - {error_text}")
                    return None
                
                data = await response.json()
                return data
    except Exception as e:
        print(f"Exception listing documents: {e}")
        return None

async def main():
    """Run the test."""
    # Use the specific conversation ID
    conversation_id = "1d4ea981-887d-4114-bd89-9469fb89061b"
    
    # First, list the documents in this conversation
    print(f"\nListing documents for conversation: {conversation_id}")
    documents = await list_documents(conversation_id)
    
    if documents:
        print(f"Found {len(documents.get('documents', []))} documents:")
        for doc in documents.get("documents", []):
            print(f"  - {doc.get('filename', 'Unknown')} (ID: {doc.get('id', 'Unknown')})")
    else:
        print("No documents found or error listing documents")
    
    # Test queries
    queries = [
        "onward platforms",
        "rodney pressley",
        "agreement",
        "nda"
    ]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"Testing query: '{query}'")
        
        result = await direct_rag_query(query, conversation_id)
        
        if result:
            chunks = result.get("chunks", [])
            total_chunks = result.get("total_chunks_found", 0)
            
            print(f"Found {len(chunks)} chunks out of {total_chunks} total chunks")
            
            for i, chunk in enumerate(chunks, 1):
                text = chunk.get("text", "").strip()
                score = chunk.get("score", 0)
                doc_id = chunk.get("document_id", "unknown")
                metadata = chunk.get("metadata", {})
                
                # Get document name from metadata if available
                doc_name = metadata.get("filename", "Document " + doc_id[:8])
                
                print(f"\n[Result {i}] From {doc_name} (Relevance: {score:.2f})")
                print(f"{text[:200]}..." if len(text) > 200 else text)
        else:
            print("No results or error")

if __name__ == "__main__":
    asyncio.run(main()) 