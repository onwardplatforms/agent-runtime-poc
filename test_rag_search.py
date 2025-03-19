#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys
import os
from typing import Dict, Any, Optional

async def query_agent(query_text: str, conversation_id: Optional[str] = None, verbose: bool = True):
    """Send a query to the agent runtime API."""
    print(f"Sending query: '{query_text}'")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prepare the request payload
            payload = {
                "query": query_text,
                "user_id": "test_user",
                "verbose": verbose,
                "stream": False  # Explicitly set stream to False
            }
            
            # Add conversation_id if provided
            if conversation_id:
                payload["conversation_id"] = conversation_id
                print(f"Using conversation ID: {conversation_id}")
            
            async with session.post(
                "http://localhost:5003/api/query",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error: {response.status} - {error_text}")
                    return None
                
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    data = await response.json()
                    return data
                elif 'text/event-stream' in content_type:
                    print("Received streaming response, processing events...")
                    full_content = ""
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            try:
                                event_data = json.loads(line[6:])
                                if 'content' in event_data:
                                    print(f"Content chunk: {event_data['content']}")
                                    full_content += event_data['content']
                                elif 'chunk' in event_data:
                                    print(f"Chunk: {event_data['chunk']}")
                                    if event_data['chunk']:
                                        full_content += event_data['chunk']
                                elif 'complete' in event_data and event_data['complete']:
                                    print("Stream complete")
                                    break
                            except json.JSONDecodeError:
                                print(f"Failed to parse event: {line[6:]}")
                    
                    return {"content": full_content, "agents_used": []}
                else:
                    print(f"Unexpected content type: {content_type}")
                    text = await response.text()
                    print(f"Response text: {text[:200]}...")
                    return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

async def test_rag_search():
    """Test the RAG search functionality."""
    # Generate a unique conversation ID for this test
    conversation_id = "test-rag-" + os.urandom(4).hex()
    
    # Test 1: Ask about tools to verify RAG is mentioned
    print("\n" + "="*50)
    print("Test 1: Ask about available tools")
    response = await query_agent("What tools do you have?", conversation_id)
    
    if response:
        print(f"\nResponse content: {response.get('content', 'No content')}")
        print(f"Agents used: {response.get('agents_used', [])}")
        
        # Check if RAG is mentioned in the response
        if "rag" in response.get('content', '').lower():
            print("✅ RAG capability is mentioned in the response")
        else:
            print("❌ RAG capability is NOT mentioned in the response")
    else:
        print("No response received")
    
    # Test 2: Direct RAG search query
    print("\n" + "="*50)
    print("Test 2: Direct RAG search query")
    response = await query_agent("Search for information about Rodney in the documents", conversation_id)
    
    if response:
        print(f"\nResponse content: {response.get('content', 'No content')}")
        print(f"Agents used: {response.get('agents_used', [])}")
        
        # Check if RAG was used
        if "rag" in response.get('agents_used', []):
            print("✅ RAG agent was used for the search")
        else:
            print("❌ RAG agent was NOT used for the search")
    else:
        print("No response received")
    
    # Test 3: Explicit call to RAG agent
    print("\n" + "="*50)
    print("Test 3: Explicit call to RAG agent")
    response = await query_agent("Call the RAG agent to search for Rodney", conversation_id)
    
    if response:
        print(f"\nResponse content: {response.get('content', 'No content')}")
        print(f"Agents used: {response.get('agents_used', [])}")
        
        # Check if RAG was used
        if "rag" in response.get('agents_used', []):
            print("✅ RAG agent was used for the search")
        else:
            print("❌ RAG agent was NOT used for the search")
    else:
        print("No response received")

async def main():
    """Run the test."""
    await test_rag_search()

if __name__ == "__main__":
    asyncio.run(main()) 