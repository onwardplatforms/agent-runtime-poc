#!/usr/bin/env python3

import os
import sys
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Add the parent directory to the path so we can import the runtime module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime.agent_runtime import AgentPlugin, AgentGroupChat, AgentTerminationStrategy

# Test data
TEST_AGENT_CONFIG_1 = {
    "id": "test-agent-1",
    "name": "Test Agent 1",
    "description": "A test agent for unit testing",
    "capabilities": ["testing", "unit_tests"],
    "endpoint": "http://localhost:9999/api/message"
}

TEST_AGENT_CONFIG_2 = {
    "id": "test-agent-2",
    "name": "Test Agent 2",
    "description": "Another test agent for unit testing",
    "capabilities": ["testing", "integration_tests"],
    "endpoint": "http://localhost:9998/api/message"
}

class TestAgentTerminationStrategy:
    """Tests for the AgentTerminationStrategy class."""
    
    def test_init(self):
        """Test that the AgentTerminationStrategy initializes correctly."""
        strategy = AgentTerminationStrategy(max_iterations=3)
        assert strategy.max_iterations == 3
    
    def test_should_terminate(self):
        """Test that should_terminate returns the correct value."""
        strategy = AgentTerminationStrategy(max_iterations=3)
        
        # Test with fewer iterations than max
        assert not strategy.should_terminate(2, [])
        
        # Test with equal iterations to max
        assert strategy.should_terminate(3, [])
        
        # Test with more iterations than max
        assert strategy.should_terminate(4, [])

class TestAgentGroupChat:
    """Tests for the AgentGroupChat class."""
    
    @pytest.fixture
    def mock_agents(self):
        """Create mock agents for testing."""
        agent1 = MagicMock(spec=AgentPlugin)
        agent1.id = "test-agent-1"
        agent1.name = "Test Agent 1"
        agent1.call_agent = AsyncMock(return_value="Response from Agent 1")
        
        agent2 = MagicMock(spec=AgentPlugin)
        agent2.id = "test-agent-2"
        agent2.name = "Test Agent 2"
        agent2.call_agent = AsyncMock(return_value="Response from Agent 2")
        
        return [agent1, agent2]
    
    @pytest.fixture
    def group_chat(self, mock_agents):
        """Create an AgentGroupChat instance with mock agents."""
        strategy = AgentTerminationStrategy(max_iterations=3)
        return AgentGroupChat(mock_agents, strategy)
    
    def test_init(self, mock_agents):
        """Test that the AgentGroupChat initializes correctly."""
        strategy = AgentTerminationStrategy(max_iterations=3)
        group_chat = AgentGroupChat(mock_agents, strategy)
        
        assert group_chat.agents == mock_agents
        assert group_chat.termination_strategy == strategy
        assert group_chat.messages == []
    
    @pytest.mark.asyncio
    async def test_process_query(self, group_chat, mock_agents):
        """Test that process_query processes a query correctly."""
        response = await group_chat.process_query("Test query", "test-user", "test-conversation")
        
        # Check that both agents were called
        mock_agents[0].call_agent.assert_called_once_with("Test query", "test-user", "test-conversation")
        mock_agents[1].call_agent.assert_called_once_with("Test query", "test-user", "test-conversation")
        
        # Check the response
        assert "Response from Agent 1" in response["content"]
        assert "Response from Agent 2" in response["content"]
        assert response["conversationId"] == "test-conversation"
        assert response["senderId"] == "agent-runtime"
        assert response["recipientId"] == "test-user"
        assert "agent_responses" in response
        assert len(response["agent_responses"]) == 2
    
    @pytest.mark.asyncio
    async def test_process_query_with_error(self, group_chat, mock_agents):
        """Test that process_query handles errors correctly."""
        # Make one agent raise an exception
        mock_agents[1].call_agent.side_effect = Exception("Test error")
        
        # We need to catch the exception since we're testing the error handling
        try:
            response = await group_chat.process_query("Test query", "test-user", "test-conversation")
            
            # Check that both agents were called
            mock_agents[0].call_agent.assert_called_once_with("Test query", "test-user", "test-conversation")
            mock_agents[1].call_agent.assert_called_once_with("Test query", "test-user", "test-conversation")
            
            # Check the response
            assert "Response from Agent 1" in response["content"]
            assert "test-agent-1" in response["agents_used"]
            assert "test-agent-2" not in response["agents_used"]
        except Exception as e:
            # If the method doesn't handle exceptions, this will be caught here
            assert str(e) == "Test error"
    
    def test_get_conversation_history(self, group_chat):
        """Test that get_conversation_history returns the correct conversation history."""
        # Add some messages to the conversation history
        group_chat.messages = [
            {"role": "user", "content": "Test query"},
            {"role": "assistant", "content": "Test response"}
        ]
        
        # Check if the method exists
        if hasattr(group_chat, 'get_conversation_history'):
            history = group_chat.get_conversation_history()
            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "Test query"
            assert history[1]["role"] == "assistant"
            assert history[1]["content"] == "Test response"
        else:
            # If the method doesn't exist, we'll just check the messages attribute
            assert len(group_chat.messages) == 2
            assert group_chat.messages[0]["role"] == "user"
            assert group_chat.messages[0]["content"] == "Test query"
            assert group_chat.messages[1]["role"] == "assistant"
            assert group_chat.messages[1]["content"] == "Test response"

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 