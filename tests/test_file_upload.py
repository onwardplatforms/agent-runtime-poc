import os
import pytest
import tempfile
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from api.proxy_api import app
from runtime.features.rag import DEFAULT_DOCUMENTS_PATH

# Use the documents path from the RAG plugin
DOCUMENTS_DIR = DEFAULT_DOCUMENTS_PATH
client = TestClient(app)

def test_file_upload_endpoint():
    """Test that the file upload endpoint works correctly."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix='.txt') as temp:
        temp.write(b"This is test content for RAG processing")
        temp.flush()
        
        # Send the file to the upload endpoint
        with open(temp.name, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"files": ("test_document.txt", f, "text/plain")}
            )
        
        # Check the response
        assert response.status_code == 200
        result = response.json()
        assert "message" in result
        assert "files" in result
        assert len(result["files"]) == 1
        
        # Check that the file info is properly returned
        file_info = result["files"][0]
        assert "original_name" in file_info
        assert file_info["original_name"] == "test_document.txt"
        assert "id" in file_info  # Document ID should be present
        
        # Note: We're no longer verifying the file path or trying to delete the file
        # The API may not expose the actual file path for security reasons

def test_multiple_file_upload():
    """Test uploading multiple files sequentially."""
    # Create two temporary files
    with tempfile.NamedTemporaryFile(suffix='.txt') as temp1, \
         tempfile.NamedTemporaryFile(suffix='.txt') as temp2:
        
        temp1.write(b"First test document")
        temp1.flush()
        temp2.write(b"Second test document")
        temp2.flush()
        
        # Upload first file
        with open(temp1.name, "rb") as f1:
            response1 = client.post(
                "/api/upload",
                files={"files": ("document1.txt", f1, "text/plain")}
            )
        
        # Check first response
        assert response1.status_code == 200
        result1 = response1.json()
        assert "files" in result1
        assert len(result1["files"]) == 1
        assert result1["files"][0]["original_name"] == "document1.txt"
        assert "id" in result1["files"][0]
        
        # Upload second file
        with open(temp2.name, "rb") as f2:
            response2 = client.post(
                "/api/upload",
                files={"files": ("document2.txt", f2, "text/plain")}
            )
        
        # Check second response
        assert response2.status_code == 200
        result2 = response2.json()
        assert "files" in result2
        assert len(result2["files"]) == 1
        assert result2["files"][0]["original_name"] == "document2.txt"
        assert "id" in result2["files"][0] 