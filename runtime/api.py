#!/usr/bin/env python3

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from runtime.agent_runtime import AgentGroupChat, AgentRuntime

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


@app.post("/runtime/query")
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


@app.post("/runtime/group-chat")
async def group_chat(query: GroupChatQuery, runtime: AgentRuntime = Depends(get_runtime)):
    """Process a query using the agent group chat."""
    logger.info(f"Received group chat query: {query.query}")

    try:
        # Use streaming if requested
        if query.stream:
            return StreamingResponse(
                stream_group_chat_response(query, runtime),
                media_type="text/event-stream"
            )

        # Create a group chat with the specified agents
        group_chat = AgentGroupChat(
            runtime=runtime,
            agent_ids=query.agent_ids,
            max_iterations=query.max_iterations,
            conversation_id=query.conversation_id,
            user_id=query.user_id
        )

        result = await group_chat.process_query(
            query=query.query,
            verbose=query.verbose
        )

        # Return the result directly
        return result
    except Exception as e:
        logger.exception(f"Error processing group chat query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def stream_group_chat_response(query: GroupChatQuery, runtime: AgentRuntime):
    """Stream the response to a group chat query."""
    logger.info(f"Starting streaming response for group chat query: {query.query}")

    try:
        # Send an initial message to confirm streaming has started
        yield f"data: {json.dumps({'chunk': 'Starting group chat...', 'complete': False})}\n\n"

        # Create a group chat with the specified agents
        group_chat = AgentGroupChat(
            runtime=runtime,
            agent_ids=query.agent_ids,
            max_iterations=query.max_iterations,
            conversation_id=query.conversation_id,
            user_id=query.user_id
        )

        async for chunk in group_chat.stream_process_query(
            query=query.query,
            verbose=query.verbose
        ):
            # Format and send the chunk
            if isinstance(chunk, str):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            else:
                yield f"data: {json.dumps(chunk)}\n\n"

            # Flush data
            await asyncio.sleep(0)

        # Send a final message to confirm streaming is complete
        yield f"data: {json.dumps({'chunk': 'Group chat complete', 'complete': True})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.exception(f"Error streaming group chat response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@app.get("/runtime/agents")
async def list_agents(runtime: AgentRuntime = Depends(get_runtime)):
    """List all available agents."""
    try:
        agent_plugins = runtime.get_all_agents()
        agents = []

        for agent_id, plugin in agent_plugins.items():
            agents.append({
                "id": plugin.id,
                "name": plugin.name,
                "description": plugin.description,
                "capabilities": plugin.capabilities,
                "conversation_starters": plugin.conversation_starters,
                "endpoint": plugin.endpoint
            })

        return {"agents": agents}
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runtime/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, runtime: AgentRuntime = Depends(get_runtime)):
    """Get a conversation by ID."""
    try:
        conversation = await runtime.get_conversation(conversation_id)
        if conversation:
            return conversation
        raise HTTPException(status_code=404, detail="Conversation not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runtime/conversations")
async def list_conversations(runtime: AgentRuntime = Depends(get_runtime)):
    """List all conversations."""
    try:
        conversations = await runtime.list_conversations()
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/runtime/conversations")
async def create_conversation(runtime: AgentRuntime = Depends(get_runtime)):
    """Create a new conversation."""
    try:
        conversation_id = str(uuid.uuid4())
        await runtime.create_conversation(conversation_id)
        return {"conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)
