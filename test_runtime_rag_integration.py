#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import logging
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("test_runtime_rag_integration")

# API URLs
RUNTIME_API_URL = "http://localhost:5003"

async def query_runtime_api(query_text):
    """Query the Runtime API with a question that should trigger RAG."""
    try:
        logger.info(f"Querying Runtime API with: '{query_text}'")
        
        # Create the query payload
        payload = {
            "query": query_text,
            "verbose": True,
            "stream": True  # We'll handle streaming responses
        }
        
        # Send the query to the Runtime API
        async with aiohttp.ClientSession() as session:
            url = f"{RUNTIME_API_URL}/api/query"
            logger.info(f"Sending POST request to: {url}")
            
            async with session.post(url, json=payload) as response:
                status = response.status
                logger.info(f"Response status: {status}")
                
                if status == 200:
                    # Handle streaming response
                    full_content = ""
                    agents_used = []
                    
                    # Read the response as a stream
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line or not line.startswith('data: '):
                            continue
                            
                        # Extract the JSON data
                        try:
                            data_str = line[6:]  # Remove 'data: ' prefix
                            data = json.loads(data_str)
                            
                            # Check for content chunks
                            if "content" in data and data["content"]:
                                full_content += data["content"]
                            
                            # Check for agent usage
                            if "agent_call" in data:
                                agent_id = data["agent_call"]
                                if agent_id not in agents_used:
                                    agents_used.append(agent_id)
                                    logger.info(f"Agent called: {agent_id}")
                            
                            # Check for completion
                            if data.get("complete", False):
                                if "agents_used" in data and data["agents_used"]:
                                    agents_used = data["agents_used"]
                                break
                                
                        except json.JSONDecodeError:
                            logger.debug(f"Failed to parse line as JSON: {line}")
                    
                    logger.info(f"Full response content: {full_content[:500]}...")
                    logger.info(f"Agents used: {agents_used}")
                    
                    # Check if the RAG plugin was used
                    if "rag" in agents_used:
                        logger.info("RAG plugin was used to answer the query!")
                    else:
                        logger.info("RAG plugin was NOT used to answer the query.")
                    
                    return {
                        "content": full_content,
                        "agents_used": agents_used
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Query failed with status: {status} - {error_text}")
                    return {}
    except Exception as e:
        logger.error(f"Error querying Runtime API: {e}", exc_info=True)
        return {}

async def main():
    """Run the tests."""
    logger.info("Starting runtime RAG integration test...")
    
    # Test queries that should trigger RAG
    rag_queries = [
        "What company is mentioned in the NDA?",
        "Tell me about Onward Platforms",
        "How long is the term of the NDA agreement?",
        "Who are the parties in the confidentiality agreement?"
    ]
    
    for query in rag_queries:
        logger.info(f"\n--- Testing query: '{query}' ---")
        result = await query_runtime_api(query)
        
        # Check if we got a valid response
        if result and "content" in result:
            # Check if the response mentions any document content
            content = result.get("content", "")
            if "Onward Platforms" in content or "NDA" in content or "agreement" in content:
                logger.info("Response contains document information!")
            else:
                logger.info("Response does not contain document information.")
        
        # Add a small delay between queries
        await asyncio.sleep(1)
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    asyncio.run(main()) 