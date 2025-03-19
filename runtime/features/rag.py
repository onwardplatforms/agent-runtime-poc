"""
RAG (Retrieval-Augmented Generation) plugin for the agent runtime.
This plugin provides functions for searching documents using the RAG API.
"""

import logging
import os
import aiohttp
import json
from typing import Dict, Any, List, Optional
import asyncio

from semantic_kernel.functions.kernel_function_decorator import kernel_function

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger("rag_feature")
logger.setLevel(logging.DEBUG)

# Default RAG API URL
DEFAULT_RAG_API_URL = "http://localhost:5005"


class RagPlugin:
    """
    A plugin for Retrieval-Augmented Generation (RAG) capabilities.
    
    This plugin provides functions for searching documents using the RAG API.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the RAG plugin with configuration.
        
        Args:
            config: Configuration dictionary for the RAG plugin
        """
        self.config = config or {}
        
        # Give it an ID like agents have
        self.id = "rag-plugin"
        self.name = "RAG Plugin"
        self.description = "Provides document search capabilities for retrieving information from uploaded documents"
        
        # Get the RAG API URL from environment or use default
        self.rag_api_url = os.environ.get("RAG_API_URL", DEFAULT_RAG_API_URL)
        
        # Log initialization
        logger.info(f"Initialized RAG plugin with API URL: {self.rag_api_url}")
        
        # Log attributes for debugging
        logger.debug(f"RagPlugin attributes: {dir(self)}")
        logger.debug(f"RagPlugin search_documents method: {getattr(self, 'search_documents', None)}")

    @kernel_function(
        description="Search documents for information related to the query. Use this function when you need to find specific information from uploaded documents.",
        name="search_documents"  # Explicitly name the function like we do with agents
    )
    async def search_documents(
        self,
        query: str,
        conversation_id: str,  # Make this required (no default)
        top_k: int = 5,
        kernel_context = None  # Add parameter to receive kernel context
    ) -> str:
        """
        Search for relevant chunks in the documents related to the query.
        
        Args:
            query: The search query
            conversation_id: The conversation ID (required)
            top_k: Number of top results to return
            kernel_context: The kernel context (contains extension_data)
            
        Returns:
            A string with the search results
        """
        logger.info(f"===== RAG plugin search_documents called with query: '{query}' =====")
        logger.info(f"With params: conversation_id={conversation_id}, top_k={top_k}")
        
        # Fix: Get the real conversation ID from extension_data if available
        actual_conversation_id = conversation_id
        
        # If kernel_context is available and conversation_id is not specified or is a placeholder
        if kernel_context and (not conversation_id or conversation_id in ["current_conversation", "current_conversation_id", "unique_conversation_id"]):
            try:
                # Extract extension_data from context
                if hasattr(kernel_context, 'variables'):
                    # Try to get extension_data directly
                    if 'extension_data' in kernel_context.variables:
                        extension_data_var = kernel_context.variables.get('extension_data')
                        if extension_data_var:
                            # Handle extension_data which could be either a dict or a JSON string
                            try:
                                # Check if extension_data is already a dictionary
                                if isinstance(extension_data_var, dict):
                                    extension_data = extension_data_var
                                else:
                                    # Try to parse it as a JSON string (for backward compatibility)
                                    extension_data = json.loads(extension_data_var)
                                
                                if 'conversation_id' in extension_data:
                                    actual_conversation_id = extension_data['conversation_id']
                                    logger.info(f"Using conversation_id from context extension_data: {actual_conversation_id}")
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(f"Failed to parse extension_data: {e}")
                    # Try to get the conversation_id directly from the kernel context variables
                    elif 'conversation_id' in kernel_context.variables:
                        actual_conversation_id = kernel_context.variables.get('conversation_id')
                        logger.info(f"Using conversation_id directly from context variables: {actual_conversation_id}")
                
                # Log all available variables in the context for debugging
                if hasattr(kernel_context, 'variables'):
                    logger.debug(f"All available variables in kernel context: {list(kernel_context.variables.keys())}")
            except Exception as e:
                logger.error(f"Error extracting conversation_id from context: {e}")
                
            # IMPORTANT: If we still have a placeholder or no conversation_id, try one more approach
            # Look for the conversation_id in the global kernel variables (not just the function context)
            if not actual_conversation_id or actual_conversation_id in ["current_conversation", "current_conversation_id", "unique_conversation_id"]:
                try:
                    import inspect
                    # Try to get the kernel from the calling context
                    frame = inspect.currentframe()
                    while frame:
                        if 'self' in frame.f_locals and hasattr(frame.f_locals['self'], 'kernel'):
                            kernel = frame.f_locals['self'].kernel
                            if hasattr(kernel, 'variables') and 'conversation_id' in kernel.variables:
                                actual_conversation_id = kernel.variables.get('conversation_id')
                                logger.info(f"Found conversation_id in kernel globals: {actual_conversation_id}")
                                break
                        frame = frame.f_back
                except Exception as e:
                    logger.warning(f"Failed to extract kernel globals: {e}")
        
        # Check if we need to log a warning about conversation_id
        if not actual_conversation_id:
            logger.warning("No conversation_id provided - document search may return global results instead of conversation-specific results")
        elif actual_conversation_id in ["current_conversation", "current_conversation_id", "unique_conversation_id"]:
            logger.warning(f"Using placeholder conversation_id: {actual_conversation_id}. This may not return the correct documents.")
        
        # Prepare the search query payload
        payload = {
            "query": query,
            "top_k": top_k
        }
        
        if actual_conversation_id and actual_conversation_id not in ["current_conversation", "current_conversation_id", "unique_conversation_id"]:
            payload["conversation_id"] = actual_conversation_id
            
        logger.info(f"Sending search query to RAG API: {payload}")
        
        try:
            # Check if we have an event handler before starting
            event_handler = None
            if kernel_context is not None:
                # First check if event_queue exists directly on the context
                if hasattr(kernel_context, 'event_queue') and kernel_context.event_queue is not None:
                    event_handler = kernel_context.event_queue
                # Then check if self.kernel.event_queue exists
                elif hasattr(kernel_context, 'kernel') and hasattr(kernel_context.kernel, 'event_queue') and kernel_context.kernel.event_queue is not None:
                    event_handler = kernel_context.kernel.event_queue
                # Next check if the parent object has an event_queue
                elif hasattr(kernel_context, '_parent') and hasattr(kernel_context._parent, 'event_queue') and kernel_context._parent.event_queue is not None:
                    event_handler = kernel_context._parent.event_queue
                    
            # Call the RAG API to search for documents
            logger.info(f"Connecting to RAG API at {self.rag_api_url}")
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Created aiohttp session, making POST request to {self.rag_api_url}/rag/query")
                endpoint = f"{self.rag_api_url}/rag/query"
                logger.info(f"Full endpoint URL: {endpoint}")
                
                async with session.post(endpoint, json=payload) as response:
                    logger.info(f"RAG API response received: status code {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        chunks = result.get("chunks", [])
                        total_chunks_found = result.get("total_chunks_found", 0)
                        
                        logger.info(f"Request successful: Found {total_chunks_found} chunks, returning top {len(chunks)}")
                        
                        if chunks:
                            # Emit a summary event if we have an event handler
                            if event_handler:
                                logger.info(f"Emitting RAG retrieval summary event for {len(chunks)} chunks")
                                await event_handler.put({
                                    "rag_retrieval": {
                                        "summary": f"Found {len(chunks)} relevant passages in {len(set(chunk.get('document_id') for chunk in chunks))} documents for query: '{query}'",
                                        "total_chunks": total_chunks_found,
                                        "document_count": len(set(chunk.get('document_id') for chunk in chunks))
                                    }
                                })
                                
                                # Emit an event for each chunk
                                for i, chunk in enumerate(chunks, 1):
                                    chunk_text = chunk.get("text", "").strip()
                                    document_id = chunk.get("document_id", "unknown")
                                    score = chunk.get("score", 0)
                                    metadata = chunk.get("metadata", {})
                                    source = metadata.get("filename", document_id)
                                    
                                    logger.info(f"Emitting RAG retrieval event for chunk {i} from {source}")
                                    await event_handler.put({
                                        "rag_retrieval": {
                                            "document_name": source,
                                            "document_id": document_id,
                                            "chunk_index": i,
                                            "relevance_score": score,
                                            "content": chunk_text[:200] + ("..." if len(chunk_text) > 200 else ""),
                                            "full_content": chunk_text
                                        }
                                    })
                                    # Small sleep to allow events to be processed
                                    await asyncio.sleep(0.01)
                            
                            # Format the response with the found chunks
                            response_parts = [f"Here's what I found in the documents for the query '{query}':"]
                            
                            for i, chunk in enumerate(chunks, 1):
                                chunk_text = chunk.get("text", "").strip()
                                document_id = chunk.get("document_id", "unknown")
                                score = chunk.get("score", 0)
                                metadata = chunk.get("metadata", {})
                                source = metadata.get("filename", document_id)
                                
                                logger.debug(f"Chunk {i}: score={score:.3f}, doc={document_id}, file={source}")
                                logger.debug(f"Chunk text: {chunk_text[:100]}...")
                                
                                response_parts.append(f"\n{i}. From {source} (relevance: {score:.3f}):")
                                response_parts.append(f"{chunk_text}")
                            
                            response_parts.append(f"\nFound {total_chunks_found} relevant passages in the documents.")
                            
                            response_text = "\n".join(response_parts)
                            logger.info(f"===== RAG search completed: returning {len(chunks)} chunks =====")
                            return response_text
                        else:
                            # Emit a "no results" event if we have an event handler
                            if event_handler:
                                logger.info("Emitting RAG retrieval event for no results")
                                # First check if there are any documents
                                logger.info("Making GET request to check document status")
                                async with session.get(f"{self.rag_api_url}/rag/documents") as doc_response:
                                    doc_status = doc_response.status
                                    if doc_status == 200:
                                        doc_result = await doc_response.json()
                                        documents = doc_result.get("documents", [])
                                        if documents:
                                            await event_handler.put({
                                                "rag_retrieval": {
                                                    "summary": f"No relevant information found for the query: '{query}'",
                                                    "document_count": len(documents),
                                                    "total_chunks": 0
                                                }
                                            })
                                        else:
                                            await event_handler.put({
                                                "rag_retrieval": {
                                                    "error": "No documents have been uploaded yet. Please upload some documents first."
                                                }
                                            })
                            
                            # Check if there are any documents in the first place
                            logger.info("Making GET request to check document status")
                            async with session.get(f"{self.rag_api_url}/rag/documents") as doc_response:
                                doc_status = doc_response.status
                                logger.info(f"Document check response status: {doc_status}")
                                
                                if doc_status == 200:
                                    doc_result = await doc_response.json()
                                    documents = doc_result.get("documents", [])
                                    
                                    logger.info(f"Document check: found {len(documents)} documents")
                                    if documents:
                                        for i, doc in enumerate(documents[:3]):  # Log the first 3 docs
                                            logger.info(f"Document {i+1}: {doc.get('document_id')} - {doc.get('filename')} ({doc.get('status')})")
                                        
                                        response = f"No relevant information found in the documents for the query '{query}'. Please try a different query."
                                        logger.info(f"===== RAG search completed: no relevant chunks in {len(documents)} documents =====")
                                        return response
                                    else:
                                        logger.warning("No documents found in the system")
                                        response = "No documents have been uploaded yet. Please upload some documents first."
                                        logger.info(f"===== RAG search completed: no documents available =====")
                                        return response
                                else:
                                    doc_content = await doc_response.text()
                                    logger.error(f"Failed to check documents: Status {doc_status} - {doc_content}")
                                    response = f"No relevant information found for the query '{query}'. The document service might be unavailable."
                                    logger.info(f"===== RAG search completed: document service error =====")
                                    return response
                    else:
                        error_text = await response.text()
                        logger.error(f"RAG API search failed: {response.status} - {error_text}")
                        response = f"Error: Failed to search documents. Status code: {response.status}."
                        logger.info(f"===== RAG search failed with error =====")
                        return response
        except Exception as e:
            logger.exception(f"Exception during document search: {e}")
            return f"Error: Failed to search documents due to an exception: {str(e)}"

    @kernel_function(
        description="List all documents available for the current conversation. Use this function to see what documents are available for search.",
        name="list_documents"
    )
    async def list_documents(
        self, 
        conversation_id: str,  # Required parameter
        kernel_context = None  # Add parameter to receive kernel context
    ) -> str:
        """
        List all documents available for the conversation.
        
        Args:
            conversation_id: The conversation ID (required)
            kernel_context: The kernel context (contains extension_data)
            
        Returns:
            A string with the list of documents
        """
        logger.info(f"===== RAG plugin list_documents called =====")
        logger.info(f"With params: conversation_id={conversation_id}")
        
        # Fix: Get the real conversation ID from extension_data if available
        actual_conversation_id = conversation_id
        
        # If kernel_context is available and conversation_id is not specified or is a placeholder
        if kernel_context and (not conversation_id or conversation_id in ["current_conversation", "current_conversation_id", "unique_conversation_id"]):
            try:
                # Extract extension_data from context
                if hasattr(kernel_context, 'variables'):
                    # Try to get extension_data directly
                    if 'extension_data' in kernel_context.variables:
                        extension_data_var = kernel_context.variables.get('extension_data')
                        if extension_data_var:
                            # Handle extension_data which could be either a dict or a JSON string
                            try:
                                # Check if extension_data is already a dictionary
                                if isinstance(extension_data_var, dict):
                                    extension_data = extension_data_var
                                else:
                                    # Try to parse it as a JSON string (for backward compatibility)
                                    extension_data = json.loads(extension_data_var)
                                
                                if 'conversation_id' in extension_data:
                                    actual_conversation_id = extension_data['conversation_id']
                                    logger.info(f"Using conversation_id from context extension_data: {actual_conversation_id}")
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(f"Failed to parse extension_data: {e}")
                    # Try to get the conversation_id directly from the kernel context variables
                    elif 'conversation_id' in kernel_context.variables:
                        actual_conversation_id = kernel_context.variables.get('conversation_id')
                        logger.info(f"Using conversation_id directly from context variables: {actual_conversation_id}")
            except Exception as e:
                logger.warning(f"Error extracting conversation_id from context: {e}")
        
        # Check if we need to log a warning about conversation_id
        if not actual_conversation_id:
            logger.warning("No conversation_id provided - document listing may return global results instead of conversation-specific results")
            return "Error: A conversation ID is required to list documents. Please provide a valid conversation ID."
        elif actual_conversation_id in ["current_conversation", "current_conversation_id", "unique_conversation_id"]:
            logger.warning(f"Using placeholder conversation_id: {actual_conversation_id}. This may not return the correct documents.")
            return "Error: A valid conversation ID is required, not a placeholder. Please provide a specific conversation ID."
            
        logger.info(f"Listing documents for conversation_id: {actual_conversation_id}")
        
        try:
            # Call the RAG API to list documents
            logger.info(f"Connecting to RAG API at {self.rag_api_url}")
            
            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.rag_api_url}/rag/documents"
                
                # Add conversation_id as query parameter if provided
                if actual_conversation_id:
                    endpoint += f"?conversation_id={actual_conversation_id}"
                
                logger.info(f"Making GET request to: {endpoint}")
                
                async with session.get(endpoint) as response:
                    logger.info(f"RAG API response received: status code {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        documents = result.get("documents", [])
                        
                        logger.info(f"Found {len(documents)} documents")
                        
                        if documents:
                            # Format the response with the found documents
                            response_parts = [f"Here are the documents available for this conversation:"]
                            
                            for i, doc in enumerate(documents, 1):
                                filename = doc.get("filename", "Unknown document")
                                doc_id = doc.get("document_id", "unknown")
                                file_size = doc.get("file_size", 0)
                                file_size_str = f"{file_size / 1024:.1f} KB" if file_size else "Unknown size"
                                chunk_count = doc.get("chunk_count", 0)
                                status = doc.get("status", "Unknown status")
                                
                                response_parts.append(f"\n{i}. {filename} ({file_size_str}, {chunk_count} chunks, Status: {status})")
                            
                            response_text = "\n".join(response_parts)
                            logger.info(f"===== Document listing completed: returning {len(documents)} documents =====")
                            return response_text
                        else:
                            return "No documents found for this conversation. Please upload documents to use document search functionality."
                    else:
                        error_text = await response.text()
                        logger.error(f"RAG API error: {response.status} - {error_text}")
                        return f"Error retrieving documents: {response.status}. Please try again or check if the RAG API is available."
        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return f"Error listing documents: {str(e)}" 