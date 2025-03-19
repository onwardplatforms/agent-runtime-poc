#!/usr/bin/env python3

import asyncio
import logging
import os
from runtime.agent_runtime import AgentRuntime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("test_rag_integration")

# Set debug mode for more verbose output
os.environ["AGENT_RUNTIME_DEBUG"] = "true"

async def main():
    """Test the RAG plugin integration."""
    print("Initializing Agent Runtime...")
    runtime = AgentRuntime()
    
    # Wait for initialization
    await asyncio.sleep(2)
    
    # Check if the kernel has plugins
    if runtime.kernel:
        print("\nExamining kernel plugins...")
        
        # Print all available plugins
        print("\nAvailable plugins in kernel.plugins:")
        for plugin_name, plugin in runtime.kernel.plugins.items():
            print(f"- {plugin_name}")
            
        # Check if the RAG plugin is registered
        if "rag" in runtime.kernel.plugins:
            print("\nRAG plugin is registered!")
            
            # Test a query using the RAG plugin
            print("\nTesting a query with the RAG plugin...")
            conversation_id = "test-conversation"
            
            # Create a test query that would use the RAG plugin
            test_query = "Can you search my documents for information about machine learning?"
            
            print(f"Processing query: '{test_query}'")
            response = await runtime.process_query(
                query=test_query,
                conversation_id=conversation_id,
                verbose=True
            )
            
            print("\nResponse:")
            print(response.get("content", "No content"))
            
            if "agents_used" in response:
                print(f"\nAgents used: {response['agents_used']}")
                
            if "execution_trace" in response:
                print("\nExecution trace:")
                for trace in response.get("execution_trace", []):
                    print(f"- {trace}")
        else:
            print("\nRAG plugin is not registered in the kernel.")
            
            # List all registered plugins
            print("\nRegistered plugins:")
            for plugin_name in runtime.kernel.plugins:
                print(f"- {plugin_name}")
    else:
        print("Kernel not initialized properly.")

if __name__ == "__main__":
    # Ensure the API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable")
    else:
        asyncio.run(main()) 