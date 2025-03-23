"""
RAG (Retrieval-Augmented Generation) plugin for the agent runtime.
This plugin provides functions for searching documents using the RAG API.
"""

import logging
import os
from typing import Any, Dict

import aiohttp
from semantic_kernel.functions.kernel_function_decorator import kernel_function

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger("rag_feature")
logger.setLevel(logging.DEBUG)

DEFAULT_DATA_PATH = "./.data"
DEFAULT_DOCUMENTS_PATH = f"{DEFAULT_DATA_PATH}/documents"
DEFAULT_EMBEDDINGS_PATH = f"{DEFAULT_DATA_PATH}/embeddings"
DEFAULT_RAG_API_URL = "http://localhost:5003"


class RagPlugin:
    """
    A plugin for Retrieval-Augmented Generation (RAG) capabilities.
    Provides document search functions.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.id = "rag-plugin"
        self.name = "RAG Plugin"
        self.description = "Provides doc search for retrieving information from uploaded documents"
        self.rag_api_url = os.environ.get("RAG_API_URL", DEFAULT_RAG_API_URL)
        self._event_queue = None  # Will be set by the agent runtime
        
        logger.info(f"Initialized RAG plugin with API URL: {self.rag_api_url}")

    def _get_event_queue(self, kernel_context=None):
        """Get event queue from either the kernel context or the instance attribute"""
        # First try to get from kernel context
        if kernel_context is not None and hasattr(kernel_context, "variables"):
            event_queue = kernel_context.variables.get("event_queue")
            if event_queue:
                logger.debug("Retrieved event_queue from kernel context")
                return event_queue
                
        # Next, try the instance attribute (set by agent_runtime)
        if self._event_queue:
            logger.debug("Using instance _event_queue attribute")
            return self._event_queue
            
        # Finally, try to extract from kernel_context if it's a dict
        if kernel_context is not None and isinstance(kernel_context, dict):
            event_queue = kernel_context.get("event_queue")
            if event_queue:
                logger.debug("Retrieved event_queue from kernel context dict")
                return event_queue
                
        logger.debug("No event_queue found")
        return None

    @kernel_function(
        description="Search documents for information related to the query.",
        name="search_documents"
    )
    async def search_documents(
        self,
        query: str,
        conversation_id: str,
        top_k: int = 5,
        relevance_threshold: float = 0.5,
        kernel_context=None
    ) -> str:
        """
        Search for relevant chunks in the documents related to 'query'.
        Filters results based on relevance_threshold (0.0-1.0).
        """
        logger.info(f"[RAG] Searching documents with query: '{query}'")
        logger.info(f"[RAG] conversation_id={conversation_id}, top_k={top_k}, relevance_threshold={relevance_threshold}")

        # Best-effort fix for conversation_id placeholders:
        actual_conversation_id = conversation_id
        if actual_conversation_id in [
            "current_conversation", "current_conversation_id", "unique_conversation_id"
        ] and kernel_context and hasattr(kernel_context, "variables"):
            # Try to extract from context
            ctx_conversation_id = kernel_context.variables.get("conversation_id")
            if ctx_conversation_id:
                actual_conversation_id = ctx_conversation_id
                logger.info(f"[RAG] Extracted conversation_id from context: {actual_conversation_id}")

        payload = {
            "query": query,
            "top_k": top_k,
            "relevance_threshold": relevance_threshold
        }
        if actual_conversation_id and actual_conversation_id not in [
            "current_conversation", "current_conversation_id", "unique_conversation_id"
        ]:
            payload["conversation_id"] = actual_conversation_id

        logger.debug(f"[RAG] Payload to RAG API: {payload}")

        # Get event queue for UI updates
        event_queue = self._get_event_queue(kernel_context)
        
        # First, emit a "starting search" event if we have a queue
        if event_queue:
            try:
                await event_queue.put({
                    "rag_retrieval": {
                        "summary": f"Searching documents for '{query}'...",
                        "is_loading": True,
                        "relevance_threshold": relevance_threshold
                    }
                })
            except Exception as e:
                logger.warning(f"[RAG] Failed to emit initial search event: {e}")

        try:
            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.rag_api_url}/rag/query"
                async with session.post(endpoint, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        chunks = result.get("chunks", [])
                        total_chunks_found = result.get("total_chunks_found", 0)
                        document_count = result.get("document_count", 0)

                        if chunks:
                            # Emit rag_retrieval summary event for the UI
                            if event_queue:
                                try:
                                    # First, send a summary of the search results
                                    await event_queue.put({
                                        "rag_retrieval": {
                                            "summary": f"Found {len(chunks)} relevant passages from {document_count} documents",
                                            "document_count": document_count,
                                            "total_chunks": total_chunks_found,
                                            "found_chunks": len(chunks),
                                            "is_loading": False,
                                            "relevance_threshold": relevance_threshold
                                        }
                                    })
                                except Exception as e:
                                    logger.warning(f"[RAG] Failed to emit summary event: {e}")
                            
                            # Format the response for the user
                            response_parts = [
                                f"Here's what I found for query '{query}' (relevance threshold: {relevance_threshold}):"
                            ]
                            
                            # Process each chunk and emit individual chunk events
                            for i, c in enumerate(chunks, 1):
                                doc_text = c.get("text", "").strip()
                                doc_id = c.get("document_id", "unknown")
                                doc_name = c.get("document_name", doc_id)
                                score = c.get("score", 0)
                                
                                # Emit individual chunk event for the UI
                                if event_queue:
                                    try:
                                        await event_queue.put({
                                            "rag_retrieval": {
                                                "document_name": doc_name,
                                                "document_id": doc_id,
                                                "chunk_index": i,
                                                "relevance_score": score,
                                                "content": doc_text[:150] + ("..." if len(doc_text) > 150 else ""),  # Preview
                                                "full_content": doc_text  # Full content
                                            }
                                        })
                                    except Exception as e:
                                        logger.warning(f"[RAG] Failed to emit chunk event: {e}")
                                
                                # Format percentage for display
                                score_percentage = f"{int(score * 100)}%"
                                response_parts.append(
                                    f"\n{i}. (Doc: {doc_name}, relevance: {score_percentage})\n{doc_text}"
                                )
                            
                            response_parts.append(
                                f"\nFound {total_chunks_found} relevant passages total from {document_count} documents."
                            )
                            return "\n".join(response_parts)
                        else:
                            # No relevant chunks - emit an empty result event
                            if event_queue:
                                try:
                                    await event_queue.put({
                                        "rag_retrieval": {
                                            "summary": "No relevant information found",
                                            "document_count": 0,
                                            "total_chunks": 0,
                                            "is_loading": False,
                                            "relevance_threshold": relevance_threshold
                                        }
                                    })
                                except Exception as e:
                                    logger.warning(f"[RAG] Failed to emit empty result event: {e}")
                            return (
                                "No relevant information found for that query. "
                                "Try rephrasing or uploading more documents."
                            )
                    else:
                        error_text = await response.text()
                        # Emit error event
                        if event_queue:
                            try:
                                await event_queue.put({
                                    "rag_retrieval": {
                                        "error": f"Error from RAG API: {response.status} - {error_text}",
                                        "isError": True,
                                        "is_loading": False
                                    }
                                })
                            except Exception as e:
                                logger.warning(f"[RAG] Failed to emit error event: {e}")
                        return f"Error from RAG API: {response.status} - {error_text}"
        except Exception as e:
            logger.exception(f"[RAG] Exception during search: {e}")
            # Emit exception event
            if event_queue:
                try:
                    await event_queue.put({
                        "rag_retrieval": {
                            "error": f"Failed to search documents: {str(e)}",
                            "isError": True,
                            "is_loading": False
                        }
                    })
                except Exception as emit_err:
                    logger.warning(f"[RAG] Failed to emit exception event: {emit_err}")
            return f"Error: failed to search documents: {str(e)}"

    @kernel_function(
        description="List all documents available for the current conversation.",
        name="list_documents"
    )
    async def list_documents(self, conversation_id: str, kernel_context=None) -> str:
        """
        List all documents relevant to the conversation_id.
        """
        logger.info(f"[RAG] Listing documents for conversation_id={conversation_id}")

        # Handle conversation_id placeholders
        actual_conversation_id = conversation_id
        if actual_conversation_id in [
            "current_conversation", "current_conversation_id", "unique_conversation_id"
        ] and kernel_context and hasattr(kernel_context, "variables"):
            # Try to extract from context
            ctx_conversation_id = kernel_context.variables.get("conversation_id")
            if ctx_conversation_id:
                actual_conversation_id = ctx_conversation_id
                logger.info(f"[RAG] Extracted conversation_id from context: {actual_conversation_id}")

        if not actual_conversation_id or actual_conversation_id in [
            "current_conversation", "current_conversation_id", "unique_conversation_id"
        ]:
            return "Error: A valid conversation_id is required."

        try:
            event_queue = self._get_event_queue(kernel_context)
            
            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.rag_api_url}/rag/documents?conversation_id={actual_conversation_id}"
                async with session.get(endpoint) as response:
                    if response.status == 200:
                        result = await response.json()
                        docs = result.get("documents", [])
                        
                        # Emit document list event
                        if event_queue:
                            await event_queue.put({
                                "rag_retrieval": {
                                    "summary": f"Found {len(docs)} documents",
                                    "document_count": len(docs),
                                    "document_list": docs
                                }
                            })
                        
                        if not docs:
                            return "No documents found. Please upload documents first."
                        
                        msg = ["Here are the documents available:\n"]
                        for i, doc in enumerate(docs, 1):
                            fn = doc.get("filename", "Untitled")
                            sid = doc.get("document_id", "unknown")
                            msg.append(f"{i}. {fn} (ID: {sid})")
                        return "\n".join(msg)
                    else:
                        error_text = await response.text()
                        # Emit error event
                        if event_queue:
                            await event_queue.put({
                                "rag_retrieval": {
                                    "error": f"Error from RAG API: {response.status} - {error_text}",
                                    "isError": True
                                }
                            })
                        return f"Error from RAG API: {response.status} - {error_text}"
        except Exception as e:
            logger.exception(f"[RAG] Exception listing documents: {e}")
            # Emit exception event
            if 'event_queue' in locals() and event_queue:
                await event_queue.put({
                    "rag_retrieval": {
                        "error": f"Error listing documents: {str(e)}",
                        "isError": True
                    }
                })
            return f"Error listing documents: {str(e)}"
