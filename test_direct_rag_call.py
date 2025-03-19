#!/usr/bin/env python3

import asyncio
import logging
import os
import json
from runtime.agent_runtime import AgentRuntime
from runtime.features.rag import RagPlugin

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("test_direct_rag_call")

async def test_direct_rag_call():
    """Test calling the RAG plugin directly."""
    print("Initializing AgentRuntime...")
    runtime = AgentRuntime()
    
    # Wait for initialization to complete
    await asyncio.sleep(1)
    
    # Get the conversation ID from the command line or use a default
    conversation_id = "1d4ea981-887d-4114-bd89-9469fb89061b"
    
    print(f"Using conversation ID: {conversation_id}")
    
    # Create a RAG plugin instance directly
    print("Creating RAG plugin instance...")
    
    # Load RAG configuration
    rag_config = {}
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "runtime/agents.json"), "r") as f:
            config = json.load(f)
            rag_config = config.get("settings", {}).get("data", {}).get("rag", {})
            if rag_config:
                print(f"Loaded RAG configuration: {rag_config}")
            else:
                print("No RAG configuration found in settings")
    except Exception as e:
        print(f"Error loading RAG configuration: {e}")
    
    # Create the RAG plugin
    rag_plugin = RagPlugin(rag_config)
    
    # Test queries
    queries = [
        "onward platforms",
        "rodney pressley",
        "agreement",
        "nda"
    ]
    
    for query in queries:
        print(f"\n{'='*50}")
        print(f"Testing direct RAG call with query: '{query}'")
        
        try:
            # Call the search_documents function directly
            result = await rag_plugin.search_documents(
                query=query,
                conversation_id=conversation_id,
                top_k=5
            )
            
            print(f"RAG search result:\n{result}")
        except Exception as e:
            print(f"Error calling RAG plugin: {e}")
    
    # Now test using the runtime's process_query method
    print("\n\n" + "="*50)
    print("Testing process_query with explicit RAG request")
    
    try:
        # Create a query that explicitly asks to use the RAG plugin
        explicit_rag_query = f"Search for information about Rodney in the documents for conversation {conversation_id}"
        
        # Process the query
        result = await runtime.process_query(
            query=explicit_rag_query,
            conversation_id=conversation_id,
            verbose=True
        )
        
        print(f"Process query result:\n{result.get('content', 'No content')}")
        print(f"Agents used: {result.get('agents_used', [])}")
    except Exception as e:
        print(f"Error processing query: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct_rag_call()) 