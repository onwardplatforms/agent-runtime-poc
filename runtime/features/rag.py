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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger("rag_feature")
logger.setLevel(logging.DEBUG)

DEFAULT_RAG_API_URL = "http://localhost:5005"


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

        logger.info(f"Initialized RAG plugin with API URL: {self.rag_api_url}")

    @kernel_function(
        description="Search documents for information related to the query.",
        name="search_documents"
    )
    async def search_documents(
        self,
        query: str,
        conversation_id: str,
        top_k: int = 5,
        kernel_context=None
    ) -> str:
        """
        Search for relevant chunks in the documents related to 'query'.
        """
        logger.info(f"[RAG] Searching documents with query: '{query}'")
        logger.info(f"[RAG] conversation_id={conversation_id}, top_k={top_k}")

        # Best-effort fix for conversation_id placeholders:
        actual_conversation_id = conversation_id
        # ... (the existing logic that tries to fix placeholder IDs, omitted for brevity)

        payload = {
            "query": query,
            "top_k": top_k
        }
        if actual_conversation_id and actual_conversation_id not in [
            "current_conversation", "current_conversation_id", "unique_conversation_id"
        ]:
            payload["conversation_id"] = actual_conversation_id

        logger.debug(f"[RAG] Payload to RAG API: {payload}")

        try:
            event_handler = None
            if kernel_context is not None:
                # (existing event handling logic)
                pass

            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.rag_api_url}/rag/query"
                async with session.post(endpoint, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        chunks = result.get("chunks", [])
                        total_chunks_found = result.get("total_chunks_found", 0)

                        if chunks:
                            # Possibly emit events
                            # Return the chunked text
                            response_parts = [
                                f"Here's what I found for query '{query}':"
                            ]
                            for i, c in enumerate(chunks, 1):
                                doc_text = c.get("text", "").strip()
                                doc_id = c.get("document_id", "unknown")
                                score = c.get("score", 0)
                                response_parts.append(
                                    f"\n{i}. (Doc: {doc_id}, relevance: {score:.3f})\n{doc_text}"
                                )
                            response_parts.append(
                                f"\nFound {total_chunks_found} relevant passages total."
                            )
                            return "\n".join(response_parts)
                        else:
                            # No relevant chunks
                            return (
                                "No relevant information found for that query. "
                                "Try rephrasing or uploading more documents."
                            )
                    else:
                        error_text = await response.text()
                        return f"Error from RAG API: {response.status} - {error_text}"
        except Exception as e:
            logger.exception(f"[RAG] Exception during search: {e}")
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

        # (Similar logic as above to fix placeholders, then call /rag/documents)
        if not conversation_id:
            return "Error: A valid conversation_id is required."

        try:
            async with aiohttp.ClientSession() as session:
                endpoint = f"{self.rag_api_url}/rag/documents?conversation_id={conversation_id}"
                async with session.get(endpoint) as response:
                    if response.status == 200:
                        result = await response.json()
                        docs = result.get("documents", [])
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
                        return f"Error from RAG API: {response.status} - {error_text}"
        except Exception as e:
            logger.exception(f"[RAG] Exception listing documents: {e}")
            return f"Error listing documents: {str(e)}"
