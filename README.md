# Agent Runtime POC

This project demonstrates a multi-agent architecture using a lightweight orchestration system powered by Semantic Kernel:

1. **Hello Agent** - A Python-based agent that generates greetings in different languages.
2. **Goodbye Agent** - A .NET-based agent that generates farewells in different languages.
3. **Agent Runtime** - A Python-based runtime that orchestrates interactions between agents using Semantic Kernel.

## Architecture

The system uses a three-tier architecture:

1. **Standalone Agents**: Independent microservices that provide specific capabilities
2. **Agent Runtime**: Coordinates agent interactions, routes user queries to appropriate agents using Semantic Kernel
3. **Client Applications**: CLI and API interfaces to interact with the system

## Agent Call Visibility

The system provides immediate visibility into which agents are being called using the `ƒ(x)` notation. When an agent is invoked, you'll see:

```
ƒ(x) calling the [agent-id] agent...
```

This happens in real-time as agents are called, providing transparency into the system's decision-making process.

## Testing

The project includes a comprehensive test suite for all components. For detailed information about testing, see [TESTING.md](TESTING.md).

Quick testing commands:
```bash
# Run all tests
make test

# Run tests with coverage
make test-cov
```

## Prerequisites

- Python 3.x
- .NET 7.0 or later
- OpenAI API key (set in your environment or .env files)
- `jq` command-line tool for formatting JSON responses (optional but recommended)

## Setup

### 1. Set Up Virtual Environment (Recommended)

```bash
make setup-venv
```

This will:
- Create a Python virtual environment in `.venv/`
- Install all required dependencies
- Show the installed Semantic Kernel version

To activate the virtual environment manually:
```bash
source .venv/bin/activate
```

### 2. Install Dependencies (Alternative)

If you prefer not to use a virtual environment:

```bash
make install-deps
```

### 3. Configure OpenAI API Key

Both agents and the runtime require an OpenAI API key to function. Set the key in your environment:

```bash
export OPENAI_API_KEY=your-key-here
```

Or in the respective `.env` files:
- `agents/hello_agent/.env`
- `agents/goodbye_agent/.env`
- `.env` (root directory)

## Running the System

The provided Makefile contains several targets to make working with the system easier:

### Quick Start (Recommended)

The simplest way to start the entire system is:

```bash
make interactive
```

This command:
1. Checks if agents are already running, and starts them if needed
2. Checks if the runtime is already running, and starts it if needed
3. Launches the CLI interface for interacting with the agents

### Other Run Options

```bash
# Start everything (both agents and the runtime) in the background
make start-all

# Or start components individually
make start-hello
make start-goodbye
make start-runtime

# Start the CLI interface only (if services are already running)
make cli

# Run runtime in foreground with visible logs (for development)
make runtime-cli

# Restart all services
make restart
```

### Test the Components

```bash
# Test individual components
make test-hello
make test-goodbye
make test-runtime
make test-group-chat

# Test all components
make test-all

# Check if all components are running
make status
```

### Stop Everything

```bash
make stop
```

## Using the CLI

The system includes a powerful Click-based CLI called `cli.py` that provides several ways to interact with the agents:

### Interactive Mode

```bash
./cli.py interactive
```

In interactive mode, you can:
1. Type your query to be processed (e.g., "Say hello in German and goodbye in Italian")
2. Type `agents` to list all available agents and their capabilities
3. Type `direct <agent-id>[:<param>]` to call a specific agent directly
4. Type `group <agent-id1>,<agent-id2>... <query>` to use group chat with specific agents
5. Type `exit` to quit the CLI

### Direct Commands

You can also use the CLI in non-interactive mode:

```bash
# Send a query to the runtime
./cli.py query "Say hello in Spanish and goodbye in French"

# Call a specific agent directly
./cli.py direct hello-agent "Say hello in German"

# Use group chat with specific agents
./cli.py group "hello-agent,goodbye-agent" "Provide a greeting and farewell"

# List available agents
./cli.py agents

# Check runtime status
./cli.py status
```

## Developer Documentation

For developers interested in understanding the technical details of how agent invocation works, see [DEVELOPER.md](DEVELOPER.md).

## Agent Runtime Implementation

The runtime uses Semantic Kernel's function calling capabilities to orchestrate agent interactions:

1. **Semantic Kernel Integration**: Agents are registered as functions with the Semantic Kernel, allowing the LLM to determine which agents to call based on the query.
2. **Fallback Mechanism**: If Semantic Kernel's function calling is not available, the system falls back to a keyword-based approach to determine which agents to call.
3. **Conversation History**: The system maintains conversation history for context, using Semantic Kernel's ChatHistory class.
4. **Streaming Support**: The system supports both synchronous and streaming responses.
5. **API and CLI Interfaces**: The system provides both API and CLI interfaces for interaction.

### Agent Configuration

Agents are configured in the `agents.json` file, which specifies:
- Agent ID
- Name
- Description
- Capabilities
- Endpoint URL

### API Endpoints

- `POST /api/query` - Process a user query
- `POST /api/group-chat` - Process a query using multiple agents
- `GET /api/conversations/{conversation_id}` - Get conversation history
- `GET /api/agents` - List available agents

## Individual Agent Endpoints

Each agent also has its own REST API:

- Hello Agent: `http://localhost:5001/api/message`
- Goodbye Agent: `http://localhost:5002/api/message`

## Example Messages

### Hello Agent

```json
// Request
{
  "messageId": "msg-123",
  "conversationId": "conv-456",
  "senderId": "user",
  "recipientId": "hello-agent",
  "content": "Say hello in Spanish",
  "timestamp": "2023-03-10T12:00:00Z",
  "type": "Text"
}

// Response (returned directly)
{
  "messageId": "msg-789",
  "conversationId": "conv-456",
  "senderId": "hello-agent",
  "recipientId": "user",
  "content": "¡Hola! ¿Cómo estás?",
  "timestamp": "2023-03-10T12:00:05Z",
  "type": "Text"
}
```

### Goodbye Agent

```json
// Request
{
  "messageId": "msg-789",
  "conversationId": "conv-456",
  "senderId": "user",
  "recipientId": "goodbye-agent",
  "content": "Say goodbye in French",
  "timestamp": "2023-03-10T12:00:00Z",
  "type": 0
}

// Response (returned directly)
{
  "messageId": "msg-999",
  "conversationId": "conv-456",
  "senderId": "goodbye-agent",
  "recipientId": "user",
  "content": "Au revoir et à bientôt!",
  "timestamp": "2023-03-10T12:00:05Z",
  "type": 0
}
```

**NOTE**: For the Goodbye Agent, the `type` field must be a number (0 for Text), not a string.

### Runtime Query

```json
// Request to runtime
{
  "query": "Say hello in Spanish and then say goodbye in French",
  "user_id": "user123",
  "conversation_id": "conv-456", // Optional
  "verbose": true // Optional, shows execution trace
}

// Response from runtime
{
  "messageId": "msg-abc",
  "conversationId": "conv-456",
  "senderId": "runtime",
  "recipientId": "user123",
  "content": "¡Hola! ¿Cómo estás? Au revoir et à bientôt!",
  "timestamp": "2023-03-10T12:00:10Z",
  "type": "Text",
  "execution_trace": ["Called Hello Agent", "Called Goodbye Agent"],
  "agents_used": ["hello-agent", "goodbye-agent"]
}
```

## Semantic Kernel Integration

The system uses Semantic Kernel's function calling capabilities to determine which agents to call based on the query. This is implemented in the `agent_runtime.py` file:

1. **Agent Registration**: Agents are registered as functions with the Semantic Kernel.
2. **Function Calling**: The system uses Semantic Kernel's function calling to determine which agents to call.
3. **Chat History**: The system uses Semantic Kernel's ChatHistory class to maintain conversation history.
4. **Prompt Execution Settings**: The system uses Semantic Kernel's PromptExecutionSettings to configure function calling behavior.

### Example: Processing a Query with Semantic Kernel

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

# Get the chat service
chat_service = self.kernel.get_service("chat-gpt")

# Set up function calling behavior
settings = PromptExecutionSettings()
settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

# Process the query with function calling
result = await chat_service.get_chat_message_contents(
    chat_history=chat_history,
    settings=settings,
    kernel=self.kernel
) 