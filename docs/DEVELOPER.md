# Developer Documentation

This document provides technical details about the Agent Runtime system for developers.

## Architectural Separation

The system is built with a clear separation of concerns across three distinct layers:

### 1. CLI Layer (User Interface)
- Implemented in `cli/runtime.py` and `cli/runtime_cli.py`
- Focused solely on user interaction and display formatting
- Makes HTTP requests to the API layer
- Processes streaming responses via SSE handling
- Maintains consistent formatting of interactions with "you → " and "runtime → " prefixes

### 2. API Layer (Communication)
- Implemented in `api/runtime_api.py`
- Acts as the boundary between clients and the runtime core
- Handles HTTP requests and translates them to runtime calls
- Implements Server-Sent Events (SSE) for streaming responses
- Provides a stable contract for any client to build against

### 3. Runtime Layer (Core Logic)
- Implemented in `runtime/agent_runtime.py`
- Contains all orchestration and agent handling logic
- Uses Semantic Kernel for agent selection and function calling
- Implements streaming at the LLM level for responsive interactions
- Maintains conversation history and context

## Streaming Implementation Details

The streaming implementation works across all three layers:

### Runtime Layer Streaming
```python
# In agent_runtime.py
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

### API Layer Streaming
```python
# In runtime_api.py
async def stream_query_response(query: Query, runtime: AgentRuntime):
    async for chunk in runtime.stream_process_query(
        query=query.query,
        conversation_id=query.conversation_id,
        verbose=query.verbose
    ):
        # Format and send the chunk as SSE
        if isinstance(chunk, str):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        else:
            yield f"data: {json.dumps(chunk)}\n\n"
```

### CLI Layer Streaming
```python
# In runtime.py
for line in response.iter_lines():
    if line.startswith(b'data: '):
        data_str = line[6:].decode('utf-8')
        data = json.loads(data_str)
        
        if "content" in data:
            chunk = data["content"]
            if chunk:
                # Display chunk as it arrives
                if not is_displaying_response:
                    click.echo(f"\nruntime → ", nl=False)
                    is_displaying_response = True
                
                # Stream the chunk without newline
                click.echo(chunk, nl=False)
                sys.stdout.flush()  # Force immediate display
```

## Agent Invocation Technical Flow

This section explains the technical flow of how agent invocation works in the system.

### Query Processing Flow

1. **CLI to Runtime API**
   - User input is captured in `interactive_mode()` in `runtime.py`
   - Input is displayed with "you → " prefix for consistent formatting
   - Query is sent to the runtime via `send_streaming_query()` which makes a POST request to `/api/query`
   - The FastAPI endpoint `process_query()` in `runtime_api.py` receives the request

2. **Agent Selection via Semantic Kernel**
   - The runtime's `process_query()` method in `agent_runtime.py` is called
   - It creates a `ChatHistory` object and adds the user's query
   - The query is processed by Semantic Kernel's chat service using `get_streaming_chat_message_content()`
   - Semantic Kernel determines which agent functions to call based on the query content

3. **Agent Function Calling**
   - When Semantic Kernel decides to call an agent, it invokes the `call_agent()` method of the `AgentPlugin` class
   - The `call_agent()` method is decorated with `@kernel_function` to make it available to Semantic Kernel
   - The method sets `last_called_agent` to track which agent is being called
   - It sends an event to the event queue with the agent call information: `{"agent_call": self.id}`
   - It makes an HTTP POST request to the agent's endpoint with the query

4. **Response Processing**
   - The agent processes the query and returns a response
   - The response is captured in the `call_agent()` method and returned to Semantic Kernel
   - The response is also sent to the event queue: `{"agent_id": self.id, "agent_response": response_content}`
   - As the LLM generates its response, each token is streamed to the event queue
   - The CLI displays each component of the response as it arrives

## Testing

The Agent Runtime system includes a comprehensive test suite that covers all major components. For detailed information about testing, see [TESTING.md](TESTING.md).

### Test Structure Overview

- **Unit Tests**: Tests for individual classes and methods
- **Integration Tests**: Tests for interactions between components
- **API Tests**: Tests for the FastAPI endpoints
- **CLI Tests**: Tests for the command-line interface

### Key Testing Concepts

1. **Mocking Semantic Kernel**: The tests use mock objects to simulate Semantic Kernel behavior without making actual API calls
2. **Dependency Injection**: FastAPI's dependency injection is mocked to isolate components during testing
3. **Async Testing**: Many tests use `pytest-asyncio` to handle asynchronous code
4. **Test Fixtures**: Reusable test fixtures provide consistent test environments

### Running Tests During Development

During development, it's recommended to run tests frequently to ensure changes don't break existing functionality:

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# For specific tests, you can use pytest directly
python -m pytest tests/test_agent_runtime.py
```

### Group Chat Flow

1. **Group Chat Initialization**
   - User specifies agents using the `group` command in the CLI
   - The CLI parses the agent IDs and sends them to the runtime via `send_group_chat_query()`
   - The request is received by the `/api/group-chat` endpoint

2. **Multi-Agent Processing**
   - The `AgentGroupChat` class manages the conversation between multiple agents
   - It iteratively sends the query to each specified agent
   - Each agent's response is added to the conversation history
   - The process continues until the termination strategy decides to stop

3. **Response Aggregation**
   - Responses from all agents are combined into a single coherent response
   - The `agents_used` field contains all agents that participated
   - The final response is returned to the CLI for display

### Direct Agent Calling

1. **Direct Agent Specification**
   - User specifies an agent using the `direct` command in the CLI
   - The CLI parses the agent ID and optional parameter
   - It calls the agent directly via `call_agent_directly()` without going through Semantic Kernel

2. **Direct HTTP Request**
   - The CLI constructs a message payload with the query
   - It sends an HTTP POST request directly to the agent's endpoint
   - The response is displayed to the user without runtime processing

## UI and UX Considerations

The CLI implementation follows these key UX principles:

1. **Consistent Formatting**
   - User inputs are always prefixed with "you → "
   - Runtime responses are prefixed with "runtime → "
   - Agent calls use a conversational format that shows messages between runtime and agents:
     ```
     talking with the agent(s):
      ↪ runtime to agent-id → query
      ↪ agent-id to runtime → response
     ```
   - Agent queries and responses are indented with " ↪ " prefix

2. **Real-time Feedback**
   - All events (agent calls, responses, LLM output) are displayed as they happen
   - Streaming output shows LLM responses token by token
   - Use of console output formatting (color, style) to distinguish different types of information

3. **Clear Indication of System State**
   - User always knows which component (runtime or agent) is responding
   - Agent call notation clearly shows when external systems are being invoked
   - Each conversation turn is clearly delineated

## Key Components

### AgentPlugin

The `AgentPlugin` class wraps each agent as a callable function for Semantic Kernel:

```python
class AgentPlugin:
    def __init__(self, agent_config: Dict[str, Any]):
        self.id = agent_config["id"]
        self.name = agent_config["name"]
        self.description = agent_config["description"]
        self.capabilities = agent_config["capabilities"]
        self.endpoint = agent_config["endpoint"]
        
    @kernel_function(
        description="Call the agent with the given query",
        name="call_agent"
    )
    async def call_agent(self, query: str, sender_id: str = "runtime", conversation_id: str = None) -> str:
        # Track this agent call
        global last_called_agent
        last_called_agent = self.id
        
        # Emit an agent_call event for streaming clients
        if hasattr(self, '_event_queue') and self._event_queue is not None:
            await self._event_queue.put({
                "agent_call": self.id,
                "agent_query": query
            })
        
        # Make HTTP request to agent endpoint
        # ...
        
        # Emit the agent response event for streaming clients
        if hasattr(self, '_event_queue') and self._event_queue is not None:
            await self._event_queue.put({
                "agent_id": self.id,
                "agent_response": response_content
            })
        
        return response_content
```

### AgentRuntime

The `AgentRuntime` class is the main orchestrator that manages agent registration and query processing:

```python
class AgentRuntime:
    def __init__(self, config_path: str = "agents.json"):
        self.agents = {}
        self.conversations = {}
        self.kernel = None
        self.load_config(config_path)
        self.initialize_kernel()
        self.register_agent_plugins()
        
    async def stream_process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False):
        """Stream the processing of a query, yielding chunks of the response."""
        # Create an event queue for this streaming session
        self.event_queue = asyncio.Queue()
        
        # Set event queue on agents temporarily
        for agent in self.agents.values():
            agent._event_queue = self.event_queue
        
        # Create a background task to process the query
        query_task = asyncio.create_task(self._process_query_with_events(query, conversation_id, verbose))
        
        # Yield the events from the queue as they arrive
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
```

### StreamingChatMessageContent

The system leverages Semantic Kernel's streaming capabilities:

```python
# Get the streaming result from the chat service
response_stream = chat_service.get_streaming_chat_message_content(
    chat_history=chat_history,
    settings=settings,
    kernel=self.kernel
)

# Process each chunk of the response as it arrives
async for chunk in response_stream:
    if chunk:
        # Extract the chunk text
        chunk_text = str(chunk)
        # Add to accumulated response
        full_response_content += chunk_text
        # Add each chunk to event queue for streaming to client
        await self.event_queue.put({
            "content": chunk_text
        })
```

## Debugging Tips

1. **Viewing Agent Calls**
   - Agent calls are displayed in real-time with the `ƒ(x)` notation
   - The `agents_used` field in the response contains all agents that were called
   - Debug output can be enabled with `DEBUG=True` or `export AGENT_RUNTIME_DEBUG=true`

2. **Checking Agent Registration**
   - Agents are registered as plugins with Semantic Kernel during initialization
   - The `register_agent_plugins()` method in `AgentRuntime` handles this process

3. **Streaming Observation**
   - To observe the raw streaming data, set `DEBUG=True` to see each chunk as it arrives
   - The system processes SSE format data with `data:` prefixed JSON objects

4. **Message Format**
   - All messages follow a standard format with `messageId`, `conversationId`, `senderId`, `recipientId`, `content`, `timestamp`, and `type`
   - The `generate_request()` method in `AgentPlugin` creates these messages 