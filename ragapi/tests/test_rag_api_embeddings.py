import os
import pytest
import pytest_asyncio
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch

from ragapi.main import app
from ragapi.config import settings


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup before each test and teardown after."""
    # Store original environment variables
    original_env = {}
    env_vars = [
        "RAG_EMBEDDING_PROVIDER",
        "RAG_EMBEDDING_MODEL", 
        "RAG_OPENAI_EMBEDDING_MODEL",
        "OPENAI_API_KEY"
    ]
    
    for var in env_vars:
        if var in os.environ:
            original_env[var] = os.environ[var]
    
    # Set up test environment
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    os.environ["RAG_EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
    
    yield
    
    # Restore original environment
    for var in env_vars:
        if var in original_env:
            os.environ[var] = original_env[var]
        elif var in os.environ:
            del os.environ[var]


def test_health_check_with_local_provider(client):
    """Test the health check endpoint with local embedding provider."""
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert settings.documents_path in response.json()["documents_path"]
    assert settings.embeddings_path in response.json()["embeddings_path"]


@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None,
                   reason="OpenAI API key not available")
def test_health_check_with_openai_provider(client):
    """Test the health check endpoint with OpenAI embedding provider."""
    # Skip if OpenAI package is not installed
    try:
        import openai
    except ImportError:
        pytest.skip("OpenAI package not installed")
    
    # Set OpenAI provider
    os.environ["RAG_EMBEDDING_PROVIDER"] = "openai"
    os.environ["RAG_OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_document_upload_with_local_provider(client):
    """Test document upload with local embedding provider."""
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    
    # Create a test document
    with tempfile.NamedTemporaryFile(suffix='.txt') as tmp:
        tmp.write(b"This is a test document for the local embedding provider.")
        tmp.flush()
        
        with open(tmp.name, "rb") as f:
            response = client.post(
                "/rag/documents",
                files={"file": ("test_local.txt", f, "text/plain")},
                data={"conversation_id": "test-local", "process_async": "true"}
            )
    
    assert response.status_code == 200
    assert response.json()["filename"] == "test_local.txt"
    assert "document_id" in response.json()


def test_document_upload_with_mocked_openai_provider(client):
    """Test document upload with mocked OpenAI embedding provider."""
    # Skip if OpenAI package is not installed
    try:
        from ragapi.embedding.providers.openai import OpenAIEmbedding
    except ImportError:
        pytest.skip("OpenAI package not installed")
    
    # Set up environment for OpenAI
    os.environ["RAG_EMBEDDING_PROVIDER"] = "openai"
    os.environ["RAG_OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"
    os.environ["OPENAI_API_KEY"] = "sk-mock-key-for-testing"
    
    # Create a test document
    with tempfile.NamedTemporaryFile(suffix='.txt') as tmp:
        tmp.write(b"This is a test document for the OpenAI embedding provider.")
        tmp.flush()
        
        # Mock the OpenAI embedding generation to avoid actual API calls
        mock_embedding = [0.1] * 1536
        
        with patch('ragapi.embedding.providers.openai.OpenAIEmbedding.get_embeddings',
                  return_value=[mock_embedding]):
            
            with open(tmp.name, "rb") as f:
                response = client.post(
                    "/rag/documents",
                    files={"file": ("test_openai.txt", f, "text/plain")},
                    data={"conversation_id": "test-openai", "process_async": "true"}
                )
    
    assert response.status_code == 200
    assert response.json()["filename"] == "test_openai.txt"
    assert "document_id" in response.json()


def test_query_with_local_provider(client):
    """Test document query with local embedding provider."""
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    
    query_request = {
        "query": "This is a test query for local embeddings",
        "conversation_id": "test-local-query",
        "top_k": 3
    }
    
    response = client.post("/rag/query", json=query_request)
    
    assert response.status_code == 200
    assert response.json()["query"] == query_request["query"]
    # Since we might not have actual data, we just check the structure
    assert "chunks" in response.json()
    assert "total_chunks_found" in response.json()


def test_query_with_mocked_openai_provider(client):
    """Test document query with mocked OpenAI embedding provider."""
    # Skip if OpenAI package is not installed
    try:
        from ragapi.embedding.providers.openai import OpenAIEmbedding
    except ImportError:
        pytest.skip("OpenAI package not installed")
    
    # Set up environment for OpenAI
    os.environ["RAG_EMBEDDING_PROVIDER"] = "openai"
    os.environ["RAG_OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"
    os.environ["OPENAI_API_KEY"] = "sk-mock-key-for-testing"
    
    query_request = {
        "query": "This is a test query for OpenAI embeddings",
        "conversation_id": "test-openai-query",
        "top_k": 3
    }
    
    # Mock the OpenAI embedding generation
    mock_embedding = [0.1] * 1536
    
    with patch('ragapi.embedding.providers.openai.OpenAIEmbedding.get_embeddings',
              return_value=[mock_embedding]):
        
        response = client.post("/rag/query", json=query_request)
    
    assert response.status_code == 200
    assert response.json()["query"] == query_request["query"]
    assert "chunks" in response.json()
    assert "total_chunks_found" in response.json()


def test_full_document_lifecycle_with_local_provider(client):
    """Test the full document lifecycle (upload, query, delete) with local provider."""
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    conversation_id = "test-lifecycle-local"
    
    # 1. Upload document
    with tempfile.NamedTemporaryFile(suffix='.txt') as tmp:
        tmp.write(b"This is a test document for the full lifecycle with local embeddings.")
        tmp.flush()
        
        with open(tmp.name, "rb") as f:
            upload_response = client.post(
                "/rag/documents",
                files={"file": ("lifecycle_local.txt", f, "text/plain")},
                data={"conversation_id": conversation_id, "process_async": "false"}
            )
    
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]
    
    # 2. Query document
    query_response = client.post(
        "/rag/query", 
        json={
            "query": "lifecycle test with local embeddings",
            "conversation_id": conversation_id,
            "top_k": 1
        }
    )
    
    assert query_response.status_code == 200
    
    # 3. Check document status
    status_response = client.get(
        f"/rag/documents/{document_id}", 
        params={"conversation_id": conversation_id}
    )
    
    assert status_response.status_code == 200
    assert status_response.json()["document_id"] == document_id
    
    # 4. Delete document
    delete_response = client.delete(
        f"/rag/documents/{document_id}", 
        params={"conversation_id": conversation_id}
    )
    
    assert delete_response.status_code == 200
    assert "deleted successfully" in delete_response.json()["message"] 