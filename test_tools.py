#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys
import os

async def query_agent(query_text):
    """Send a query to the agent runtime API."""
    print(f"Sending query: '{query_text}'")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:5003/api/query",
                json={
                    "query": query_text,
                    "user_id": "test_user",
                    "conversation_id": "test_conversation",
                    "verbose": True,
                    "stream": False  # Explicitly set stream to False
                }
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

async def main():
    """Run the test."""
    # Test query about tools
    query = "What tools do you have?"
    
    print("\n" + "="*50)
    response = await query_agent(query)
    
    if response:
        print(f"Response content: {response.get('content', 'No content')}")
        print(f"Agents used: {response.get('agents_used', [])}")
        if 'execution_trace' in response and response['execution_trace']:
            print(f"Execution trace: {response['execution_trace']}")
    else:
        print("No response received")

if __name__ == "__main__":
    asyncio.run(main()) 