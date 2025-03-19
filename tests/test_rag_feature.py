"""
Test the RAG feature integration.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Add the parent directory to the path so we can import the runtime modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.features.rag import RagPlugin


class TestRagFeature(unittest.TestCase):
    """Test the RAG feature functionality."""

    def setUp(self):
        """Set up the test environment."""
        self.rag_config = {
            "local_storage": {
                "documents_path": "./.data/documents",
                "embeddings_path": "./.data/embeddings"
            }
        }
        self.plugin = RagPlugin(self.rag_config)

    @patch('aiohttp.ClientSession.post')
    def test_search_documents(self, mock_post):
        """Test the search_documents function."""
        # Set up the mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "query": "test query",
            "chunks": [
                {
                    "chunk_id": "chunk1",
                    "document_id": "doc1",
                    "text": "This is a test chunk.",
                    "score": 0.95
                },
                {
                    "chunk_id": "chunk2",
                    "document_id": "doc2",
                    "text": "This is another test chunk.",
                    "score": 0.85
                }
            ],
            "total_chunks_found": 2
        })
        mock_post.return_value.__aenter__.return_value = mock_response

        # Call the function and get the result
        result = asyncio.run(self.plugin.search_documents(
            query="test query",
            conversation_id="test-conversation",
            top_k=2
        ))

        # Verify the result
        self.assertIn("Here's what I found in the documents for the query", result)
        self.assertIn("This is a test chunk", result)
        self.assertIn("This is another test chunk", result)
        self.assertIn("Found 2 relevant passages", result)
        
        # Verify the API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args[0][0]
        self.assertEqual(call_args, "http://localhost:5005/rag/query")

    @patch('aiohttp.ClientSession.post')
    @patch('aiohttp.ClientSession.get')
    def test_search_documents_no_results(self, mock_get, mock_post):
        """Test the search_documents function when no results are found."""
        # Set up the mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "query": "test query",
            "chunks": [],
            "total_chunks_found": 0
        })
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Set up the mock document check response
        mock_doc_response = AsyncMock()
        mock_doc_response.status = 200
        mock_doc_response.json = AsyncMock(return_value={
            "documents": []
        })
        mock_get.return_value.__aenter__.return_value = mock_doc_response

        # Call the function and get the result
        result = asyncio.run(self.plugin.search_documents(
            query="test query",
            conversation_id="test-conversation"
        ))

        # Verify the result
        self.assertIn("No documents have been uploaded yet", result)

    @patch('aiohttp.ClientSession.post')
    def test_search_documents_with_kernel_context(self, mock_post):
        """Test the search_documents function with kernel context."""
        # Set up the mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "query": "test query",
            "chunks": [
                {
                    "chunk_id": "chunk1",
                    "document_id": "doc1",
                    "text": "This is a test chunk.",
                    "score": 0.95
                }
            ],
            "total_chunks_found": 1
        })
        mock_post.return_value.__aenter__.return_value = mock_response

        # Create a mock kernel context with conversation_id
        class MockContext:
            def __init__(self):
                self.variables = {
                    'extension_data': '{"conversation_id": "context-conversation-id"}'
                }

        # Call the function with kernel context but no conversation_id
        result = asyncio.run(self.plugin.search_documents(
            query="test query",
            conversation_id=None,
            kernel_context=MockContext()
        ))

        # Verify the result
        self.assertIn("Here's what I found in the documents for the query", result)
        self.assertIn("This is a test chunk", result)
        
        # Verify the API was called with the conversation_id from the context
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload.get('conversation_id'), "context-conversation-id")


if __name__ == "__main__":
    unittest.main() 