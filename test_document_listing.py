#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("test_document_listing")

# API URLs
RUNTIME_API_URL = "http://localhost:5003"
RAG_API_URL = "http://localhost:5005"

async def test_direct_rag_documents():
    """Test the RAG API documents endpoint directly."""
    try:
        logger.info("Testing direct RAG API documents endpoint...")
        async with aiohttp.ClientSession() as session:
            url = f"{RAG_API_URL}/rag/documents"
            logger.info(f"Sending GET request to: {url}")
            
            async with session.get(url) as response:
                status = response.status
                logger.info(f"Response status: {status}")
                
                text = await response.text()
                logger.info(f"Response text: {text[:500]}")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        documents = data.get("documents", [])
                        logger.info(f"Found {len(documents)} documents")
                        
                        # Print each document
                        for i, doc in enumerate(documents):
                            logger.info(f"Document {i+1}: {doc}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response as JSON: {e}")
                else:
                    logger.error(f"Request failed with status: {status}")
    except Exception as e:
        logger.error(f"Error testing direct RAG documents: {e}", exc_info=True)

async def test_runtime_rag_documents():
    """Test the Runtime API documents endpoint."""
    try:
        logger.info("Testing Runtime API documents endpoint...")
        async with aiohttp.ClientSession() as session:
            url = f"{RUNTIME_API_URL}/api/rag/documents"
            logger.info(f"Sending GET request to: {url}")
            
            async with session.get(url) as response:
                status = response.status
                logger.info(f"Response status: {status}")
                
                text = await response.text()
                logger.info(f"Response text: {text[:500]}")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        documents = data.get("documents", [])
                        logger.info(f"Found {len(documents)} documents")
                        
                        # Print each document
                        for i, doc in enumerate(documents):
                            logger.info(f"Document {i+1}: {doc}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response as JSON: {e}")
                else:
                    logger.error(f"Request failed with status: {status}")
    except Exception as e:
        logger.error(f"Error testing runtime RAG documents: {e}", exc_info=True)

async def main():
    """Run the tests."""
    logger.info("Starting document listing tests...")
    
    # Test direct RAG API
    await test_direct_rag_documents()
    
    # Test Runtime API
    await test_runtime_rag_documents()
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 