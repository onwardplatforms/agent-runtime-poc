#!/usr/bin/env python3

import asyncio
import datetime
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

import shutil
from pathlib import Path

from runtime.agent_runtime import AgentGroupChat, AgentRuntime, AgentTerminationStrategy

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Change from ERROR to INFO for more verbose logging
)
logger = logging.getLogger("runtime_api")
logger.setLevel(logging.INFO)  # Set to INFO for more detailed logs

app = FastAPI(title="Agent Runtime API", version="0.3.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response


class Query(BaseModel):
    query: str
    user_id: str = "user"
    conversation_id: Optional[str] = None
    verbose: bool = False
    max_agents: Optional[int] = None
    stream: bool = False


class GroupChatQuery(BaseModel):
    query: str
    user_id: str = "user"
    conversation_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    max_iterations: int = 5
    verbose: bool = False
    stream: bool = False


class Message(BaseModel):
    messageId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversationId: str
    senderId: str
    recipientId: str
    content: str
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    type: Any = "Text"
    execution_trace: Optional[List[Any]] = None
    agents_used: Optional[List[str]] = None


class Agent(BaseModel):
    id: str
    name: str
    description: str
    capabilities: List[str]
    endpoint: str


class Conversation(BaseModel):
    id: str
    messages: List[Dict[str, Any]]


# Singleton runtime instance
_runtime_instance: Optional[AgentRuntime] = None


async def get_runtime():
    """Get or create the AgentRuntime instance."""
    global _runtime_instance
    if _runtime_instance is None:
        _runtime_instance = AgentRuntime()
        # Short delay to allow kernel initialization
        await asyncio.sleep(1)
    return _runtime_instance


# Get storage path from configuration
def get_documents_dir() -> Path:
    """Get the documents directory from the configuration."""
    try:
        with open("runtime/agents.json", "r") as f:
            config = json.load(f)
        
        # Get the documents path from the config
        documents_path = config.get("settings", {}).get("data", {}).get("rag", {}).get("local_storage", {}).get("documents_path", "./.data/documents")
        path = Path(documents_path)
        
        # Create the directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured documents directory exists: {path}")
        
        return path
    except Exception as e:
        logger.warning(f"Error loading configuration or creating directory: {e}")
        # Fall back to default path
        default_path = Path("./.data/documents")
        default_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created default documents directory: {default_path}")
        return default_path


# Get and ensure the documents directory exists
DOCUMENTS_DIR = get_documents_dir()
logger.info(f"Using documents directory: {DOCUMENTS_DIR}")


# Define RAG API URL
RAG_API_URL = "http://localhost:5005"


@app.post("/api/query")
async def process_query(query: Query, runtime: AgentRuntime = Depends(get_runtime)):
    """Process a query using the agent runtime."""
    logger.info(f"Received query: {query.query}")

    try:
        # Check if streaming is requested or enabled globally
        use_streaming = query.stream or runtime.enable_streaming

        if use_streaming:
            logger.debug("Streaming response requested")
            return StreamingResponse(
                stream_query_response(query, runtime),
                media_type="text/event-stream"
            )

        result = await runtime.process_query(
            query=query.query,
            conversation_id=query.conversation_id,
            verbose=query.verbose,
            max_agents=query.max_agents
        )

        # The result is already a Message object, so we can return it directly
        logger.debug(f"Query processed successfully: {result.get('content', '')[:50]}...")
        return result
    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def stream_query_response(query: Query, runtime: AgentRuntime):
    """Stream the response to a query."""
    logger.info(f"Starting streaming response for query: {query.query}")

    try:
        # Send an initial message to confirm streaming has started
        logger.debug("Sending initial streaming message")
        yield f"data: {json.dumps({'chunk': 'Starting streaming response...', 'complete': False})}\n\n"

        # Log the streaming process
        logger.debug(f"Starting stream_process_query with conversation_id: {query.conversation_id}")

        # Create a counter for chunks
        chunk_counter = 0

        # Set response flush interval to ensure real-time updates
        flush_interval = 0.05  # 50ms
        last_flush_time = time.time()

        async for chunk in runtime.stream_process_query(
            query=query.query,
            conversation_id=query.conversation_id,
            verbose=query.verbose
        ):
            chunk_counter += 1
            logger.debug(f"Streaming chunk #{chunk_counter}: {chunk if isinstance(chunk, str) else str(chunk)[:100]}...")

            # Format and send the chunk
            if isinstance(chunk, str):
                # If it's a string, wrap it in a content object
                logger.debug(f"Yielding string chunk #{chunk_counter}")
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            else:
                # If it's an object, send it as is
                logger.debug(f"Yielding object chunk #{chunk_counter}")
                yield f"data: {json.dumps(chunk)}\n\n"

            # Flush data more frequently for agent calls/responses
            current_time = time.time()
            if 'agent_call' in chunk or 'agent_response' in chunk or (current_time - last_flush_time > flush_interval):
                await asyncio.sleep(0)  # Yield control to ensure data is flushed
                last_flush_time = current_time

        # Send a final message to confirm streaming is complete
        logger.debug("Sending streaming complete message")
        yield f"data: {json.dumps({'chunk': 'Streaming complete', 'complete': True})}\n\n"

        logger.debug("Sending [DONE] marker")
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.exception(f"Error streaming response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/api/group-chat")
async def group_chat(query: GroupChatQuery, runtime: AgentRuntime = Depends(get_runtime)):
    """Process a user query using a group chat of agents."""
    try:
        # Check if streaming is requested or enabled globally
        use_streaming = query.stream or runtime.enable_streaming

        if use_streaming:
            logger.debug("Streaming group chat response requested")
            return StreamingResponse(
                stream_group_chat_response(query, runtime),
                media_type="text/event-stream"
            )

        # Create a group chat with specified agents
        group_chat = AgentGroupChat(
            agents=[runtime.get_agent_by_id(agent_id) for agent_id in query.agent_ids
                    if runtime.get_agent_by_id(agent_id) is not None]
            if query.agent_ids else list(runtime.get_all_agents().values()),
            termination_strategy=AgentTerminationStrategy(max_iterations=query.max_iterations)
        )

        # Process the query through the group chat
        response = await group_chat.process_query(
            query.query,
            user_id=query.user_id,
            conversation_id=query.conversation_id,
            verbose=query.verbose
        )

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing group chat: {str(e)}")


async def stream_group_chat_response(query: GroupChatQuery, runtime: AgentRuntime):
    """Stream the response to a group chat query."""
    logger.debug(f"Starting streaming group chat response for query: {query.query}")

    try:
        # Initialize response with default values to avoid the variable reference error
        response = {"content": "", "agents_used": []}
        
        # Send an initial message to confirm streaming has started
        yield f"data: {json.dumps({'chunk': 'Starting group chat streaming response...', 'complete': False})}\n\n"

        # Create a group chat with specified agents
        group_chat = AgentGroupChat(
            agents=[runtime.get_agent_by_id(agent_id) for agent_id in query.agent_ids
                    if runtime.get_agent_by_id(agent_id) is not None]
            if query.agent_ids else list(runtime.get_all_agents().values()),
            termination_strategy=AgentTerminationStrategy(max_iterations=query.max_iterations)
        )

        # Set up event queue for the group chat
        # This is a temporary approach until the group chat is fully integrated with streaming
        runtime.event_queue = asyncio.Queue()

        # Set event queue on agents temporarily
        for agent in runtime.agents.values():
            agent._event_queue = runtime.event_queue

        # Set response flush interval to ensure real-time updates
        flush_interval = 0.05  # 50ms
        last_flush_time = time.time()

        # Process the query through the group chat (in background task)
        process_task = asyncio.create_task(group_chat.process_query(
            query.query,
            user_id=query.user_id,
            conversation_id=query.conversation_id,
            verbose=query.verbose
        ))

        # Process events as they come in
        while not process_task.done() or not runtime.event_queue.empty():
            try:
                # Try to get an event from the queue
                event = await asyncio.wait_for(runtime.event_queue.get(), 0.1)
                logger.debug(f"Got event from queue: {event}")

                # Send the event to the client
                yield f"data: {json.dumps(event)}\n\n"
                runtime.event_queue.task_done()

                # Flush data more frequently for agent calls/responses
                current_time = time.time()
                if 'agent_call' in event or 'agent_response' in event or (current_time - last_flush_time > flush_interval):
                    await asyncio.sleep(0)  # Yield control to ensure data is flushed
                    last_flush_time = current_time
            except asyncio.TimeoutError:
                # No event available, check if process task is done
                if process_task.done():
                    try:
                        # Get the result
                        response = process_task.result()
                        logger.debug(f"Process task completed with response: {response}")
                    except Exception as e:
                        logger.exception(f"Error getting process task result: {e}")
                        response = {"content": f"Error: {str(e)}", "agents_used": []}
                    break

        # Cleanup
        for agent in runtime.agents.values():
            agent._event_queue = None

        # Stream the final response content
        if response and "content" in response:
            yield f"data: {json.dumps({'content': response['content']})}\n\n"

        # Send the complete response
        yield f"data: {json.dumps({'chunk': None, 'complete': True, 'response': response.get('content', ''), 'agents_used': response.get('agents_used', [])})}\n\n"

        # Send a final message to confirm streaming is complete
        yield f"data: {json.dumps({'chunk': 'Group chat streaming complete', 'complete': True})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.exception(f"Error streaming group chat response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, runtime: AgentRuntime = Depends(get_runtime)):
    """Get the conversation history for a specific conversation."""
    try:
        history = runtime.get_conversation_history(conversation_id)

        if not history:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

        return {
            "id": conversation_id,
            "messages": history
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation: {str(e)}")


@app.get("/api/agents")
async def list_agents(runtime: AgentRuntime = Depends(get_runtime)):
    """List all available agents and their capabilities."""
    try:
        agents = runtime.get_all_agents()
        result = []

        for agent_id, agent in agents.items():
            result.append({
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "capabilities": agent.capabilities,
                "conversation_starters": agent.conversation_starters,
                "endpoint": agent.endpoint
            })

        return {"agents": result}
    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint providing API information."""
    return {
        "name": "Agent Runtime API",
        "version": "0.3.0",
        "description": "An API for orchestrating interactions between agents using Semantic Kernel",
        "endpoints": [
            {"path": "/api/query", "method": "POST", "description": "Process a user query"},
            {"path": "/api/group-chat", "method": "POST", "description": "Process a query using a group chat of agents"},
            {"path": "/api/conversations/{conversation_id}", "method": "GET", "description": "Get conversation history"},
            {"path": "/api/agents", "method": "GET", "description": "List available agents"}
        ]
    }


@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    conversation_id: str = Form(None)
):
    """
    Upload files for RAG processing.
    
    Files are organized by conversation ID if provided, otherwise stored in the root documents directory.
    Original filenames are preserved with a UUID prefix to avoid collisions.
    Files are also forwarded to the RAG API for processing.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
            
        # Create a conversation-specific directory if conversation_id is provided
        target_dir = DOCUMENTS_DIR
        if conversation_id:
            target_dir = DOCUMENTS_DIR / conversation_id
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created/ensured conversation directory: {target_dir}")
            except Exception as e:
                logger.error(f"Failed to create conversation directory {target_dir}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to create upload directory: {str(e)}")
            
        logger.info(f"Uploading files to: {target_dir}")
        
        # Load existing metadata if it exists
        metadata_path = target_dir / "metadata.json"
        metadata = {"files": {}}
        if metadata_path.exists():
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    if not isinstance(metadata.get("files"), dict):
                        metadata["files"] = {}
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in metadata file: {metadata_path}, starting fresh")
            except Exception as e:
                logger.warning(f"Error reading metadata file: {e}, starting fresh")
        
        uploaded_files = []
        
        # Process each uploaded file
        for file in files:
            try:
                # Get original filename and file extension
                original_filename = file.filename
                if not original_filename:
                    logger.warning("File has no filename, using 'unnamed_file'")
                    original_filename = "unnamed_file"
                    
                # Create a unique ID for this file
                file_id = str(uuid.uuid4())
                
                # Use a safe version of the original filename
                safe_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in original_filename)
                
                # Create full path with file_id to avoid collisions
                stored_filename = f"{file_id}-{safe_filename}"
                file_path = target_dir / stored_filename
                
                # Save file to disk
                try:
                    file_content = await file.read()
                    with open(file_path, "wb") as f:
                        f.write(file_content)
                except IOError as e:
                    logger.error(f"I/O error saving file: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"I/O error saving file: {str(e)}")
                
                # Reset file object position for later reuse
                await file.seek(0)
                
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Relative path for storage
                try:
                    rel_path = str(file_path.relative_to(Path(".")))
                except ValueError:
                    # If we can't get a relative path, use absolute
                    rel_path = str(file_path)
                
                # Create response object with file details
                file_info = {
                    "id": file_id,
                    "name": original_filename,
                    "size": file_size,
                    "path": rel_path,
                    "original_name": original_filename,
                    "stored_name": stored_filename,
                    "conversation_id": conversation_id,
                    "upload_time": datetime.datetime.now().isoformat()
                }
                
                # Forward the file to the RAG API for processing
                try:
                    # Create a new FormData for the RAG API
                    rag_form = aiohttp.FormData()
                    rag_form.add_field('file', 
                                       file_content,
                                       filename=original_filename,
                                       content_type=file.content_type)
                    
                    if conversation_id:
                        rag_form.add_field('conversation_id', conversation_id)
                    
                    # Process synchronously for immediate indexing
                    rag_form.add_field('process_async', 'false')
                    
                    # Send the file to the RAG API
                    async with aiohttp.ClientSession() as session:
                        rag_response = await session.post(
                            f"{RAG_API_URL}/rag/documents",
                            data=rag_form
                        )
                        
                        if rag_response.status != 200:
                            rag_error = await rag_response.text()
                            logger.error(f"RAG API error: {rag_response.status} - {rag_error}")
                            # Continue despite RAG processing error
                        else:
                            rag_data = await rag_response.json()
                            rag_document_id = rag_data.get("document_id")
                            logger.info(f"RAG API processing successful for {original_filename}, document ID: {rag_document_id}")
                            
                            # Store the RAG document ID for future reference
                            file_info["rag_document_id"] = rag_document_id
                            
                except Exception as rag_error:
                    logger.error(f"Error forwarding file to RAG API: {str(rag_error)}")
                    # Continue despite RAG processing error
                
                # Add file info to metadata
                metadata["files"][file_id] = file_info
                
                # Save updated metadata
                try:
                    with open(metadata_path, "w") as f:
                        json.dump(metadata, f, indent=2)
                    logger.info(f"Updated metadata file with new file: {file_id}")
                except Exception as e:
                    logger.error(f"Error saving metadata file: {e}")
                
                uploaded_files.append(file_info)
                
                logger.info(f"File uploaded: {original_filename} -> {file_path} ({file_size} bytes)")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                # Continue with other files
        
        if not uploaded_files:
            return {"message": "No files were successfully uploaded", "files": []}
        
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "files": uploaded_files
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading files: {str(e)}")


@app.delete("/api/upload/{file_id}")
async def delete_file(file_id: str, conversation_id: str = None):
    """
    Delete a file by its stored file ID.
    
    If conversation_id is provided, looks in that specific directory.
    Otherwise, searches through all conversation directories.
    Also deletes the file from the RAG API using the RAG document ID stored in metadata.
    """
    try:
        if not file_id:
            raise HTTPException(status_code=400, detail="No file ID provided")
        
        file_found = False
        rag_document_id = None
        file_path_found = None
        metadata_updated = False
        conversation_dir = None
        
        # Find the file and directory
        if conversation_id:
            # If conversation_id is provided, look only in that directory
            target_dir = DOCUMENTS_DIR / conversation_id
            conversation_dir = target_dir
            if target_dir.exists():
                # Try to get metadata first
                metadata_path = target_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                            if metadata.get("files") and file_id in metadata["files"]:
                                file_info = metadata["files"][file_id]
                                rag_document_id = file_info.get("rag_document_id")
                                stored_name = file_info.get("stored_name")
                                if stored_name:
                                    file_path_found = target_dir / stored_name
                                    file_found = True
                                    logger.info(f"Found file {file_path_found} from metadata")
                    except Exception as e:
                        logger.warning(f"Error reading metadata file: {e}")
                
                # If metadata didn't work, try direct file search
                if not file_found:
                    for file_path in target_dir.glob(f"{file_id}-*"):
                        file_path_found = file_path
                        file_found = True
                        logger.info(f"Found file {file_path} from conversation {conversation_id}")
                        break
        else:
            # Otherwise search through all conversation directories
            for conv_dir in DOCUMENTS_DIR.glob("*"):
                if conv_dir.is_dir():
                    metadata_path = conv_dir / "metadata.json"
                    if metadata_path.exists():
                        try:
                            with open(metadata_path, "r") as f:
                                metadata = json.load(f)
                                if metadata.get("files") and file_id in metadata["files"]:
                                    file_info = metadata["files"][file_id]
                                    rag_document_id = file_info.get("rag_document_id")
                                    stored_name = file_info.get("stored_name")
                                    if stored_name:
                                        file_path_found = conv_dir / stored_name
                                        file_found = True
                                        conversation_dir = conv_dir
                                        logger.info(f"Found file {file_path_found} from metadata in {conv_dir}")
                                        break
                        except Exception as e:
                            logger.warning(f"Error reading metadata file in {conv_dir}: {e}")
            
            # If metadata search failed, try direct file search
            if not file_found:
                for file_path in DOCUMENTS_DIR.glob(f"**/{file_id}-*"):
                    file_path_found = file_path
                    conversation_dir = file_path.parent
                    file_found = True
                    logger.info(f"Found file {file_path}")
                    break
        
        # Try to get the RAG document ID from metadata if we didn't find it yet
        if file_found and not rag_document_id and conversation_dir:
            metadata_path = conversation_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                        if metadata.get("files") and file_id in metadata["files"]:
                            file_info = metadata["files"][file_id]
                            rag_document_id = file_info.get("rag_document_id")
                            logger.info(f"Found RAG document ID from metadata: {rag_document_id}")
                except Exception as e:
                    logger.warning(f"Error reading metadata file: {e}")
        
        # Delete the file if found
        if file_found and file_path_found and file_path_found.exists():
            file_path_found.unlink()
            logger.info(f"Deleted file {file_path_found}")
            
            # Update metadata to reflect deletion
            if conversation_dir:
                metadata_path = conversation_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                            if metadata.get("files") and file_id in metadata["files"]:
                                # Remove the file entry completely instead of just marking it as deleted
                                del metadata["files"][file_id]
                                
                                # Write updated metadata
                                with open(metadata_path, "w") as f:
                                    json.dump(metadata, f, indent=2)
                                metadata_updated = True
                                logger.info(f"Removed file {file_id} from metadata")
                    except Exception as e:
                        logger.warning(f"Error updating metadata file after deletion: {e}")
                
        # If we don't have a RAG document ID yet, use the file_id as a fallback
        if not rag_document_id:
            rag_document_id = file_id
            logger.info(f"Using file ID as RAG document ID fallback: {rag_document_id}")
                
        # Also delete from RAG API
        try:
            # Build the RAG API URL using the rag_document_id
            rag_url = f"{RAG_API_URL}/rag/documents/{rag_document_id}"
            if conversation_id:
                rag_url += f"?conversation_id={conversation_id}"
                
            # Send delete request to RAG API
            async with aiohttp.ClientSession() as session:
                rag_response = await session.delete(rag_url)
                
                if rag_response.status == 200:
                    rag_data = await rag_response.json()
                    logger.info(f"RAG API deletion successful: {rag_data.get('message', 'No message')}")
                elif rag_response.status != 404:  # Ignore 404 errors (file not found)
                    rag_error = await rag_response.text()
                    logger.error(f"RAG API error during deletion: {rag_response.status} - {rag_error}")
        except Exception as rag_error:
            logger.error(f"Error deleting file from RAG API: {str(rag_error)}")
            # Continue despite RAG deletion error
                
        if not file_found:
            return {"success": True, "message": "File not found, it may have been already deleted"}
            
        return {"success": True, "message": "File deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


if __name__ == "__main__":
    # Start the server
    print("Starting Agent Runtime API")
    uvicorn.run(app, host="0.0.0.0", port=5003, log_level="warning")
