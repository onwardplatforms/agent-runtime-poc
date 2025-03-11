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

from runtime.agent_runtime import AgentGroupChat, AgentRuntime, AgentTerminationStrategy

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR  # Change from WARNING to ERROR
)
logger = logging.getLogger("runtime_api")
logger.setLevel(logging.ERROR)

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
                    # Get the result
                    response = process_task.result()
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
                "endpoint": agent.endpoint
            })
            
        return {"agents": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing agents: {str(e)}")

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

if __name__ == "__main__":
    # Start the server
    print("Starting Agent Runtime API")
    uvicorn.run(app, host="0.0.0.0", port=5003, log_level="warning") 