# Semantic Kernel Runtime: Core Concepts

This document explores the core concepts behind our Agent Runtime implementation and how it leverages Semantic Kernel to orchestrate multiple independent agents in a unified system.

## Introduction to Semantic Kernel

[Semantic Kernel](https://github.com/microsoft/semantic-kernel) is an open-source orchestration framework that combines Large Language Models (LLMs) with conventional programming. It provides developers with a flexible way to compose AI capabilities with traditional code.

Key Semantic Kernel features we leverage:

- **Function Calling**: Allows LLMs to intelligently invoke functions defined in our system
- **Chat Completion**: Provides structured generation of conversational responses
- **Plugin Architecture**: Enables extension through modular capabilities
- **Streaming**: Supports token-by-token streaming for responsive user experiences

## Multi-Agent Orchestration

Our Agent Runtime uses Semantic Kernel as the foundation for orchestrating interactions between multiple independent agents. The core innovation is the ability to:

1. **Dynamically discover** and interact with agents based on their descriptions
2. **Intelligently route** queries to the most appropriate agent(s)
3. **Coordinate communication** between multiple agents
4. **Stream responses** in real-time from agents to clients

## Key Components

### 1. AgentPlugin

The `AgentPlugin` class is a wrapper around external agent services that makes them available to Semantic Kernel as functions:

```python
class AgentPlugin:
    def __init__(self, agent_config: Dict[str, Any]):
        self.id = agent_config["id"]
        self.name = agent_config["name"]
        self.description = agent_config["description"]
        self.endpoint = agent_config["endpoint"]
        
    @kernel_function(
        description="Call the agent with the given query",
        name="call_agent"
    )
    async def call_agent(self, query: str, sender_id: str = "runtime", 
                         conversation_id: str = None) -> str:
        # Implementation details for calling the external agent service
        # ...
        return response_content
```

Key concepts:
- Each agent is registered as a **kernel function** via the `@kernel_function` decorator
- The function includes a **description** that informs Semantic Kernel when to use it
- Agents are invoked via HTTP requests to their registered endpoints
- The agent's description is used by the LLM to determine when to call this agent

### 2. Function Calling and Agent Selection

The runtime uses Semantic Kernel's function calling capabilities to determine which agent to invoke based on the user's query:

```python
async def process_query(self, query: str, conversation_id: Optional[str] = None, 
                        verbose: bool = False, max_agents: int = None) -> Dict[str, Any]:
    # Create chat history
    chat_history = sk.ChatHistory()
    chat_history.add_user_message(query)
    
    # Configure function calling to select the appropriate agent
    settings = sk.PromptExecutionSettings(
        extension_data={
            "max_tokens": 2000,
            "temperature": 0.7,
            "tool_choice": "auto",
            "tools": self._get_function_definitions()
        }
    )
    
    # Get the chat completion service
    chat_service = self.kernel.get_service("chat-completion")
    
    # Get a response from the chat service, which may call agent functions
    result = await chat_service.get_chat_message_contents(
        chat_history=chat_history,
        settings=settings,
        kernel=self.kernel
    )
    
    # Return the result
    return result
```

Key concepts:
- The user's query is added to a **ChatHistory** object
- **PromptExecutionSettings** configures the LLM to use function calling
- Function definitions from all registered agents are provided to the LLM
- Semantic Kernel uses the LLM to determine which function/agent to call
- The LLM intelligently selects agents based on their descriptions and the query's intent

### 3. Streaming Implementation

The runtime implements streaming using Semantic Kernel's streaming capabilities:

```python
async def stream_process_query(self, query: str, conversation_id: Optional[str] = None, 
                              verbose: bool = False):
    # Create an event queue for this streaming session
    self.event_queue = asyncio.Queue()
    
    # Set event queue on agents temporarily
    for agent in self.agents.values():
        agent._event_queue = self.event_queue
    
    # Create a background task to process the query
    query_task = asyncio.create_task(
        self._process_query_with_events(query, conversation_id, verbose)
    )
    
    # Yield the events from the queue as they arrive
    while not query_task.done() or not self.event_queue.empty():
        try:
            event = await asyncio.wait_for(self.event_queue.get(), 0.1)
            yield event
            self.event_queue.task_done()
        except asyncio.TimeoutError:
            if query_task.done():
                break

async def _process_query_with_events(self, query: str, conversation_id: Optional[str] = None, 
                                    verbose: bool = False):
    # Similar to process_query but uses streaming
    chat_history = sk.ChatHistory()
    chat_history.add_user_message(query)
    
    settings = sk.PromptExecutionSettings(/* ... */)
    chat_service = self.kernel.get_service("chat-completion")
    
    # Get streaming response
    response_stream = chat_service.get_streaming_chat_message_content(
        chat_history=chat_history,
        settings=settings,
        kernel=self.kernel
    )
    
    # Process each chunk as it arrives
    async for chunk in response_stream:
        if chunk:
            # Extract the chunk text
            chunk_text = str(chunk)
            # Add each chunk to event queue for streaming to client
            await self.event_queue.put({
                "content": chunk_text
            })
```

Key concepts:
- An **asyncio.Queue** is used to collect events from both the LLM and agents
- Agents send events to the queue when they're called or return responses
- The LLM streams chunks of text through the `get_streaming_chat_message_content` method
- Each chunk is yielded to the API layer as it arrives
- The API layer converts these events to Server-Sent Events (SSE) for the client

### 4. Group Chat Implementation

The `AgentGroupChat` class handles coordinated conversations between multiple agents:

```python
class AgentGroupChat:
    def __init__(self, agents: List[AgentPlugin], 
                 termination_strategy: Optional[AgentTerminationStrategy] = None):
        self.agents = agents
        self.termination_strategy = termination_strategy or AgentTerminationStrategy()
        self.messages = []
    
    async def process_query(self, query: str, user_id: str = "user", 
                           conversation_id: Optional[str] = None, 
                           verbose: bool = False) -> Dict[str, Any]:
        # Add the user query to messages
        self.messages.append({
            "role": "user",
            "content": query,
            "sender_id": user_id
        })
        
        agent_responses = []
        iteration = 0
        
        # Iterate until termination strategy says to stop
        while not self.termination_strategy.should_terminate(iteration, self.messages):
            iteration += 1
            
            # Process the query with each agent
            for agent in self.agents:
                try:
                    # Call the agent
                    response = await agent.call_agent(
                        query=query,
                        sender_id=user_id,
                        conversation_id=conversation_id
                    )
                    
                    # Add response to messages and agent_responses
                    self.messages.append({
                        "role": "assistant",
                        "content": response,
                        "sender_id": agent.id
                    })
                    
                    agent_responses.append({
                        "agent_id": agent.id,
                        "response": response
                    })
                except Exception as e:
                    # Handle errors
                    print(f"Error calling agent {agent.id}: {e}")
            
        # Generate a combined response
        combined_response = self._combine_responses(agent_responses)
        
        # Return the final result
        return {
            "messageId": str(uuid.uuid4()),
            "conversationId": conversation_id or str(uuid.uuid4()),
            "senderId": "agent-runtime",
            "recipientId": user_id,
            "content": combined_response,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "Text",
            "agent_responses": agent_responses,
            "agents_used": [response["agent_id"] for response in agent_responses]
        }
```

Key concepts:
- The group chat manages interactions between **multiple agents**
- A **termination strategy** determines when to stop the conversation
- Each agent is called with the same query
- Responses are collected and combined
- The runtime tracks which agents were used

## Agent Registry Concept

While our current implementation uses a simple JSON file (`agents.json`) for configuration, the architecture includes an **Agent Registry** as a first-class component:

```
┌────────────────────────────────────────────────────────────────┐
│                       Agent Registry                           │
│                                                                │
│  ┌───────────────┐      ┌──────────────┐    ┌───────────────┐  │
│  │  Agent        │      │  Agent       │    │  Runtime      │  │
│  │  Metadata     │      │  Groups      │    │  Configs      │  │
│  └───────────────┘      └──────────────┘    └───────────────┘  │
│                                                                │
│                       ┌───────────────────┐                    │
│                       │  Registry API     │                    │
│                       └───────────────────┘                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

The Agent Registry provides:
1. **Discovery**: Finding agents based on their descriptions and functions
2. **Metadata**: Information about agent parameters and details
3. **Groups**: Pre-defined collections of agents that work well together
4. **Configuration**: Runtime settings for different environments

## Integration with Semantic Kernel's Chat Completion

The runtime uses Semantic Kernel's chat completion to determine which agents to call:

```python
def initialize_kernel(self):
    """Initialize the semantic kernel with OpenAI chat completion."""
    try:
        # Create a new kernel
        self.kernel = sk.Kernel()
        
        # Add the OpenAI chat completion service
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Add the chat service
        self.kernel.add_service(
            OpenAIChatCompletion(
                service_id="chat-completion",
                api_key=api_key,
                model_id="gpt-3.5-turbo"
            )
        )
        
        return True
    except Exception as e:
        print(f"Error initializing kernel: {e}")
        return False
```

The key benefit of this approach is that we delegate the intelligence about **which agent to call** to the LLM, using function calling. This allows:

1. **Natural language routing**: Users can express their needs in plain language
2. **Intent recognition**: The LLM understands the intent behind queries
3. **Dynamic selection**: Agents are selected based on their relevance to the query
4. **Composition**: Multiple agents can be called for complex queries

## From Function Calling to Agent Orchestration

Semantic Kernel's function calling mechanic transforms into agent orchestration through these steps:

1. **Registration**: Agents register with detailed descriptions that inform selection
2. **Query Analysis**: The LLM analyzes the user's query to determine intent
3. **Function Selection**: The LLM selects the most appropriate function(s) to call
4. **Invocation**: The selected function calls the corresponding agent
5. **Response Integration**: Agent responses are integrated into the overall LLM response

This allows for a **dynamic, description-based orchestration** that's driven by natural language.

## Extensibility

The system is designed for extensibility in several ways:

1. **Adding New Agents**: Create a new agent service with an API endpoint and register it in the Agent Registry
2. **Custom Routing Logic**: Implement custom logic to override the default LLM-based routing
3. **Advanced Orchestration Patterns**: Implement more complex coordination patterns between agents
4. **Alternative LLM Providers**: Switch to different LLM providers through Semantic Kernel's abstraction

## Conclusion

Our Agent Runtime leverages Semantic Kernel to create an intelligent orchestration layer for independent agent services. The key innovations are:

1. **Agent as Functions**: Representing each agent as a Semantic Kernel function
2. **LLM-Based Routing**: Using LLMs to determine which agent(s) to call
3. **Streaming Architecture**: End-to-end streaming for responsive experiences
4. **Coordination Patterns**: Group chat and other multi-agent interaction patterns
5. **Registry-Based Discovery**: A central repository for agent metadata and configuration

This approach combines the intelligence of LLMs with the flexibility of a service-oriented architecture, allowing for sophisticated agent interactions driven by natural language. 