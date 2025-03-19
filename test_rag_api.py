#!/usr/bin/env python3
"""
Test script to directly query the RAG API.
This helps isolate whether the issue is with the API itself or how we're calling it.
"""

import asyncio
import json
import sys
import aiohttp

# RAG API URL
RAG_API_URL = "http://localhost:5005"

async def test_rag_api_documents(conversation_id=None):
    """Test the /rag/documents endpoint to list available documents."""
    print(f"Testing RAG API documents endpoint with conversation_id: {conversation_id}")
    
    try:
        url = f"{RAG_API_URL}/rag/documents"
        if conversation_id:
            url += f"?conversation_id={conversation_id}"
            
        print(f"Sending GET request to: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"Response status: {response.status}")
                
                response_text = await response.text()
                print(f"Response text: {response_text[:500]}...")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        document_count = len(data.get('documents', []))
                        print(f"Found {document_count} documents.")
                        
                        # Print each document
                        for i, doc in enumerate(data.get('documents', [])):
                            print(f"Document {i+1}: {doc.get('document_id')} - {doc.get('filename')}")
                    except json.JSONDecodeError:
                        print("Failed to parse response as JSON")
                
    except Exception as e:
        print(f"Error testing documents endpoint: {e}")

async def test_rag_api_query(query, conversation_id=None, top_k=3):
    """Test the /rag/query endpoint to search documents."""
    print(f"Testing RAG API query endpoint with: '{query}', conversation_id: {conversation_id}, top_k: {top_k}")
    
    try:
        url = f"{RAG_API_URL}/rag/query"
        
        # Create payload
        payload = {
            "query": query,
            "top_k": top_k
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
            
        print(f"Sending POST request to: {url}")
        print(f"Payload: {payload}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                print(f"Response status: {response.status}")
                
                response_text = await response.text()
                print(f"Response text: {response_text[:500]}...")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        chunk_count = len(data.get('chunks', []))
                        print(f"Found {chunk_count} chunks for query '{query}'.")
                        
                        # Print each chunk
                        for i, chunk in enumerate(data.get('chunks', [])):
                            print(f"Chunk {i+1}: score={chunk.get('score', 0):.3f}")
                            print(f"Text: {chunk.get('text', '')[:100]}...")
                            print("---")
                    except json.JSONDecodeError:
                        print("Failed to parse response as JSON")
                
    except Exception as e:
        print(f"Error testing query endpoint: {e}")

async def main():
    # Use commandline args if provided
    conversation_id = sys.argv[1] if len(sys.argv) > 1 else None
    query = sys.argv[2] if len(sys.argv) > 2 else "parties involved in the NDA"
    
    print("=== RAG API Test ===")
    
    # Test documents endpoint
    print("\n1. Testing documents endpoint:")
    await test_rag_api_documents(conversation_id)
    
    # Test query endpoint
    print("\n2. Testing query endpoint:")
    await test_rag_api_query(query, conversation_id)
    
    # Test with a more general query that should work
    print("\n3. Testing with a more general query 'confidentiality':")
    await test_rag_api_query("confidentiality", conversation_id)
    
    # Test with the "company" query specifically
    print("\n4. Testing with the company query:")
    await test_rag_api_query("company name in NDA", conversation_id)
    
    # Test some more specific queries about company names and parties
    print("\n5. Testing with various company/party queries:")
    company_queries = [
        "company mentioned in the NDA",
        "what company is this NDA for",
        "parties to the agreement",
        "who are the parties in this NDA",
        "Onward Platforms"
    ]
    
    for q in company_queries:
        print(f"\nQuery: '{q}'")
        await test_rag_api_query(q, conversation_id)

if __name__ == "__main__":
    asyncio.run(main()) 