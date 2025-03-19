#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("test_document_query")

# API URLs
RUNTIME_API_URL = "http://localhost:5003"
RAG_API_URL = "http://localhost:5005"

async def query_rag_api(query_text):
    """Query the RAG API directly."""
    try:
        logger.info(f"Querying RAG API with: '{query_text}'")
        
        # Create the query payload
        payload = {
            "query": query_text,
            "top_k": 3
        }
        
        # Send the query to the RAG API
        async with aiohttp.ClientSession() as session:
            url = f"{RAG_API_URL}/rag/query"
            logger.info(f"Sending POST request to: {url}")
            
            async with session.post(url, json=payload) as response:
                status = response.status
                logger.info(f"Response status: {status}")
                
                text = await response.text()
                logger.info(f"Response text: {text[:500]}...")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        chunks = data.get("chunks", [])
                        logger.info(f"Found {len(chunks)} chunks")
                        
                        # Print each chunk
                        for i, chunk in enumerate(chunks):
                            logger.info(f"Chunk {i+1}:")
                            logger.info(f"  Text: {chunk.get('text', '')[:100]}...")
                            logger.info(f"  Score: {chunk.get('score', 0)}")
                            logger.info(f"  Document ID: {chunk.get('document_id', '')}")
                        
                        return chunks
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response as JSON: {e}")
                        return []
                else:
                    logger.error(f"Query failed with status: {status}")
                    return []
    except Exception as e:
        logger.error(f"Error querying RAG API: {e}", exc_info=True)
        return []

async def query_runtime_api(query_text):
    """Query the Runtime API."""
    try:
        logger.info(f"Querying Runtime API with: '{query_text}'")
        
        # Create the query payload
        payload = {
            "query": query_text,
            "verbose": True,
            "stream": False  # Explicitly disable streaming for this test
        }
        
        # Send the query to the Runtime API
        async with aiohttp.ClientSession() as session:
            url = f"{RUNTIME_API_URL}/api/query"
            logger.info(f"Sending POST request to: {url}")
            
            async with session.post(url, json=payload) as response:
                status = response.status
                logger.info(f"Response status: {status}")
                
                text = await response.text()
                logger.info(f"Response text: {text[:500]}...")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        content = data.get("content", "")
                        agents_used = data.get("agents_used", [])
                        
                        logger.info(f"Response content: {content}")
                        logger.info(f"Agents used: {agents_used}")
                        
                        return data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response as JSON: {e}")
                        return {}
                else:
                    logger.error(f"Query failed with status: {status}")
                    return {}
    except Exception as e:
        logger.error(f"Error querying Runtime API: {e}", exc_info=True)
        return {}

async def main():
    """Run the tests."""
    logger.info("Starting document query tests...")
    
    # Test querying the RAG API directly for Onward Platforms
    query = "What is Onward Platforms?"
    chunks = await query_rag_api(query)
    
    # Test querying the RAG API directly for NDA information
    query = "Who is the NDA for?"
    chunks = await query_rag_api(query)
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 