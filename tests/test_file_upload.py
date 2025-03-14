import os
import pytest
import tempfile
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from api.runtime_api import app, DOCUMENTS_DIR

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
        assert "path" in file_info
        
        # Verify the file was saved
        stored_path = Path(file_info["path"])
        assert stored_path.exists()
        
        # Clean up the test file
        if stored_path.exists():
            os.remove(stored_path)

def test_multiple_file_upload():
    """Test uploading multiple files simultaneously."""
    # Create two temporary files
    with tempfile.NamedTemporaryFile(suffix='.txt') as temp1, \
         tempfile.NamedTemporaryFile(suffix='.txt') as temp2:
        
        temp1.write(b"First test document")
        temp1.flush()
        temp2.write(b"Second test document")
        temp2.flush()
        
        # Upload both files
        with open(temp1.name, "rb") as f1, open(temp2.name, "rb") as f2:
            response = client.post(
                "/api/upload",
                files=[
                    ("files", ("document1.txt", f1, "text/plain")),
                    ("files", ("document2.txt", f2, "text/plain"))
                ]
            )
        
        # Check the response
        assert response.status_code == 200
        result = response.json()
        assert len(result["files"]) == 2
        
        # Verify both files and clean up
        for file_info in result["files"]:
            stored_path = Path(file_info["path"])
            assert stored_path.exists()
            
            # Clean up
            if stored_path.exists():
                os.remove(stored_path) 