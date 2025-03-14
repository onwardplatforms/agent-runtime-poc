import pytest
from fastapi.testclient import TestClient
import os
import io
import tempfile
from pathlib import Path

from ..main import app

# Create a test client
client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_document_upload():
    """Test document upload."""
    # Create a test file
    content = "This is a test document for upload testing."
    files = {"file": ("test.txt", content)}
    
    response = client.post(
        "/rag/documents",
        files=files,
        data={"conversation_id": "test-conversation", "process_async": "false"}
    )
    
    assert response.status_code == 200
    assert response.json()["filename"] == "test.txt"
    assert "document_id" in response.json()
    
    # Clean up
    doc_id = response.json()["document_id"]
    client.delete(f"/rag/documents/{doc_id}", params={"conversation_id": "test-conversation"})


def test_document_query():
    """Test document query."""
    response = client.post(
        "/rag/query",
        json={
            "query": "test query",
            "conversation_id": "test-conversation",
            "top_k": 3
        }
    )
    
    assert response.status_code == 200
    assert response.json()["query"] == "test query"
    assert "chunks" in response.json()
    
    
@pytest.mark.asyncio
async def test_document_lifecycle():
    """Test the full document lifecycle: upload, query, delete."""
    # Create a test file
    content = "This is a comprehensive test document for testing the full RAG pipeline."
    files = {"file": ("lifecycle.txt", content)}
    
    # 1. Upload the document
    upload_response = client.post(
        "/rag/documents",
        files=files,
        data={"conversation_id": "lifecycle-test", "process_async": "false"}
    )
    
    assert upload_response.status_code == 200
    doc_id = upload_response.json()["document_id"]
    
    # 2. Query for the document
    query_response = client.post(
        "/rag/query",
        json={
            "query": "comprehensive test",
            "conversation_id": "lifecycle-test",
            "top_k": 2
        }
    )
    
    assert query_response.status_code == 200
    
    # 3. Delete the document
    delete_response = client.delete(
        f"/rag/documents/{doc_id}",
        params={"conversation_id": "lifecycle-test"}
    )
    
    assert delete_response.status_code == 200
    assert "deleted successfully" in delete_response.json()["message"]
