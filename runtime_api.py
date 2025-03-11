#!/usr/bin/env python3

import json
import os
import uuid
import time
import logging
from typing import Dict, List, Any, Optional, Set
import asyncio
import argparse
import uvicorn

import semantic_kernel as sk
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from agent_runtime import AgentRuntime, AgentTerminationStrategy, AgentGroupChat

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Set a default level
)
logger = logging.getLogger("runtime_api")
logger.setLevel(logging.WARNING)

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
        if query.stream:
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
    logger.debug(f"Starting streaming response for query: {query.query}")
    
    try:
        async for chunk in runtime.stream_process_query(
            query=query.query,
            conversation_id=query.conversation_id,
            verbose=query.verbose
        ):
            logger.debug(f"Streaming chunk: {chunk[:50] if isinstance(chunk, str) else 'non-string chunk'}...")
            if isinstance(chunk, str):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            else:
                yield f"data: {json.dumps(chunk)}\n\n"
        
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.exception(f"Error streaming response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

@app.post("/api/group-chat", response_model=Message)
async def group_chat(query: GroupChatQuery, runtime: AgentRuntime = Depends(get_runtime)):
    """Process a user query using a group chat of agents."""
    try:
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