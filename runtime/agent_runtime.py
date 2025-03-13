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
import semantic_kernel as sk
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions.kernel_function_decorator import kernel_function

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR  # Change from WARNING to ERROR
)
logger = logging.getLogger("agent_runtime")

# Debug flag - set to False by default
DEBUG = os.environ.get("AGENT_RUNTIME_DEBUG", "false").lower() == "true"
print(f"Agent Runtime DEBUG mode: {DEBUG}, env var: {os.environ.get('AGENT_RUNTIME_DEBUG', 'not set')}")


def debug_print(message: str):
    """Print debug messages only if DEBUG is True."""
    if DEBUG:
        print(message)


# Track the last called agent
last_called_agent = None
last_agent_response = None  # Added to track the agent response for streaming


class AgentPlugin:
    """A plugin that represents an agent in the Semantic Kernel."""

    def __init__(self, agent_config: Dict[str, Any]):
        self.id = agent_config["id"]
        self.name = agent_config["name"]
        self.endpoint = agent_config["endpoint"]
        self.description = agent_config.get("description", f"Call the {self.name} agent")
        self.capabilities = agent_config.get("capabilities", [])
        self.conversation_starters = agent_config.get("conversation_starters", [])
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
        description="Call the agent with the given query. ONLY use for specific language greeting/farewell tasks, NOT for general knowledge or math.",
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
        global last_agent_response

        # Track this agent call
        last_called_agent = self.id
        last_agent_response = None  # Reset the response

        # Emit an agent_call event immediately (for streaming clients)
        # Skip the direct print to avoid duplicated output
        if hasattr(self, '_event_queue') and self._event_queue is not None:
            await self._event_queue.put({
                "agent_call": self.id,
                "agent_query": query  # Include the query being sent to the agent
            })

        logger.debug(f"Calling agent {self.id} with query: {query}")
        try:
            request = self.generate_request(query, sender_id, conversation_id)

            async with aiohttp.ClientSession() as session:
                logger.debug(f"Sending request to {self.endpoint}")
                async with session.post(self.endpoint, json=request) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_content = result.get("content", "No response from agent")
                        logger.debug(f"Received response from {self.id}: {response_content[:50]}...")

                        # Store the response for streaming
                        last_agent_response = response_content

                        # Emit the agent response event immediately (for streaming clients)
                        if hasattr(self, '_event_queue') and self._event_queue is not None:
                            await self._event_queue.put({
                                "agent_id": self.id,
                                "agent_response": response_content
                            })

                        return response_content
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
    """Main runtime for orchestrating agent interactions."""

    def __init__(self, config_path: str = None):
        self.agents = {}
        self.conversations = {}
        self.kernel = None
        self.verbose = False
        self.enable_streaming = False  # Default to False
        self.event_queue = None  # Initialize as None, will create when streaming is used

        # If config_path is not provided, use the default path
        if config_path is None:
            # Get the directory of the current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "agents.json")

        self.load_config(config_path)
        self.initialize_kernel()
        self.register_agent_plugins()

    def load_config(self, config_path: str):
        """Load agent configurations from the provided JSON file."""
        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            # Load settings if available
            if "settings" in config:
                settings = config["settings"]
                self.enable_streaming = settings.get("enable_streaming", False)

            for agent_config in config.get("agents", []):
                agent_id = agent_config["id"]
                self.agents[agent_id] = AgentPlugin(agent_config)
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
                chat_service = OpenAIChatCompletion(
                    service_id="chat-gpt",
                    ai_model_id="gpt-4o",
                    api_key=api_key
                )
                self.kernel.add_service(chat_service)
                logger.debug("OpenAI chat service added successfully")

                # Register agent plugins
                self.register_agent_plugins()

                logger.info("Semantic Kernel initialized successfully.")
            except Exception as e:
                logger.exception(f"Error initializing OpenAI chat service: {e}")
                logger.info("Continuing without function calling capabilities. Direct agent calling will not be available.")
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
                        self.kernel.plugins.add_from_object(agent, plugin_name)
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
            logger.warning("Continuing without function calling capabilities. Direct agent calling will not be available.")

        logger.info("Semantic Kernel initialized successfully.")

    async def process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False, max_agents: int = None) -> Dict[str, Any]:
        """Process a query using Semantic Kernel's function calling capabilities."""
        time.time()

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
        You are an intelligent orchestrator that coordinates between human users and specialized agent functions. Your primary responsibilities are:

        1. COORDINATION: Look at what agents you have access to and determine which one is the best fit for the user's question or if you should answer directly
        2. DETAILED COMMUNICATION: When calling an agent, provide the FULL CONTEXT of the user's question, not just isolated formulas or parts
        3. PROBLEM DESCRIPTION: Describe the complete problem to the agent, including all relevant details the user provided
        4. CLARITY: Frame queries to agents as requests for help solving a specific problem, not as commands to perform operations
        5. INTERACTION: If a user query is ambiguous or lacks necessary details, ask follow-up questions to clarify before proceeding
        6. CONSOLIDATION: Integrate agent responses into a coherent answer without unnecessary repetition

        IMPORTANT GUIDELINES:
        - When calling specialized agents like the math agent, frame requests as "The user wants to solve [complete problem]. Can you help with this?"
        - Allow agents to break down problems themselves rather than pre-fragmenting tasks
        - For each agent call, share the complete context and details from the user's question
        - Let agents determine their own approach to solving problems within their domain
        - Keep your final responses to users concise and focused on the answer, not the process
        - In final responses to users, don't repeat the agent's full chain of reasoning unless specifically requested
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

            # Add a note to only use functions when absolutely necessary
            settings.extension_data = {"function_call_guidance": "only_when_necessary"}

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

            # Return an error message instead of falling back
            error_message = f"Error processing query: {str(e)}"

            # Create an error response message
            response_message = {
                "messageId": str(uuid.uuid4()),
                "conversationId": conversation_id,
                "senderId": "runtime",
                "recipientId": "user",
                "content": error_message,
                "timestamp": datetime.datetime.now().isoformat(),
                "type": "Text",
                "error": str(e)
            }

            return response_message

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get the conversation history for a specific conversation."""
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]
        return []

    def get_agent_by_id(self, agent_id: str) -> Optional[AgentPlugin]:
        """Get an agent by its ID."""
        return self.agents.get(agent_id)

    def get_all_agents(self) -> Dict[str, AgentPlugin]:
        """Get all registered agents."""
        return self.agents

    async def stream_process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False):
        """Stream the processing of a query, yielding chunks of the response."""
        debug_print(f"DEBUG: stream_process_query called with query: {query}, conversation_id: {conversation_id}")
        start_time = time.time()

        # Create an event queue for this streaming session
        self.event_queue = asyncio.Queue()
        self._query_processed = False

        # Set event queue on agents temporarily
        for agent in self.agents.values():
            agent._event_queue = self.event_queue

        # Initialize conversation if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            debug_print(f"DEBUG: Generated new conversation_id: {conversation_id}")

        # Initialize conversation dictionary if it doesn't exist
        if conversation_id not in self.conversations:
            debug_print(f"DEBUG: Initializing new conversation dictionary for {conversation_id}")
            self.conversations[conversation_id] = []

        # Add user query to conversation history
        debug_print(f"DEBUG: Adding user query to conversation history for {conversation_id}")
        self.conversations[conversation_id].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        })

        # Create a background task to process the query
        query_task = asyncio.create_task(self._process_query_with_events(query, conversation_id, verbose))

        # Yield the events from the queue as they arrive
        while not query_task.done() or not self.event_queue.empty():
            try:
                # Try to get an event from the queue with a small timeout
                event = await asyncio.wait_for(self.event_queue.get(), 0.1)
                debug_print(f"DEBUG: Yielding event: {event}")
                yield event
                self.event_queue.task_done()
            except asyncio.TimeoutError:
                # No event available, check if query task is done
                if query_task.done():
                    # Get the result from the query task
                    result = query_task.result()
                    if result:
                        debug_print(f"DEBUG: Query task complete with result: {result}")
                        yield result
                    break

        # Cleanup
        for agent in self.agents.values():
            agent._event_queue = None
        self._query_processed = True
        debug_print(f"DEBUG: Stream processing complete in {time.time() - start_time:.2f}s")

    async def _process_query_with_events(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False):
        """Process a query and emit events along the way."""
        debug_print(f"DEBUG: _process_query_with_events called with query: {query}, conversation_id: {conversation_id}")
        start_time = time.time()

        # Try to use Semantic Kernel for function calling if available
        try:
            if self.kernel:
                # Create a chat history for this conversation
                debug_print("DEBUG: Creating chat history for conversation")
                chat_history = ChatHistory()

                # Add system message
                system_message = """
                You are an intelligent orchestrator that coordinates between human users and specialized agent functions. Your primary responsibilities are:

                1. COORDINATION: Analyze user queries to determine if they require specialized agent capabilities
                2. DETAILED COMMUNICATION: When calling an agent, provide the FULL CONTEXT of the user's question, not just isolated formulas or parts
                3. PROBLEM DESCRIPTION: Describe the complete problem to the agent, including all relevant details the user provided
                4. CLARITY: Frame queries to agents as requests for help solving a specific problem, not as commands to perform operations
                5. INTERACTION: If a user query is ambiguous or lacks necessary details, ask follow-up questions to clarify before proceeding
                6. CONSOLIDATION: Integrate agent responses into a coherent answer without unnecessary repetition

                IMPORTANT GUIDELINES:
                - When calling specialized agents like the math agent, frame requests as "The user wants to solve [complete problem]. Can you help with this?"
                - Allow agents to break down problems themselves rather than pre-fragmenting tasks
                - For each agent call, share the complete context and details from the user's question
                - Let agents determine their own approach to solving problems within their domain
                - Keep your final responses to users concise and focused on the answer, not the process
                - In final responses to users, don't repeat the agent's full chain of reasoning unless specifically requested
                - If you want to know more about what an agent can do, you are allowed to first ask the agent to describe its capabilities
                """
                debug_print("DEBUG: Adding system message to chat history")
                chat_history.add_system_message(system_message)

                # Add conversation history
                debug_print("DEBUG: Adding conversation history to chat history")
                for message in self.conversations[conversation_id]:
                    if message["role"] == "user":
                        chat_history.add_user_message(message["content"])
                    elif message["role"] == "assistant":
                        chat_history.add_assistant_message(message["content"])

                # Get the chat service
                debug_print("DEBUG: Getting chat service from kernel")
                chat_service = self.kernel.get_service("chat-gpt")

                # Set up function calling behavior
                debug_print("DEBUG: Setting up function calling behavior")
                settings = PromptExecutionSettings()
                settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

                # Add a note to only use functions when absolutely necessary
                settings.extension_data = {"function_call_guidance": "only_when_necessary"}

                debug_print("Using Semantic Kernel for function calling")

                # Get the final result - STREAMING VERSION
                debug_print("DEBUG: Getting streaming result from chat service")
                # Don't use await directly on an async generator
                response_stream = chat_service.get_streaming_chat_message_content(
                    chat_history=chat_history,
                    settings=settings,
                    kernel=self.kernel
                )

                # Process each chunk of the response as it arrives
                debug_print("DEBUG: Processing streaming response")
                full_response_content = ""
                chunks = []

                async for chunk in response_stream:
                    if chunk:
                        # Extract the chunk text
                        chunk_text = str(chunk)
                        debug_print(f"DEBUG: Received streaming chunk: '{chunk_text}'")
                        full_response_content += chunk_text
                        chunks.append(chunk)

                        # Add each chunk to event queue for streaming to client
                        debug_print(f"DEBUG: Putting chunk in event queue: '{chunk_text}'")
                        await self.event_queue.put({
                            "content": chunk_text
                        })
                        # Small sleep to ensure chunks are processed
                        await asyncio.sleep(0.01)

                # Process the complete response
                debug_print("DEBUG: Finished streaming, full response: {full_response_content}")

                # Get the agents that were used
                global last_called_agent
                global last_agent_response
                agents_used = []
                if last_called_agent:
                    debug_print(f"DEBUG: Adding last_called_agent to agents_used: {last_called_agent}")
                    agents_used.append(last_called_agent)
                    last_called_agent = None  # Reset for next query
                    last_agent_response = None  # Reset the response

                # Add to conversation history
                debug_print("DEBUG: Adding assistant response to conversation history for {conversation_id}")
                self.conversations[conversation_id].append({
                    "role": "assistant",
                    "content": full_response_content,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "agents_used": agents_used
                })

                # Return the complete response
                debug_print("DEBUG: Returning complete response")
                return {
                    "chunk": None,
                    "complete": True,
                    "response": full_response_content,
                    "conversation_id": conversation_id,
                    "processing_time": time.time() - start_time,
                    "agents_used": agents_used
                }
            else:
                # Kernel not available
                debug_print("DEBUG: Semantic Kernel not available")
                return {"error": "Semantic Kernel not available for processing"}
        except Exception as e:
            debug_print(f"Error in processing query: {e}")
            return {"error": f"Error processing query: {e}"}


async def main():
    """Run the agent runtime."""
    # Import what's needed here to avoid circular imports
    import argparse

    # Don't redefine asyncio which is already imported at the top
    # Just use what's already available

    parser = argparse.ArgumentParser(description="Agent Runtime")
    parser.add_argument("--config", help="Path to agent configuration file")

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
    asyncio.run(main())
