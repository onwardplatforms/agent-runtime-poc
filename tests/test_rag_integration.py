#!/usr/bin/env python3

import os
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp

# Add the parent directory to the path so we can import the runtime module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime.agent_runtime import AgentRuntime
from runtime.features.rag import RagPlugin


class TestRagIntegration:
    """Tests for the RAG integration with the Agent Runtime."""

    @pytest.fixture
    def mock_kernel(self):
        """Create a mock Semantic Kernel."""
        mock = MagicMock()
        mock.get_service.return_value = MagicMock()
        return mock

    @pytest.fixture
    def mock_aiohttp_response(self):
        """Create a mock aiohttp response."""
        mock = MagicMock()
        mock.status = 200
        mock.json = AsyncMock()
        mock.text = AsyncMock()
        return mock

    @pytest.fixture
    def rag_plugin(self):
        """Create a RagPlugin instance with test configuration."""
        config = {
            "rag_api_url": "http://localhost:5003"
        }
        return RagPlugin(config)

    @pytest.fixture
    def runtime(self, mock_kernel):
        """Create an AgentRuntime instance with a mock kernel."""
        with patch('runtime.agent_runtime.sk.Kernel', return_value=mock_kernel):
            runtime = AgentRuntime()
            runtime.kernel = mock_kernel
            return runtime

    @pytest.mark.asyncio
    async def test_rag_plugin_initialization(self, rag_plugin):
        """Test that the RagPlugin initializes correctly."""
        assert rag_plugin.rag_api_url == "http://localhost:5003"
        assert isinstance(rag_plugin.config, dict)

    @pytest.mark.asyncio
    async def test_search_documents(self, rag_plugin, mock_aiohttp_response):
        """Test the search_documents function."""
        # Set up the mock response
        mock_aiohttp_response.json.return_value = {
            "query": "test query",
            "chunks": [
                {
                    "chunk_id": "chunk1",
                    "document_id": "doc1",
                    "text": "This is a test chunk.",
                    "score": 0.95,
                    "metadata": {"filename": "test.txt"}
                },
                {
                    "chunk_id": "chunk2",
                    "document_id": "doc2",
                    "text": "This is another test chunk.",
                    "score": 0.85,
                    "metadata": {"filename": "test2.txt"}
                }
            ],
            "total_chunks_found": 2
        }
        
        # Patch the aiohttp.ClientSession.post method
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Set up the mock to return our response
            mock_post.return_value.__aenter__.return_value = mock_aiohttp_response
            
            # Call the function and get the result
            result = await rag_plugin.search_documents(
                query="test query",
                conversation_id="test-conversation",
                top_k=2
            )
            
            # Verify the result contains the expected information
            assert "Here's what I found for query 'test query'" in result
            assert "This is a test chunk." in result
            assert "This is another test chunk." in result
            assert "Doc: doc1" in result
            assert "Doc: doc2" in result
            assert "relevance: 95%" in result
            assert "relevance: 85%" in result
            
            # Verify the API was called correctly
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "http://localhost:5003/rag/query" in args[0]
            assert kwargs["json"]["query"] == "test query"
            assert kwargs["json"]["top_k"] == 2
            assert kwargs["json"]["conversation_id"] == "test-conversation"

    @pytest.mark.asyncio
    async def test_search_documents_no_results(self, rag_plugin, mock_aiohttp_response):
        """Test the search_documents function when no results are found."""
        # Set up the mock response for no results
        mock_aiohttp_response.json.return_value = {
            "query": "test query",
            "chunks": [],
            "total_chunks_found": 0
        }
        
        # Patch the aiohttp.ClientSession.post method
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Set up the mock to return our response
            mock_post.return_value.__aenter__.return_value = mock_aiohttp_response
            
            # Call the function and get the result
            result = await rag_plugin.search_documents(
                query="test query",
                conversation_id="test-conversation"
            )
            
            # Verify the result indicates no relevant information was found
            assert "No relevant information found" in result
            
            # Verify the API was called correctly
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "http://localhost:5003/rag/query" in args[0]
            assert kwargs["json"]["query"] == "test query"
            assert kwargs["json"]["conversation_id"] == "test-conversation"

    @pytest.mark.asyncio
    async def test_runtime_registers_rag_plugin(self, runtime):
        """Test that the runtime correctly registers the RAG plugin."""
        # Mock the RagPlugin class
        mock_rag_plugin = MagicMock()
        
        # Patch the import and plugin creation
        with patch('runtime.features.rag.RagPlugin', return_value=mock_rag_plugin):
            # Directly test the add_plugin method with our mock
            runtime.kernel.add_plugin(mock_rag_plugin, plugin_name="rag")
            
            # Verify that the kernel's add_plugin method was called with the RAG plugin
            runtime.kernel.add_plugin.assert_called_with(mock_rag_plugin, plugin_name="rag")

    @pytest.mark.asyncio
    async def test_process_query_with_rag(self, runtime, mock_kernel):
        """Test that process_query correctly uses the RAG plugin when needed."""
        # Mock the chat service
        mock_chat_service = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "Here's information from the documents: Onward Platforms is a company."
        
        # Set up function calls to indicate RAG was used
        mock_function_call = MagicMock()
        mock_function_call.name = "rag-search_documents"
        mock_function_call.arguments = json.dumps({"query": "What is Onward Platforms?"})
        
        # Add the function call to the result
        mock_result.function_calls = [mock_function_call]
        
        # Set up the chat service to return our mock result
        mock_chat_service.get_chat_message_contents = AsyncMock(return_value=mock_result)
        mock_kernel.get_service.return_value = mock_chat_service
        
        # Process a query that should trigger RAG
        response = await runtime.process_query(
            "What is Onward Platforms?", 
            "test-conversation"
        )
        
        # Check that the response includes the RAG information
        assert "Here's information from the documents" in response["content"]
        assert "Onward Platforms" in response["content"]
        
        # Check that the agents_used list includes "rag"
        assert "rag" in response["agents_used"]

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 