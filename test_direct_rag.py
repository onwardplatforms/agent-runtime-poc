#!/usr/bin/env python3

import asyncio
import os
import sys
from runtime.agent_runtime import AgentRuntime

async def test_direct_rag():
    """Test the RAG plugin directly."""
    print("Initializing AgentRuntime...")
    runtime = AgentRuntime()
    
    # Wait for kernel initialization
    await asyncio.sleep(1)
    
    print("\nTesting direct RAG plugin invocation...")
    try:
        if runtime.kernel and "rag" in runtime.kernel.plugins:
            print("RAG plugin is available in the kernel")
            
            # Call the RAG plugin directly
            result = await runtime.kernel.invoke_function(
                plugin_name="rag",
                function_name="search_documents",
                arguments={
                    "query": "Rodney",
                    "conversation_id": "test-direct-rag",
                    "top_k": 5
                }
            )
            
            print("\nRAG search result:")
            print(result)
        else:
            print("RAG plugin is NOT available in the kernel")
    except Exception as e:
        print(f"Error calling RAG plugin directly: {e}")
    
    print("\nTesting process_query with explicit RAG request...")
    try:
        response = await runtime.process_query(
            query="Call the RAG agent to search for Rodney",
            conversation_id="test-direct-rag",
            verbose=True
        )
        
        print("\nProcess query response:")
        print(f"Content: {response.get('content', 'No content')}")
        print(f"Agents used: {response.get('agents_used', [])}")
        if 'execution_trace' in response and response['execution_trace']:
            print(f"Execution trace: {response['execution_trace']}")
    except Exception as e:
        print(f"Error in process_query: {e}")

async def main():
    """Run the test."""
    await test_direct_rag()

if __name__ == "__main__":
    asyncio.run(main()) 