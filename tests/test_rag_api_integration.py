#!/usr/bin/env python3

import os
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the API module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.runtime_api import app, get_runtime
from runtime.agent_runtime import AgentRuntime
from runtime.features.rag import RagPlugin


class TestRagApiIntegration:
    """Tests for the RAG API integration with the Runtime API."""

    @pytest.fixture
    def client(self):
        """Create a FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_runtime(self):
        """Create a mock AgentRuntime for testing."""
        mock = MagicMock()
        mock.process_query = AsyncMock(return_value={
            "messageId": "test-msg-id",
            "conversationId": "test-conv-id",
            "senderId": "runtime",
            "recipientId": "user",
            "content": "Test response with document information",
            "timestamp": "2023-01-01T00:00:00Z",
            "type": "Text",
            "agents_used": ["rag"]
        })
        return mock

    @pytest.fixture
    def mock_aiohttp_response(self):
        """Create a mock aiohttp response."""
        mock = MagicMock()
        mock.status = 200
        mock.json = AsyncMock(return_value={
            "documents": [
                {
                    "document_id": "doc1",
                    "filename": "test.txt",
                    "file_size": 1024,
                    "mime_type": "text/plain",
                    "chunk_count": 5,
                    "created_at": "2023-01-01T00:00:00Z",
                    "status": "INDEXED"
                }
            ]
        })
        return mock

    def test_list_documents_endpoint(self, client, mock_runtime, mock_aiohttp_response):
        """Test the /api/rag/documents endpoint."""
        # Patch the aiohttp.ClientSession.get method
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Set up the mock to return our response
            mock_get.return_value.__aenter__.return_value = mock_aiohttp_response
            
            # Patch the get_runtime dependency to return our mock runtime
            app.dependency_overrides[get_runtime] = lambda: mock_runtime
            
            # Make the request
            response = client.get("/api/rag/documents")
            
            # Verify the response
            assert response.status_code == 200
            data = response.json()
            assert "documents" in data
            assert len(data["documents"]) == 1
            assert data["documents"][0]["document_id"] == "doc1"
            
            # Clean up
            app.dependency_overrides = {}

    def test_query_with_rag_plugin(self, client, mock_runtime):
        """Test that the /api/query endpoint correctly uses the RAG plugin."""
        # Patch the get_runtime dependency to return our mock runtime
        app.dependency_overrides[get_runtime] = lambda: mock_runtime
        
        # Make the request with a query that should trigger RAG
        response = client.post(
            "/api/query",
            json={
                "query": "What information is in the document?",
                "verbose": True,
                "stream": False
            }
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test response with document information"
        assert "rag" in data["agents_used"]
        
        # Verify the runtime's process_query was called with the correct arguments
        mock_runtime.process_query.assert_called_once()
        args, kwargs = mock_runtime.process_query.call_args
        assert args[0] == "What information is in the document?"
        assert kwargs["verbose"] is True
        
        # Clean up
        app.dependency_overrides = {}

    def test_streaming_query_with_rag_plugin(self, client, mock_runtime):
        """Test that the streaming query endpoint correctly uses the RAG plugin."""
        # Mock the stream_process_query method
        mock_runtime.stream_process_query = AsyncMock()
        
        # Set up the mock to yield chunks that indicate RAG usage
        async def mock_stream_generator():
            yield {"chunk": "Starting streaming response...", "complete": False}
            yield {"content": "Here's information from the documents: ", "complete": False}
            yield {"content": "Onward Platforms is a company.", "complete": False}
            yield {"agent_call": "rag", "agent_query": "What is Onward Platforms?", "complete": False}
            yield {"agent_response": "Onward Platforms is a Delaware corporation.", "complete": False}
            yield {
                "chunk": None,
                "complete": True,
                "response": "Here's information from the documents: Onward Platforms is a company.",
                "conversation_id": "test-conv-id",
                "processing_time": 0.5,
                "agents_used": ["rag"]
            }
        
        mock_runtime.stream_process_query.return_value = mock_stream_generator()
        
        # Patch the get_runtime dependency to return our mock runtime
        app.dependency_overrides[get_runtime] = lambda: mock_runtime
        
        # This test is more complex because we need to handle streaming responses
        # For simplicity, we'll just verify that the endpoint is called correctly
        # and that the runtime's stream_process_query method is called with the right arguments
        
        # Make the request with a query that should trigger RAG
        with client.stream(
            "POST",
            "/api/query",
            json={
                "query": "What is Onward Platforms?",
                "verbose": True,
                "stream": True
            }
        ) as response:
            # Verify the response status
            assert response.status_code == 200
            
            # Verify the runtime's stream_process_query was called with the correct arguments
            mock_runtime.stream_process_query.assert_called_once()
            args, kwargs = mock_runtime.stream_process_query.call_args
            assert args[0] == "What is Onward Platforms?"
            assert kwargs["verbose"] is True
        
        # Clean up
        app.dependency_overrides = {}

    def test_upload_document(self, client, mock_runtime, mock_aiohttp_response):
        """Test the document upload endpoint."""
        # Set up the mock response for the upload
        upload_response = MagicMock()
        upload_response.status = 200
        upload_response.json = AsyncMock(return_value={
            "document_id": "doc1",
            "conversation_id": None,
            "filename": "test.txt",
            "status": "INDEXED",
            "message": "Document uploaded and processed successfully"
        })
        
        # Patch the aiohttp.ClientSession.post method
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Set up the mock to return our response
            mock_post.return_value.__aenter__.return_value = upload_response
            
            # Patch the get_runtime dependency to return our mock runtime
            app.dependency_overrides[get_runtime] = lambda: mock_runtime
            
            # Create a test file
            test_content = "This is a test document for RAG."
            test_file = {"files": ("test.txt", test_content, "text/plain")}
            
            # Make the request
            response = client.post(
                "/api/upload",
                files=test_file
            )
            
            # Verify the response
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "files" in data
            
            # Clean up
            app.dependency_overrides = {}

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 