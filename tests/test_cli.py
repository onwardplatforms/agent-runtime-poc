#!/usr/bin/env python3

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner

# Add the parent directory to the path so we can import the CLI module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the CLI module
from cli.runtime import cli, send_query

class TestCLI:
    """Tests for the CLI functionality."""
    
    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner for testing."""
        return CliRunner()
    
    def test_cli_help(self, runner):
        """Test that the CLI help command works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Options:" in result.output
        assert "Commands:" in result.output
    
    def test_send_query(self):
        """Test that send_query works with mocked requests."""
        with patch("requests.post") as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": "Test response"}
            mock_post.return_value = mock_response
            
            # Call send_query
            result = send_query("Test query")
            
            # Check the API call
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0].endswith("/api/query")
            assert kwargs["json"]["query"] == "Test query"
            
            # Check the result
            assert result["content"] == "Test response"
    
    def test_send_query_with_conversation_id(self):
        """Test that send_query works with a conversation ID."""
        with patch("requests.post") as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"content": "Test response"}
            mock_post.return_value = mock_response
            
            # Call send_query with conversation_id
            result = send_query("Test query", conversation_id="test-conv-id")
            
            # Check the API call
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0].endswith("/api/query")
            assert kwargs["json"]["query"] == "Test query"
            assert kwargs["json"]["conversation_id"] == "test-conv-id"
            
            # Check the result
            assert result["content"] == "Test response"
    
    def test_cli_query(self, runner):
        """Test that the CLI query command works."""
        with patch("cli.runtime.send_streaming_query") as mock_send_query:
            mock_send_query.return_value = {"content": "Test response"}
            
            # Run the CLI command
            result = runner.invoke(cli, ["query", "Test query"])
            
            # Check that the command was successful
            assert result.exit_code == 0
            
            # Since we mocked send_streaming_query, we can check the function call
            mock_send_query.assert_called_once()
            args, kwargs = mock_send_query.call_args
            assert args[0] == "Test query"
            assert "conversation_id" in kwargs
    
    def test_cli_direct(self, runner):
        """Test that the CLI direct command works."""
        with patch("cli.runtime.call_agent_directly") as mock_call_agent:
            # Run the CLI command
            result = runner.invoke(cli, ["direct", "agent1", "Test query"])
            
            # Check that the command was successful
            assert result.exit_code == 0
            mock_call_agent.assert_called_once_with({"agent1": "Test query"})
    
    def test_cli_group(self, runner):
        """Test that the CLI group command works."""
        with patch("cli.runtime.send_streaming_group_chat_query") as mock_send_group:
            mock_send_group.return_value = {"content": "Test group response"}
            
            # Run the CLI command
            result = runner.invoke(cli, ["group", "agent1,agent2", "Test query"])
            
            # Check that the command was successful
            assert result.exit_code == 0
            
            # Since we mocked send_streaming_group_chat_query, we can check the function call
            mock_send_group.assert_called_once()
            args, kwargs = mock_send_group.call_args
            assert args[0] == "Test query"
            assert "agent_ids" in kwargs
    
    def test_cli_status(self, runner):
        """Test that the CLI status command works."""
        with patch("cli.runtime.check_runtime_status") as mock_check:
            mock_check.return_value = True
            
            # Run the CLI command
            result = runner.invoke(cli, ["status"])
            
            # Check that the command was successful
            assert result.exit_code == 0
            assert "Runtime is available" in result.output
            mock_check.assert_called_once()
    
    def test_cli_agents(self, runner):
        """Test that the CLI agents command works."""
        with patch("cli.runtime.list_agents") as mock_list_agents:
            mock_list_agents.return_value = {
                "agents": [
                    {"id": "agent1", "name": "Agent 1", "description": "Test agent 1", "capabilities": ["cap1"], "endpoint": "http://localhost:5001"},
                    {"id": "agent2", "name": "Agent 2", "description": "Test agent 2", "capabilities": ["cap2"], "endpoint": "http://localhost:5002"}
                ]
            }
            
            # Run the CLI command
            result = runner.invoke(cli, ["agents"])
            
            # Check that the command was successful
            assert result.exit_code == 0
            assert "Agent 1" in result.output
            assert "Agent 2" in result.output
            mock_list_agents.assert_called_once()

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 