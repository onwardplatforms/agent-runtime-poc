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
    level=logging.DEBUG  # You can dial this back to INFO or ERROR in production
)
logger = logging.getLogger("agent_runtime")

DEBUG = os.environ.get("AGENT_RUNTIME_DEBUG", "true").lower() == "true"
print(f"Agent Runtime DEBUG mode: {DEBUG}, env var: {os.environ.get('AGENT_RUNTIME_DEBUG', 'not set')}")

def debug_print(message: str):
    """Print debug messages only if DEBUG is True."""
    if DEBUG:
        print(message)

# Track the last called agent
last_called_agent = None
last_agent_response = None  # Track the agent response for streaming

# ──────────────────────────────────────────────────────────────────────────────
# SINGLE SOURCE FOR THE SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────────────────────
BASE_SYSTEM_PROMPT = """\
You are an intelligent orchestrator that coordinates between human users and specialized agent plugins (including a Retrieval-Augmented Generation plugin named 'rag_plugin'). 

Your primary responsibilities are:
1. **COORDINATION**: Analyze user queries to decide if they require specialized plugin calls.
2. **FULL CONTEXT**: When calling a plugin, provide the complete relevant details from the user question.
3. **PROBLEM DESCRIPTION**: Inform the plugin what the user is seeking or what problem they want solved.
4. **INTERACTION**: If a user query is ambiguous or lacks details, ask clarifying questions first.
5. **CONSOLIDATION**: Integrate plugin responses into a coherent final answer, focusing on correctness and clarity.

**IMPORTANT**:
- Use function calls only when needed (e.g., if the user’s query might require factual data from uploaded documents, consider calling the 'rag_plugin.search_documents' function).
- Always pass the correct 'conversation_id' when calling any function, especially for RAG.
- If no plugin function is relevant, simply reply directly as yourself.
- In final user responses, keep it concise and helpful.
- Summaries or explanations of the plugin’s internal reasoning should not be revealed unless explicitly asked.

Remember:
- The plugin system may contain a “rag_plugin” for retrieval-augmented generation; call it if you need factual references from documents. If no relevant information is found or the user’s query doesn’t require it, proceed with your own response.
"""

# ──────────────────────────────────────────────────────────────────────────────

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

        # Example of setting message type based on agent ID
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
        description="Call this specialized agent for certain tasks. Not for general knowledge or math.",
        name="call_agent"  # Ensure no hyphens in function name
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

        last_called_agent = self.id
        last_agent_response = None

        # Emit an agent_call event immediately (for streaming clients)
        if hasattr(self, '_event_queue') and self._event_queue is not None:
            await self._event_queue.put({
                "agent_call": self.id,
                "agent_query": query
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

                        # Emit the agent response event for streaming
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
        return iteration >= self.max_iterations


class AgentGroupChat:
    """Manages a conversation between multiple agents."""

    def __init__(self, agents: List[AgentPlugin], termination_strategy: Optional[AgentTerminationStrategy] = None):
        self.agents = agents
        self.termination_strategy = termination_strategy or AgentTerminationStrategy()
        self.messages = []

    async def process_query(self, query: str, user_id: str = "user",
                            conversation_id: Optional[str] = None, verbose: bool = False) -> Dict[str, Any]:
        """Process a user query through agent conversation."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        user_message = {
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.messages.append(user_message)

        execution_trace = []

        responses = []
        for agent in self.agents:
            if verbose:
                trace_entry = f"Calling {agent.name}..."
                execution_trace.append(trace_entry)
                print(trace_entry)

            response_content = await agent.call_agent(query, user_id, conversation_id)

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

        combined_content = " ".join([r["response"].get("content", "") for r in responses])

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

        self.messages.append({
            "role": "assistant",
            "content": combined_content,
            "timestamp": datetime.datetime.now().isoformat(),
            "agent_responses": responses,
            "execution_trace": execution_trace if verbose else None
        })

        return final_message

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.messages


class AgentRuntime:
    """Main runtime for orchestrating agent interactions."""

    def __init__(self, config_path: str = None):
        self.agents = {}
        self.conversations = {}
        self.kernel = None
        self.verbose = False
        self.enable_streaming = False
        self.event_queue = None

        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "agents.json")

        self.load_config(config_path)
        self.initialize_kernel()
        self.register_agent_plugins()

    def load_config(self, config_path: str):
        """Load agent configurations from JSON."""
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                
            self.config = config
            if "settings" in config:
                settings = config["settings"]
                self.enable_streaming = settings.get("enable_streaming", False)

            for agent_config in config.get("agents", []):
                agent_id = agent_config["id"]
                self.agents[agent_id] = AgentPlugin(agent_config)
        except Exception as e:
            print(f"Error loading agent configuration: {e}")
            self.config = {}

    def initialize_kernel(self):
        """Initialize the Semantic Kernel instance."""
        try:
            logger.info("Creating new Semantic Kernel instance")
            self.kernel = sk.Kernel()

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY environment variable not set.")

            logger.info("Adding OpenAI chat completion service")
            chat_service = OpenAIChatCompletion(
                service_id="chat-gpt",
                ai_model_id="gpt-4o",
                api_key=api_key
            )
            self.kernel.add_service(chat_service)
            logger.debug("OpenAI chat service added successfully")

            self.register_agent_plugins()

            logger.info("Semantic Kernel initialized successfully.")
        except Exception as e:
            logger.exception(f"Error initializing Semantic Kernel: {e}")

    def register_agent_plugins(self):
        """Register agent plugins with the kernel (including RAG)."""
        try:
            for agent_id, agent in self.agents.items():
                plugin_name = agent_id.replace('-', '_')
                try:
                    self.kernel.add_plugin(agent, plugin_name=plugin_name)
                    logger.info(f"Registered agent {agent_id} as plugin (add_plugin).")
                except Exception as e1:
                    logger.debug(f"add_plugin failed: {e1}")
                    try:
                        self.kernel.plugins.add_from_object(agent, plugin_name)
                        logger.info(f"Registered agent {agent_id} using create_plugin_from_object.")
                    except Exception as e2:
                        logger.debug(f"create_plugin_from_object failed: {e2}")
                        try:
                            self.kernel.register_plugin(agent, plugin_name=plugin_name)
                            logger.info(f"Registered agent {agent_id} using register_plugin.")
                        except Exception as e3:
                            logger.error(f"Could not register agent {agent_id}: {e1}, {e2}, {e3}")

            # Attempt to register RAG plugin
            try:
                from runtime.features.rag import RagPlugin
                rag_config = {}
                if hasattr(self, 'config') and isinstance(self.config, dict):
                    rag_config = self.config.get("settings", {}).get("data", {}).get("rag", {})

                rag_plugin = RagPlugin(rag_config)
                plugin_name = "rag_plugin"

                self.kernel.add_plugin(rag_plugin, plugin_name=plugin_name)
                logger.info("RAG plugin registered via add_plugin.")

                # Also try shorter name "rag" for convenience (ignore errors if it fails)
                try:
                    self.kernel.add_plugin(rag_plugin, plugin_name="rag")
                except Exception:
                    pass

                # Optionally register the search_documents function directly
                if hasattr(self.kernel, 'add_function'):
                    try:
                        search_docs_func = getattr(rag_plugin, 'search_documents')
                        if callable(search_docs_func):
                            self.kernel.add_function(search_docs_func, plugin_name="rag_plugin")
                            logger.info("Registered RAG's search_documents function directly.")
                    except Exception as direct_err:
                        logger.warning(f"Failed to register search_documents directly: {direct_err}")

                logger.info("RAG plugin registration complete.")
            except ImportError as e:
                logger.warning(f"Could not import RAG plugin: {e}")
            except Exception as e:
                logger.error(f"Error registering RAG plugin: {e}")
        except Exception as e:
            logger.error(f"Error registering agent plugins: {e}")
            logger.warning("Continuing without some plugin capabilities.")

    async def process_query(self, query: str, conversation_id: Optional[str] = None,
                            verbose: bool = False, max_agents: int = None) -> Dict[str, Any]:
        """
        Process a query using the orchestrator logic with GPT function calls if needed.
        """
        logger.info(f"*** Processing query: '{query}' ***")

        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        # Add user message
        self.conversations[conversation_id].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        })

        # Create chat history
        chat_history = ChatHistory()

        # SINGLE SOURCE FOR SYSTEM PROMPT
        system_message = BASE_SYSTEM_PROMPT + f"\n\n(Conversation ID: {conversation_id})"
        chat_history.add_system_message(system_message)

        # Add conversation history
        for msg in self.conversations[conversation_id]:
            if msg["role"] == "user":
                chat_history.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                chat_history.add_assistant_message(msg["content"])

        # Settings for function calling
        chat_service = self.kernel.get_service("chat-gpt")
        settings = PromptExecutionSettings()
        settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

        # Extension data for function calls
        extension_data = {
            "function_call_guidance": "only_when_necessary",
            "conversation_id": conversation_id
        }
        settings.extension_data = extension_data

        debug_print("Using Semantic Kernel for function calling")
        try:
            result = await chat_service.get_chat_message_contents(
                chat_history=chat_history, 
                settings=settings
            )
        except Exception as e:
            logger.error(f"Error getting chat message: {e}")
            return {
                "messageId": str(uuid.uuid4()),
                "conversationId": conversation_id,
                "senderId": "runtime",
                "recipientId": "user",
                "content": f"Error processing query: {e}",
                "timestamp": datetime.datetime.now().isoformat(),
                "type": "Text",
                "error": str(e)
            }

        # Extract content
        response_content = getattr(result, 'content', str(result))

        # Track function calls (if any)
        function_calls = getattr(result, 'function_calls', [])
        agents_used = []
        for fc in function_calls:
            function_name = fc.name
            agent_id = function_name.split('-')[0].replace('_', '-')
            agents_used.append(agent_id)
            logger.debug(f"Called {agent_id} with args: {fc.arguments}")

        response_message = {
            "messageId": str(uuid.uuid4()),
            "conversationId": conversation_id,
            "senderId": "runtime",
            "recipientId": "user",
            "content": response_content,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "Text",
            "agents_used": agents_used
        }

        self.conversations[conversation_id].append({
            "role": "assistant",
            "content": response_content,
            "timestamp": datetime.datetime.now().isoformat(),
            "agents_used": agents_used
        })

        return response_message

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]
        return []

    def get_agent_by_id(self, agent_id: str) -> Optional[AgentPlugin]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> Dict[str, AgentPlugin]:
        return self.agents

    async def stream_process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False):
        """
        Stream the processing of a query, yielding chunks of the response.
        Useful for UI streaming.
        """
        debug_print(f"DEBUG: stream_process_query called with query: {query}, conversation_id: {conversation_id}")
        start_time = time.time()

        self.event_queue = asyncio.Queue()
        self._query_processed = False

        for agent in self.agents.values():
            agent._event_queue = self.event_queue

        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        self.conversations[conversation_id].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.datetime.now().isoformat()
        })

        query_task = asyncio.create_task(self._process_query_with_events(query, conversation_id, verbose))

        while not query_task.done() or not self.event_queue.empty():
            try:
                event = await asyncio.wait_for(self.event_queue.get(), 0.1)
                yield event
                self.event_queue.task_done()
            except asyncio.TimeoutError:
                if query_task.done():
                    result = query_task.result()
                    if result:
                        yield result
                    break

        for agent in self.agents.values():
            agent._event_queue = None
        self._query_processed = True
        debug_print(f"DEBUG: Stream processing complete in {time.time() - start_time:.2f}s")

    async def _process_query_with_events(self, query: str, conversation_id: str, verbose: bool = False):
        debug_print(f"DEBUG: _process_query_with_events called with query: {query}, conversation_id: {conversation_id}")
        start_time = time.time()

        if not self.kernel:
            return {"error": "Semantic Kernel not available"}

        # Create chat history
        chat_history = ChatHistory()

        # SINGLE SOURCE FOR SYSTEM PROMPT
        system_message = BASE_SYSTEM_PROMPT + f"\n\n(Conversation ID: {conversation_id})"
        chat_history.add_system_message(system_message)

        # Add conversation history
        for msg in self.conversations[conversation_id]:
            if msg["role"] == "user":
                chat_history.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                chat_history.add_assistant_message(msg["content"])

        chat_service = self.kernel.get_service("chat-gpt")
        settings = PromptExecutionSettings()
        settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

        extension_data = {
            "function_call_guidance": "only_when_necessary",
            "conversation_id": conversation_id
        }
        settings.extension_data = extension_data

        debug_print("Using Semantic Kernel for function calling (streaming)")

        try:
            response_stream = chat_service.get_streaming_chat_message_content(
                chat_history=chat_history,
                settings=settings,
                kernel=self.kernel
            )

            full_response_content = ""
            async for chunk in response_stream:
                if chunk:
                    chunk_text = str(chunk)
                    full_response_content += chunk_text
                    await self.event_queue.put({"content": chunk_text})
                    await asyncio.sleep(0.01)

            global last_called_agent
            global last_agent_response
            agents_used = []
            if last_called_agent:
                agents_used.append(last_called_agent)
                last_called_agent = None
                last_agent_response = None

            self.conversations[conversation_id].append({
                "role": "assistant",
                "content": full_response_content,
                "timestamp": datetime.datetime.now().isoformat(),
                "agents_used": agents_used
            })

            return {
                "chunk": None,
                "complete": True,
                "response": full_response_content,
                "conversation_id": conversation_id,
                "processing_time": time.time() - start_time,
                "agents_used": agents_used
            }
        except Exception as e:
            return {"error": f"Error processing query: {e}"}


async def main():
    """Example usage of AgentRuntime."""
    import argparse
    parser = argparse.ArgumentParser(description="Agent Runtime")
    parser.add_argument("--config", help="Path to agent configuration file")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable")
        return

    runtime = AgentRuntime(config_path=args.config)

    await asyncio.sleep(1)

    queries = [
        "Say hello in Spanish",
        "Tell me about the contents of my NDA document",
        "First say hello in German, then say goodbye in Italian"
    ]

    for query in queries:
        print(f"\nProcessing query: '{query}'")
        response = await runtime.process_query(query, verbose=True)
        print(f"Response: {response.get('content', '')}")
        if "agents_used" in response:
            print(f"Agents used: {response['agents_used']}")


if __name__ == "__main__":
    asyncio.run(main())
