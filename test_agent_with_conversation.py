#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys

async def query_agent(query_text, conversation_id):
    """Send a query to the agent runtime API with a specific conversation ID."""
    print(f"Sending query to agent: '{query_text}' with conversation ID: {conversation_id}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:5003/api/query",
                json={
                    "query": query_text,
                    "user_id": "test_user",
                    "conversation_id": conversation_id,
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
                    agents_used = []
                    execution_trace = []
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line:
                            continue
                            
                        if line.startswith('data: '):
                            try:
                                if line[6:] == "[DONE]":
                                    break
                                    
                                event_data = json.loads(line[6:])
                                
                                if 'content' in event_data and event_data['content']:
                                    print(f"Content chunk: {event_data['content']}")
                                    full_content += event_data['content']
                                elif 'chunk' in event_data:
                                    if event_data.get('complete', False):
                                        print("Stream complete")
                                        if 'response' in event_data:
                                            full_content = event_data['response']
                                        if 'agents_used' in event_data:
                                            agents_used = event_data['agents_used']
                                        break
                                    elif event_data['chunk']:
                                        print(f"Chunk: {event_data['chunk']}")
                                        full_content += event_data['chunk']
                                elif 'agent_call' in event_data:
                                    print(f"Agent call: {event_data['agent_call']}")
                                    if event_data['agent_call'] not in agents_used:
                                        agents_used.append(event_data['agent_call'])
                                elif 'agent_response' in event_data:
                                    print(f"Agent response: {event_data['agent_response'][:50]}...")
                                elif 'error' in event_data:
                                    print(f"Error: {event_data['error']}")
                                    return None
                            except json.JSONDecodeError:
                                print(f"Failed to parse event: {line[6:]}")
                    
                    return {
                        "content": full_content,
                        "agents_used": agents_used,
                        "execution_trace": execution_trace
                    }
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
    # Use the specific conversation ID
    conversation_id = "1d4ea981-887d-4114-bd89-9469fb89061b"
    
    # Test queries
    queries = [
        "what is onward platforms?",
        "who is rodney pressley?",
        "tell me about the agreement",
        "what is this NDA about?"
    ]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"Testing query: '{query}'")
        
        response = await query_agent(query, conversation_id)
        
        if response:
            print(f"\nFinal response content: {response.get('content', 'No content')}")
            print(f"Agents used: {response.get('agents_used', [])}")
            if 'execution_trace' in response and response['execution_trace']:
                print(f"Execution trace: {response['execution_trace']}")
        else:
            print("No response received")
        
        # Wait a bit between queries
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main()) 