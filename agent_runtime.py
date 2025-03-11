#!/usr/bin/env python3

import json
import os
import uuid
import time
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Set, Annotated
import datetime
import aiohttp

import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.functions.kernel_function_decorator import kernel_function
from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.contents.chat_history import ChatHistory
import requests

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Set a default level
)
logger = logging.getLogger("agent_runtime")

# Track the last called agent
last_called_agent = None

class AgentPlugin:
    """A plugin that represents an agent in the Semantic Kernel."""
    
    def __init__(self, agent_config: Dict[str, Any]):
        self.id = agent_config["id"]
        self.name = agent_config["name"]
        self.endpoint = agent_config["endpoint"]
        self.description = agent_config.get("description", f"Call the {self.name} agent")
        self.capabilities = agent_config.get("capabilities", [])
        logger.debug(f"Initialized AgentPlugin: {self.id} with endpoint {self.endpoint}")
        
    def generate_request(self, content: str, sender_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a request to the agent."""
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
            
        # Handle special message types based on agent ID
        # This is an implementation detail that could be moved to agent config
        msg_type = 0 if self.id == "goodbye-agent" else "Text"
            
        return {
            "messageId": str(uuid.uuid4()),
            "conversationId": conversation_id,
            "senderId": sender_id,
            "recipientId": self.id,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": msg_type
        }
    
    @kernel_function(
        description="Call the agent with the given query",
        name="call_agent"  # Explicitly set the function name without hyphens
    )
    async def call_agent(
        self, 
        query: str,
        sender_id: str = "runtime",
        conversation_id: str = None
    ) -> str:
        """Call the agent with the given query."""
        global last_called_agent
        
        # Track this agent call
        last_called_agent = self.id
        
        # Print the agent call to stdout for immediate visibility
        print(f"\nƒ(x) calling the [{self.id}] agent...")
        
        logger.debug(f"Calling agent {self.id} with query: {query}")
        try:
            request = self.generate_request(query, sender_id, conversation_id)
            
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Sending request to {self.endpoint}")
                async with session.post(self.endpoint, json=request) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.debug(f"Received response from {self.id}: {result.get('content', '')[:50]}...")
                        return result.get("content", "No response from agent")
                    else:
                        error_text = await response.text()
                        logger.error(f"Error calling agent {self.id}: {response.status} - {error_text}")
                        return f"Error calling agent: {response.status}"
        except Exception as e:
            logger.error(f"Exception calling agent {self.id}: {e}")
            return f"Exception calling agent: {str(e)}"

class AgentTerminationStrategy:
    """Strategy to determine when a multi-agent conversation should terminate."""
    
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
    
    def should_terminate(self, iteration: int, messages: List[Dict[str, Any]]) -> bool:
        """Determine if the conversation should terminate."""
        # Basic implementation: terminate after max iterations
        return iteration >= self.max_iterations

class AgentGroupChat:
    """Manages a conversation between multiple agents."""
    
    def __init__(self, agents: List[AgentPlugin], termination_strategy: Optional[AgentTerminationStrategy] = None):
        self.agents = agents
        self.termination_strategy = termination_strategy or AgentTerminationStrategy()
        self.messages = []
    
    async def process_query(self, query: str, user_id: str = "user", conversation_id: Optional[str] = None, verbose: bool = False) -> Dict[str, Any]:
        """Process a user query through agent conversation."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Add user message to conversation
        user_message = {
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.messages.append(user_message)
        
        # Set up execution trace if verbose
        execution_trace = []
        
        # Call agents and collect responses
        responses = []
        for agent in self.agents:
            # Add to execution trace before calling
            if verbose:
                trace_entry = f"Calling {agent.name}..."
                execution_trace.append(trace_entry)
                print(trace_entry)
            
            # Call the agent
            response_content = await agent.call_agent(query, user_id, conversation_id)
            
            # Add to execution trace if verbose
            if verbose:
                print(f"  ↪ {response_content}")
            
            responses.append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "response": {
                    "content": response_content,
                    "messageId": str(uuid.uuid4()),
                    "conversationId": conversation_id,
                    "senderId": agent.id,
                    "recipientId": user_id,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "type": "Text"
                }
            })
        
        # Combine responses
        combined_content = " ".join([r["response"].get("content", "") for r in responses])
        
        # Create final message
        final_message = {
            "messageId": str(uuid.uuid4()),
            "conversationId": conversation_id,
            "senderId": "agent-runtime",
            "recipientId": user_id,
            "content": combined_content,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "Text",
            "agent_responses": responses,
            "execution_trace": execution_trace if verbose else None
        }
        
        # Add to conversation history
        self.messages.append({
            "role": "assistant",
            "content": combined_content,
            "timestamp": datetime.datetime.now().isoformat(),
            "agent_responses": responses,
            "execution_trace": execution_trace if verbose else None
        })
        
        return final_message
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return self.messages

class AgentRuntime:
    """A runtime that orchestrates agent interactions using Semantic Kernel."""
    
    def __init__(self, config_path: str = "agents.json"):
        self.agents = {}
        self.conversations = {}
        self.kernel = None
        self.verbose = False
        self.load_config(config_path)
        self.initialize_kernel()
        
    def load_config(self, config_path: str):
        """Load agent configurations from the provided JSON file."""
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                
            for agent_config in config.get("agents", []):
                agent_id = agent_config["id"]
                self.agents[agent_id] = AgentPlugin(agent_config)
                print(f"Loaded agent: {agent_config['name']} ({agent_id})")
        except Exception as e:
            print(f"Error loading agent configuration: {e}")
    
    def initialize_kernel(self):
        """Initialize the Semantic Kernel instance with agent functions."""
        try:
            # Create a new kernel
            logger.info("Creating new Semantic Kernel instance")
            self.kernel = sk.Kernel()
            
            # Add the OpenAI chat completion service
            try:
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("OPENAI_API_KEY environment variable not set.")
                
                # Add the OpenAI chat completion service
                logger.info("Adding OpenAI chat completion service")
                chat_service = sk.connectors.ai.open_ai.OpenAIChatCompletion(
                    service_id="chat-gpt",
                    ai_model_id="gpt-3.5-turbo",
                    api_key=api_key
                )
                self.kernel.add_service(chat_service)
                logger.debug("OpenAI chat service added successfully")
                
                # Register agent plugins
                self.register_agent_plugins()
                
                logger.info("Semantic Kernel initialized successfully.")
            except Exception as e:
                logger.exception(f"Error initializing OpenAI chat service: {e}")
                logger.info("Continuing without function calling capabilities.")
        except Exception as e:
            logger.exception(f"Error initializing Semantic Kernel: {e}")
    
    def register_agent_plugins(self):
        """Register agent plugins with the kernel."""
        try:
            # Register each agent as a plugin
            for agent_id, agent in self.agents.items():
                logger.debug(f"Registering agent {agent_id} as a plugin")
                logger.debug(f"Agent object: {agent.__dict__}")
                
                # Convert agent_id to a valid plugin name (replace hyphens with underscores)
                plugin_name = agent_id.replace('-', '_')
                logger.debug(f"Using plugin name: {plugin_name} for agent {agent_id}")
                
                # Log the available methods on the kernel
                logger.debug(f"Available kernel methods: {dir(self.kernel)}")
                
                # Try different registration methods based on Semantic Kernel version
                try:
                    logger.debug("Trying to register with add_plugin")
                    self.kernel.add_plugin(agent, plugin_name=plugin_name)
                    logger.info(f"Registered agent {agent_id} as a plugin using add_plugin")
                except Exception as e1:
                    logger.debug(f"add_plugin failed: {e1}")
                    try:
                        logger.debug("Trying to register with create_plugin_from_object")
                        plugin = self.kernel.create_plugin_from_object(agent, name=plugin_name)
                        logger.info(f"Registered agent {agent_id} as a plugin using create_plugin_from_object")
                    except Exception as e2:
                        logger.debug(f"create_plugin_from_object failed: {e2}")
                        try:
                            logger.debug("Trying to register with register_plugin")
                            self.kernel.register_plugin(agent, plugin_name=plugin_name)
                            logger.info(f"Registered agent {agent_id} as a plugin using register_plugin")
                        except Exception as e3:
                            logger.debug(f"register_plugin failed: {e3}")
                            logger.error(f"All registration methods failed for agent {agent_id}")
                            raise Exception(f"Could not register agent {agent_id}: {e1}, {e2}, {e3}")
        except Exception as e:
            logger.error(f"Error registering agent plugins: {e}")
            # Continue without function calling capabilities
            logger.warning("Continuing without function calling capabilities. Will use fallback method.")
            
        logger.info("Semantic Kernel initialized successfully.")
    
    async def process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False, max_agents: int = None) -> Dict[str, Any]:
        """Process a query using Semantic Kernel's function calling capabilities."""
        start_time = time.time()
        
        # Initialize conversation if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Initialize conversation history if it doesn't exist
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        # Add user message to conversation history
        self.conversations[conversation_id].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Create a chat history for the conversation
        chat_history = ChatHistory()
        
        # Add system message
        system_message = """
        You are an orchestrator for multiple specialized agents. Your job is to:
        1. Understand user queries and decide which agent functions should handle them
        2. Provide a complete, coherent response that incorporates information from the agents
        3. Only call agent functions when necessary to answer the query
        """
        chat_history.add_system_message(system_message)
        
        # Add conversation history
        for message in self.conversations[conversation_id]:
            if message["role"] == "user":
                chat_history.add_user_message(message["content"])
            elif message["role"] == "assistant":
                chat_history.add_assistant_message(message["content"])
        
        # Track which agents were used
        agents_used = []
        execution_trace = []
        
        try:
            # Get the chat service
            chat_service = self.kernel.get_service("chat-gpt")
            
            # Set up function calling behavior
            settings = PromptExecutionSettings()
            settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
            
            print("Using Semantic Kernel for function calling")
            
            # Process the query with function calling
            result = await chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings,
                kernel=self.kernel
            )
            
            # Extract the response content
            # Handle different result formats
            if hasattr(result, 'content'):
                response_content = result.content
            elif hasattr(result, 'items') and len(result.items) > 0 and hasattr(result.items[0], 'text'):
                response_content = result.items[0].text
            elif isinstance(result, list) and len(result) > 0:
                if hasattr(result[0], 'items') and len(result[0].items) > 0 and hasattr(result[0].items[0], 'text'):
                    response_content = result[0].items[0].text
                elif hasattr(result[0], 'content'):
                    response_content = result[0].content
                else:
                    response_content = str(result[0])
            else:
                response_content = str(result)
            
            logger.debug(f"Extracted response content: {response_content[:50]}...")
            
            # Check if any function calls were made
            function_calls = []
            if hasattr(result, 'function_calls'):
                function_calls = result.function_calls
            elif isinstance(result, list) and len(result) > 0 and hasattr(result[0], 'function_calls'):
                function_calls = result[0].function_calls
            
            if function_calls:
                for function_call in function_calls:
                    function_name = function_call.name
                    agent_id = function_name.split('-')[0].replace('_', '-')
                    agents_used.append(agent_id)
                    execution_trace.append(f"Called {agent_id} with query: {query}")
                    logger.debug(f"Function call: {function_name} with args: {function_call.arguments}")
            
            # Create the response message
            response_message = {
                "messageId": str(uuid.uuid4()),
                "conversationId": conversation_id,
                "senderId": "runtime",
                "recipientId": "user",
                "content": response_content,
                "timestamp": datetime.datetime.now().isoformat(),
                "type": "Text",
                "execution_trace": execution_trace if verbose else [],
                "agents_used": agents_used  # Always include agents_used
            }
            
            # Add to conversation history
            self.conversations[conversation_id].append({
                "role": "assistant",
                "content": response_content,
                "timestamp": datetime.datetime.now().isoformat(),
                "execution_trace": execution_trace if verbose else [],
                "agents_used": agents_used  # Always include agents_used
            })
            
            return response_message
            
        except Exception as e:
            logger.exception(f"Error using Semantic Kernel for function calling: {e}")
            print(f"Falling back to direct agent calling due to error: {e}")
            
            # Fall back to direct agent calling
            return await self._fallback_process_query(query, conversation_id, verbose, max_agents)
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get the conversation history for a specific conversation."""
        return self.conversations.get(conversation_id, [])
    
    def get_agent_by_id(self, agent_id: str) -> Optional[AgentPlugin]:
        """Get an agent by its ID."""
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> Dict[str, AgentPlugin]:
        """Get all registered agents."""
        return self.agents

    async def stream_process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False):
        """Stream the processing of a query, yielding chunks of the response."""
        start_time = time.time()
        
        # Initialize conversation if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            self.conversations[conversation_id] = []
        
        # Add user query to conversation history
        self.conversations[conversation_id].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Try to use Semantic Kernel for function calling if available
        try:
            if self.kernel:
                # Yield a status update
                yield {
                    "chunk": "Processing with Semantic Kernel...",
                    "complete": False
                }
                
                # Create a chat history for the conversation
                chat_history = ChatHistory()
                
                # Add system message
                system_message = """
                You are an orchestrator for multiple specialized agents. Your job is to:
                1. Understand user queries and decide which agent functions should handle them
                2. Provide a complete, coherent response that incorporates information from the agents
                3. Only call agent functions when necessary to answer the query
                
                The available agent functions each have specific capabilities. Call only the functions needed
                to fully address all aspects of the user's query.
                """
                chat_history.add_system_message(system_message)
                
                # Add conversation history
                for message in self.conversations[conversation_id]:
                    if message["role"] == "user":
                        chat_history.add_user_message(message["content"])
                    elif message["role"] == "assistant":
                        chat_history.add_assistant_message(message["content"])
                
                # Get the chat service
                chat_service = self.kernel.get_service("chat-gpt")
                
                # Set up function calling behavior with the new API
                settings = PromptExecutionSettings()
                settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
                
                # Process the query with streaming
                content_chunks = []
                agents_used = []
                execution_trace = []
                
                async for chunk in chat_service.get_streaming_chat_message_contents(
                    chat_history=chat_history,
                    settings=settings,
                    kernel=self.kernel
                ):
                    # Extract content from the chunk
                    content = chunk.content if hasattr(chunk, "content") else ""
                    if content:
                        content_chunks.append(content)
                        yield {
                            "chunk": content,
                            "complete": False
                        }
                    
                    # Extract function calls from chunk
                    if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                        for tool_call in chunk.tool_calls:
                            if hasattr(tool_call, "function") and hasattr(tool_call.function, "name"):
                                func_name = tool_call.function.name
                                
                                # Extract agent ID from function name
                                for agent_id in self.agents:
                                    if agent_id in func_name and agent_id not in agents_used:
                                        agents_used.append(agent_id)
                                        trace_entry = f"Called {agent_id}"
                                        execution_trace.append(trace_entry)
                                        yield {
                                            "chunk": f"Calling {self.agents[agent_id].name}...",
                                            "complete": False,
                                            "agent_id": agent_id
                                        }
                
                # Join the chunks for the final content
                full_content = "".join(content_chunks)
                
                # Add the response to the conversation history
                self.conversations[conversation_id].append({
                    "role": "assistant",
                    "content": full_content,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "agents_used": agents_used
                })
                
                # Yield the complete response
                yield {
                    "chunk": None,
                    "complete": True,
                    "response": full_content,
                    "conversation_id": conversation_id,
                    "processing_time": time.time() - start_time,
                    "agents_used": agents_used,
                    "execution_trace": execution_trace if verbose else None
                }
                return
            else:
                # Fall back to direct agent calling if Semantic Kernel is not available
                yield {
                    "chunk": "Semantic Kernel not available, falling back to direct agent calling...",
                    "complete": False
                }
        except Exception as e:
            print(f"Error using Semantic Kernel for function calling: {e}")
            yield {
                "chunk": f"Error using Semantic Kernel: {str(e)}. Falling back to direct agent calling...",
                "complete": False
            }
        
        # Fall back to direct agent calling
        # Simple keyword-based agent selection
        agents_to_use = []
        
        # Check for hello-related keywords
        if any(keyword in query.lower() for keyword in ["hello", "hi", "greet", "hola", "bonjour"]):
            agents_to_use.append("hello-agent")
            
        # Check for goodbye-related keywords
        if any(keyword in query.lower() for keyword in ["goodbye", "bye", "farewell", "adios", "au revoir"]):
            agents_to_use.append("goodbye-agent")
            
        # If no specific agent was selected, use both as a fallback
        if not agents_to_use:
            agents_to_use = ["hello-agent", "goodbye-agent"]
        
        # Call the selected agents
        responses = []
        execution_trace = []
        
        for agent_id in agents_to_use:
            agent = self.agents[agent_id]
            try:
                # Yield a status update
                yield {
                    "chunk": f"Calling {agent.name}...",
                    "complete": False
                }
                
                print(f"Calling agent {agent_id} with query: {query}")
                response = await agent.call_agent(query, "user", conversation_id)
                
                # Yield the agent's response
                yield {
                    "chunk": response,
                    "complete": False,
                    "agent_id": agent_id
                }
                
                responses.append({
                    "agent_id": agent_id,
                    "response": response
                })
                execution_trace.append({
                    "agent_id": agent_id,
                    "query": query,
                    "response": response,
                    "timestamp": datetime.datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Error calling agent {agent_id}: {e}")
                # Yield the error
                yield {
                    "chunk": f"Error calling {agent.name}: {str(e)}",
                    "complete": False,
                    "agent_id": agent_id
                }
                
                responses.append({
                    "agent_id": agent_id,
                    "error": str(e)
                })
                execution_trace.append({
                    "agent_id": agent_id,
                    "query": query,
                    "error": str(e),
                    "timestamp": datetime.datetime.now().isoformat()
                })
        
        # Combine responses
        combined_response = " ".join([r["response"] for r in responses if "response" in r])
        
        # Add to conversation history
        self.conversations[conversation_id].append({
            "role": "assistant",
            "content": combined_response,
            "timestamp": datetime.datetime.now().isoformat(),
            "agents_used": agents_to_use
        })
        
        # Yield the complete response
        yield {
            "chunk": None,
            "complete": True,
            "response": combined_response,
            "conversation_id": conversation_id,
            "processing_time": time.time() - start_time,
            "agents_used": agents_to_use,
            "execution_trace": execution_trace if verbose else None
        }

    async def _fallback_process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False, max_agents: int = None) -> Dict[str, Any]:
        """Fallback method for processing queries when Semantic Kernel function calling fails."""
        start_time = time.time()
        
        # Initialize conversation if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Initialize conversation history if it doesn't exist
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        # Simple keyword-based agent selection
        agents_to_use = []
        
        # Check for hello-related keywords
        if any(keyword in query.lower() for keyword in ["hello", "hi", "greet", "hola", "bonjour"]):
            agents_to_use.append("hello-agent")
            
        # Check for goodbye-related keywords
        if any(keyword in query.lower() for keyword in ["goodbye", "bye", "farewell", "adios", "au revoir"]):
            agents_to_use.append("goodbye-agent")
            
        # If no specific agent was selected, use both as a fallback
        if not agents_to_use:
            agents_to_use = ["hello-agent", "goodbye-agent"]
            
        # Limit the number of agents if specified
        if max_agents and len(agents_to_use) > max_agents:
            agents_to_use = agents_to_use[:max_agents]
            
        # Call the selected agents
        responses = []
        execution_trace = []
        
        for agent_id in agents_to_use:
            agent = self.agents[agent_id]
            try:
                logger.debug(f"Calling agent {agent_id} with query: {query}")
                response = await agent.call_agent(query, "user", conversation_id)
                responses.append({
                    "agent_id": agent_id,
                    "response": response
                })
                execution_trace.append(f"Called {agent_id} with query: {query}")
            except Exception as e:
                logger.exception(f"Error calling agent {agent_id}: {e}")
                responses.append({
                    "agent_id": agent_id,
                    "error": str(e)
                })
                execution_trace.append(f"Error calling {agent_id}: {e}")
        
        # Combine responses
        combined_response = " ".join([r["response"] for r in responses if "response" in r])
        
        # Create the response message
        response_message = {
            "messageId": str(uuid.uuid4()),
            "conversationId": conversation_id,
            "senderId": "runtime",
            "recipientId": "user",
            "content": combined_response,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "Text",
            "execution_trace": execution_trace if verbose else [],
            "agents_used": agents_to_use  # Always include agents_used
        }
        
        # Add to conversation history
        self.conversations[conversation_id].append({
            "role": "assistant",
            "content": combined_response,
            "timestamp": datetime.datetime.now().isoformat(),
            "execution_trace": execution_trace if verbose else [],
            "agents_used": agents_to_use  # Always include agents_used
        })
        
        return response_message

async def main():
    """Main function to demonstrate the agent runtime."""
    # Ensure the API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the runtime
    runtime = AgentRuntime()
    
    # Wait for kernel initialization
    await asyncio.sleep(1)
    
    # Example queries
    queries = [
        "Say hello in Spanish",
        "Say goodbye in French",
        "First say hello in German, then say goodbye in Italian"
    ]
    
    # Process each query
    for query in queries:
        print(f"\nProcessing query: '{query}'")
        response = await runtime.process_query(query, verbose=True)
        print(f"Response: {response['response']}")
        if "agents_used" in response:
            print(f"Selected agents: {response['agents_used']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 