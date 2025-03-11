# Developer Documentation

This document provides technical details about the Agent Runtime system for developers.

## Agent Invocation Technical Flow

This section explains the technical flow of how agent invocation works in the system.

### Query Processing Flow

1. **CLI to Runtime API**
   - User input is captured in `interactive_mode()` in `runtime.py`
   - Query is sent to the runtime via `send_query()` which makes a POST request to `/api/query`
   - The FastAPI endpoint `process_query()` in `runtime_api.py` receives the request

2. **Agent Selection via Semantic Kernel**
   - The runtime's `process_query()` method in `agent_runtime.py` is called
   - It creates a `ChatHistory` object and adds the user's query
   - The query is processed by Semantic Kernel's chat service using `get_chat_message_contents()`
   - Semantic Kernel determines which agent functions to call based on the query content

3. **Agent Function Calling**
   - When Semantic Kernel decides to call an agent, it invokes the `call_agent()` method of the `AgentPlugin` class
   - The `call_agent()` method is decorated with `@kernel_function` to make it available to Semantic Kernel
   - The method sets `last_called_agent` to track which agent is being called
   - It prints the agent call notification: `ƒ(x) calling the [agent-id] agent...`
   - It makes an HTTP POST request to the agent's endpoint with the query

4. **Response Processing**
   - The agent processes the query and returns a response
   - The response is captured in the `call_agent()` method and returned to Semantic Kernel
   - The runtime collects all agent responses and builds a final response message
   - The `agents_used` field in the response contains the list of agents that were called
   - The response is returned to the CLI, which displays it to the user

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
        
        # Print the agent call notification
        print(f"\nƒ(x) calling the [{self.id}] agent...")
        
        # Make HTTP request to agent endpoint
        # ...
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
        
    async def process_query(self, query: str, conversation_id: Optional[str] = None, verbose: bool = False, max_agents: int = None) -> Dict[str, Any]:
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
        
        # Process query with Semantic Kernel
        # ...
```

### ChatHistory

The `ChatHistory` class from Semantic Kernel maintains the conversation context:

```python
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
```

### PromptExecutionSettings

The `PromptExecutionSettings` class configures how Semantic Kernel handles function calling:

```python
# Set up function calling behavior
settings = PromptExecutionSettings()
settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

# Process the query with function calling
result = await chat_service.get_chat_message_contents(
    chat_history=chat_history,
    settings=settings,
    kernel=self.kernel
)
```

## Debugging Tips

1. **Viewing Agent Calls**
   - Agent calls are displayed in real-time with the `ƒ(x)` notation
   - The `agents_used` field in the response contains all agents that were called

2. **Checking Agent Registration**
   - Agents are registered as plugins with Semantic Kernel during initialization
   - The `register_agent_plugins()` method in `AgentRuntime` handles this process

3. **Fallback Mechanism**
   - If Semantic Kernel's function calling fails, the system falls back to a keyword-based approach
   - The `_fallback_process_query()` method in `AgentRuntime` implements this fallback

4. **Message Format**
   - All messages follow a standard format with `messageId`, `conversationId`, `senderId`, `recipientId`, `content`, `timestamp`, and `type`
   - The `generate_request()` method in `AgentPlugin` creates these messages 