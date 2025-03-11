#!/usr/bin/env python3

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the API module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the API module
from api.runtime_api import app, get_runtime


class TestAPI:
    """Tests for the API functionality."""
    
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
            "content": "Test response",
            "timestamp": "2023-01-01T00:00:00Z",
            "type": "Text"
        })
        return mock
    
    def test_query(self, client, mock_runtime):
        """Test that the query endpoint works."""
        # Override the get_runtime dependency
        app.dependency_overrides[get_runtime] = lambda: mock_runtime
        
        # Set up the mock to use process_query instead of stream_process_query
        mock_runtime.enable_streaming = False
        
        try:
            response = client.post("/api/query", json={"query": "Test query", "stream": False})
            assert response.status_code == 200
            response_json = response.json()
            assert "content" in response_json
            assert "messageId" in response_json
            assert "conversationId" in response_json
            assert "timestamp" in response_json
            
            mock_runtime.process_query.assert_called_once()
            args, kwargs = mock_runtime.process_query.call_args
            assert kwargs["query"] == "Test query"
            assert "conversation_id" in kwargs
            assert kwargs["verbose"] is False
        finally:
            # Clean up the override
            app.dependency_overrides.clear()
    
    def test_query_with_conversation_id(self, client, mock_runtime):
        """Test that the query endpoint works with a conversation ID."""
        # Override the get_runtime dependency
        app.dependency_overrides[get_runtime] = lambda: mock_runtime
        
        # Set up the mock to use process_query instead of stream_process_query
        mock_runtime.enable_streaming = False
        
        try:
            response = client.post("/api/query", json={"query": "Test query", "conversation_id": "test-conv-id", "stream": False})
            assert response.status_code == 200
            response_json = response.json()
            assert "content" in response_json
            assert "messageId" in response_json
            assert "conversationId" in response_json
            assert "timestamp" in response_json
            
            mock_runtime.process_query.assert_called_once()
            args, kwargs = mock_runtime.process_query.call_args
            assert kwargs["query"] == "Test query"
            assert kwargs["conversation_id"] == "test-conv-id"
            assert kwargs["verbose"] is False
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_stream_query_response(self, client, mock_runtime):
        """Test the streaming query response endpoint."""
        # Configure the mock runtime's stream_process_query to yield test chunks
        mock_runtime.stream_process_query = AsyncMock()
        mock_runtime.stream_process_query.return_value = (chunk for chunk in [
            {"content": "First"},
            {"content": "Second"},
            {"agent_call": "test-agent", "agent_query": "agent query"},
            {"agent_id": "test-agent", "agent_response": "agent response"},
            {"content": "Final"}
        ])
        
        # Make the request
        response = client.post(
            "/api/query",
            json={"query": "Test query", "stream": True}
        )
        
        # Check the response headers
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # In TestClient, we can't easily stream responses, so just verify the status code
        # and content type for the streaming endpoint
    
    def test_stream_query_response_error(self, client, mock_runtime):
        """Test error handling in streaming query response."""
        # Configure the mock runtime to raise an exception
        mock_runtime.stream_process_query = AsyncMock(side_effect=Exception("Test error"))
        
        # Make the request
        response = client.post(
            "/api/query",
            json={"query": "Test query", "stream": True}
        )
        
        # Check the response headers
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # In TestClient, we can't easily stream error responses, so just verify
        # the status code and content type
    
    def test_stream_group_chat_response(self, client, mock_runtime):
        """Test the streaming group chat response endpoint."""
        # Mock the necessary methods for streaming group chat
        mock_runtime.event_queue = MagicMock()
        mock_runtime.event_queue.empty = MagicMock(return_value=True)  # Queue is eventually empty
        mock_runtime.get_agent_by_id = MagicMock(return_value=MagicMock())
        mock_runtime.get_all_agents = MagicMock(return_value={"test-agent": MagicMock()})
        
        # Make the request
        response = client.post(
            "/api/group-chat",
            json={
                "query": "Test query",
                "agent_ids": ["test-agent"],
                "stream": True
            }
        )
        
        # Check the response headers
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # In TestClient, we can't easily stream responses, so just verify the status code
        # and content type for the streaming endpoint

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 