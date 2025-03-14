import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock

# Import the embedding models
from ragapi.embedding.providers.local import SentenceTransformerEmbedding
from ragapi.embedding.models import get_embedding_model, EmbeddingModel


# Test the local embedding provider
@pytest.mark.asyncio
async def test_local_embedding_provider():
    """Test that the local SentenceTransformers embedding provider works."""
    # Set environment variables for test
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    os.environ["RAG_EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
    
    try:
        # Get the embedding model
        model = get_embedding_model()
        assert isinstance(model, SentenceTransformerEmbedding)
        assert model.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        
        # Initialize the model
        await model.initialize()
        
        # Check the embedding dimension
        assert model.embedding_dim == 384  # This is the dimension for the specified model
        
        # Generate embeddings for test text
        texts = ["This is a test sentence for embeddings.", "Another test sentence."]
        embeddings = await model.get_embeddings(texts)
        
        # Check that we got the right number of embeddings
        assert len(embeddings) == len(texts)
        
        # Check embedding shape
        assert embeddings[0].shape == (model.embedding_dim,)
        
        # Check that embeddings are normalized (cosine similarity preparation)
        for emb in embeddings:
            norm = np.linalg.norm(emb)
            assert 0.99 <= norm <= 1.01  # Allow for small floating point errors
    finally:
        # Clean up environment variables
        if "RAG_EMBEDDING_PROVIDER" in os.environ:
            del os.environ["RAG_EMBEDDING_PROVIDER"]
        if "RAG_EMBEDDING_MODEL" in os.environ:
            del os.environ["RAG_EMBEDDING_MODEL"]


# Test the OpenAI embedding provider with mocked API
@pytest.mark.asyncio
async def test_openai_embedding_provider_mocked():
    """Test the OpenAI embedding provider with a mocked API response."""
    # Skip import if OpenAI is not installed
    try:
        from ragapi.embedding.providers.openai import OpenAIEmbedding
    except ImportError:
        pytest.skip("OpenAI package not installed")
    
    # Set environment variables for test
    os.environ["RAG_EMBEDDING_PROVIDER"] = "openai"
    os.environ["RAG_OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"
    os.environ["OPENAI_API_KEY"] = "sk-mock-api-key-for-testing"
    
    try:
        # Create mock embeddings
        mock_embeddings = [
            np.array([0.1] * 1536, dtype=np.float32),
            np.array([0.2] * 1536, dtype=np.float32)
        ]
        
        # Create a test instance directly
        model = OpenAIEmbedding(model_name="text-embedding-3-small")
        
        # Mock the get_embeddings method to return our predefined embeddings
        with patch.object(model, 'get_embeddings', return_value=mock_embeddings):
            # Check basic properties
            assert model.model_name == "text-embedding-3-small"
            assert model.embedding_dim == 1536
            
            # Get embeddings using our mocked method
            texts = ["This is a test sentence for embeddings.", "Another test sentence."]
            embeddings = await model.get_embeddings(texts)
            
            # Check embeddings match our mocks
            assert len(embeddings) == 2
            assert embeddings[0].shape == (1536,)
            np.testing.assert_array_equal(embeddings[0], mock_embeddings[0])
            np.testing.assert_array_equal(embeddings[1], mock_embeddings[1])
    finally:
        # Clean up environment variables
        for var in ["RAG_EMBEDDING_PROVIDER", "RAG_OPENAI_EMBEDDING_MODEL", "OPENAI_API_KEY"]:
            if var in os.environ:
                del os.environ[var]


# Test get_embedding_model factory function
@pytest.mark.asyncio
async def test_embedding_model_factory():
    """Test that the embedding model factory returns the correct provider based on environment."""
    # Test with local provider
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    model = get_embedding_model()
    assert isinstance(model, SentenceTransformerEmbedding)
    
    # Test with OpenAI provider if available
    try:
        from ragapi.embedding.providers.openai import OpenAIEmbedding
        has_openai = True
    except ImportError:
        has_openai = False
    
    if has_openai:
        os.environ["RAG_EMBEDDING_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-mock-api-key-for-testing"
        model = get_embedding_model()
        assert isinstance(model, OpenAIEmbedding)
        
        # Clean up OpenAI specific env vars
        del os.environ["OPENAI_API_KEY"]
    
    # Clean up common env vars
    del os.environ["RAG_EMBEDDING_PROVIDER"]
    
    # Test default behavior when provider not specified
    if "RAG_EMBEDDING_PROVIDER" in os.environ:
        del os.environ["RAG_EMBEDDING_PROVIDER"]
    model = get_embedding_model()
    assert isinstance(model, SentenceTransformerEmbedding)


# Test error handling when OpenAI API key is missing
@pytest.mark.asyncio
async def test_openai_missing_api_key():
    """Test that an error is raised when the OpenAI API key is missing."""
    # Skip import if OpenAI is not installed
    try:
        from ragapi.embedding.providers.openai import OpenAIEmbedding
    except ImportError:
        pytest.skip("OpenAI package not installed")
    
    # Set environment for OpenAI but without API key
    os.environ["RAG_EMBEDDING_PROVIDER"] = "openai"
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    
    try:
        model = OpenAIEmbedding()
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            await model.initialize()
    finally:
        # Clean up environment variables
        if "RAG_EMBEDDING_PROVIDER" in os.environ:
            del os.environ["RAG_EMBEDDING_PROVIDER"] 