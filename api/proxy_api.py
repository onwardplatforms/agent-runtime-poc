#!/usr/bin/env python3

import logging
import os
import json

import aiohttp
import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("api_proxy")
logger.setLevel(logging.INFO)

app = FastAPI(title="API Proxy", version="0.3.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service endpoints
RUNTIME_API_URL = os.environ.get("RUNTIME_API_URL", "http://localhost:5002")
RAG_API_URL = os.environ.get("RAG_API_URL", "http://localhost:5003")

# Root endpoint for API reachability tests
@app.get("/")
async def root():
    """Root endpoint for API reachability tests."""
    return {"status": "ok", "message": "API Proxy is running"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "services": {
        "runtime": RUNTIME_API_URL,
        "rag": RAG_API_URL
    }}

# --------- Runtime API Proxy ---------

@app.api_route("/api/query", methods=["POST"])
async def proxy_query(request: Request):
    """Proxy query to Runtime API."""
    return await proxy_request(f"{RUNTIME_API_URL}/runtime/query", request)

@app.api_route("/api/group-chat", methods=["POST"])
async def proxy_group_chat(request: Request):
    """Proxy group chat to Runtime API."""
    return await proxy_request(f"{RUNTIME_API_URL}/runtime/group-chat", request)

@app.api_route("/api/agents", methods=["GET"])
async def proxy_agents(request: Request):
    """Proxy agents list to Runtime API."""
    return await proxy_request(f"{RUNTIME_API_URL}/runtime/agents", request)

@app.api_route("/api/conversations/{conversation_id}", methods=["GET"])
async def proxy_conversation(conversation_id: str, request: Request):
    """Proxy conversation to Runtime API."""
    return await proxy_request(f"{RUNTIME_API_URL}/runtime/conversations/{conversation_id}", request)

@app.api_route("/api/conversations", methods=["GET", "POST"])
async def proxy_conversations(request: Request):
    """Proxy conversations to Runtime API."""
    return await proxy_request(f"{RUNTIME_API_URL}/runtime/conversations", request)

# --------- RAG API Proxy ---------

@app.api_route("/api/rag/documents", methods=["GET"])
async def proxy_rag_documents(request: Request):
    """Proxy RAG documents to RAG API."""
    return await proxy_request(f"{RAG_API_URL}/rag/documents", request)

@app.api_route("/api/rag/documents", methods=["POST"])
async def proxy_upload_document(request: Request):
    """Proxy document upload to RAG API."""
    return await proxy_request(f"{RAG_API_URL}/rag/documents", request)

@app.api_route("/api/rag/documents/{document_id}", methods=["GET", "DELETE"])
async def proxy_rag_document(document_id: str, request: Request):
    """Proxy specific RAG document operations to RAG API."""
    return await proxy_request(f"{RAG_API_URL}/rag/documents/{document_id}", request)

@app.api_route("/api/rag/search", methods=["POST"])
async def proxy_rag_search(request: Request):
    """Proxy RAG search to RAG API."""
    return await proxy_request(f"{RAG_API_URL}/rag/search", request)

# --------- File Upload Proxy ---------

@app.api_route("/api/upload", methods=["POST"])
async def proxy_upload(request: Request):
    """Proxy file upload to RAG API documents endpoint."""
    logger.info("Proxying file upload to RAG API documents endpoint")
    
    # Special handling for file uploads to ensure field name compatibility
    try:
        # Extract form data from the incoming request
        form_data = await request.form()
        
        # Log more details about the form data
        logger.info(f"Received upload form data with fields: {[k for k in form_data.keys()]}")
        
        # Dump more information about each field
        for k, v in form_data.items():
            logger.info(f"Field: {k}, Type: {type(v)}, Value: {v if not isinstance(v, UploadFile) else f'UploadFile(filename={v.filename}, content_type={v.content_type})'}")
        
        # Create a new FormData for the outgoing request
        outgoing_form = aiohttp.FormData()
        
        # Process each form field
        file_field_found = False
        
        for field_name, field_value in form_data.items():
            logger.info(f"Processing field: {field_name}, type: {type(field_value).__name__}")
            
            # Check if this is a file field - FastAPI uses Starlette's UploadFile
            if hasattr(field_value, 'filename'):
                logger.info(f"Found file field: {field_name} with filename: {field_value.filename}")
                file_field_found = True
                
                # If field is named 'files' (from frontend), rename to 'file' (expected by RAG API)
                target_field_name = 'file' if field_name == 'files' else field_name
                
                # Reset file pointer to beginning
                if hasattr(field_value, 'seek') and callable(field_value.seek):
                    field_value.seek(0)
                
                # Read file content
                file_content = await field_value.read()
                logger.info(f"Read {len(file_content)} bytes from file {field_value.filename}")
                
                # Add to outgoing form with correct field name
                outgoing_form.add_field(
                    target_field_name,
                    file_content,
                    filename=field_value.filename,
                    content_type=field_value.content_type or 'application/octet-stream'
                )
                logger.info(f"Added file field '{target_field_name}' with filename '{field_value.filename}'")
            else:
                # For non-file fields (like conversation_id), pass as is
                outgoing_form.add_field(field_name, str(field_value))
                logger.info(f"Added form field '{field_name}' with value '{field_value}'")
        
        # If still no file field, report error
        if not file_field_found:
            logger.error("No file field found in the request")
            raise HTTPException(status_code=400, detail="No file was received in the upload request")
        
        # Add the required process_async parameter with default value of False
        if 'process_async' not in form_data:
            outgoing_form.add_field('process_async', 'false')
            logger.info("Added default process_async=false parameter")
        
        # Send the request to the RAG API
        target_url = f"{RAG_API_URL}/rag/documents"
        logger.info(f"Sending upload request to {target_url}")
        
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                url=target_url,
                data=outgoing_form
            )
            
            # Process the response
            content = await response.read()
            logger.info(f"Upload response status: {response.status}")
            
            # If successful, transform the response to match what the UI expects
            if response.status == 200 or response.status == 201:
                try:
                    response_text = content.decode('utf-8')
                    logger.info(f"Response text: {response_text}")
                    data = json.loads(response_text)
                    logger.info(f"RAG API response: {data}")
                    
                    # Format the response to match the expected UploadResponse structure
                    formatted_response = {
                        "message": data.get("message", "File uploaded successfully"),
                        "files": [{
                            "id": data.get("document_id", ""),
                            "name": data.get("filename", ""),
                            "size": 0,  # We don't have this information readily available
                            "path": "",  # Not exposed by the API for security
                            "original_name": data.get("filename", ""),
                            "stored_name": data.get("document_id", "")
                        }]
                    }
                    
                    logger.info(f"Formatted response: {formatted_response}")
                    return JSONResponse(content=formatted_response)
                except Exception as e:
                    logger.exception(f"Error formatting response: {e}")
                    # Fall back to original response if there's an error
            
            return Response(
                content=content,
                status_code=response.status,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error handling file upload: {e}")
        raise HTTPException(status_code=500, detail=f"Error handling file upload: {str(e)}")

@app.api_route("/api/upload/{file_id}", methods=["DELETE"])
async def proxy_delete_file(file_id: str, request: Request):
    """Proxy file deletion to RAG API documents endpoint."""
    logger.info(f"Proxying file deletion for file ID: {file_id}")
    return await proxy_request(f"{RAG_API_URL}/rag/documents/{file_id}", request)

# --------- Utility Functions ---------

async def proxy_request(target_url: str, request: Request):
    """
    Generic request proxy function.
    
    This forwards the request to the target URL and returns the response.
    It handles various request methods and content types, including streaming responses.
    """
    method = request.method
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ('host', 'content-length')}
    
    # Get URL parameters
    params = dict(request.query_params)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prepare the request based on method
            if method in ("GET", "DELETE"):
                response = await session.request(
                    method=method,
                    url=target_url,
                    params=params,
                    headers=headers
                )
            else:  # POST, PUT, etc.
                content_type = request.headers.get("content-type", "")
                
                # Handle different content types
                if "multipart/form-data" in content_type:
                    # For file uploads, we need to handle form data
                    form_data = aiohttp.FormData()
                    async for part in request.form():
                        if isinstance(part, UploadFile):
                            form_data.add_field(
                                part.name,
                                await part.read(),
                                filename=part.filename,
                                content_type=part.content_type
                            )
                        else:
                            form_data.add_field(part.name, part.value)
                    
                    response = await session.request(
                        method=method,
                        url=target_url,
                        data=form_data,
                        params=params,
                        headers=headers
                    )
                else:
                    # For JSON requests, just forward the body
                    body = await request.body()
                    response = await session.request(
                        method=method,
                        url=target_url,
                        data=body,
                        params=params,
                        headers=headers
                    )
            
            # Check if it's a streaming response
            if response.headers.get("content-type") == "text/event-stream":
                return StreamingResponse(
                    response.content,
                    media_type="text/event-stream",
                    status_code=response.status
                )
            
            # For regular responses
            content = await response.read()
            return Response(
                content=content,
                status_code=response.status,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
    
    except Exception as e:
        logger.exception(f"Error proxying request to {target_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Error proxying request: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001) 