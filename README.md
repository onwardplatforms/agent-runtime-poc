# Agent Runtime POC

This project demonstrates a multi-agent architecture using a lightweight orchestration system powered by Semantic Kernel:

1. **Hello Agent** - A Python-based agent that generates greetings in different languages.
2. **Goodbye Agent** - A .NET-based agent that generates farewells in different languages.
3. **Agent Runtime** - A Python-based runtime that orchestrates interactions between agents using Semantic Kernel.
4. **Web UI** - A Next.js-based user interface for interacting with the agent system.

## Architecture

The system uses a three-tier architecture:

1. **Standalone Agents**: Independent microservices that provide specific capabilities
2. **Agent Runtime**: Coordinates agent interactions using Semantic Kernel's function calling
3. **Client Applications**: CLI, Web UI, and API interfaces for natural interaction

Each layer serves a specific purpose:
- Agents focus on their specialized tasks (greetings, farewells)
- Runtime handles orchestration, routing, and conversation management
- Clients provide natural language interfaces to the system

The system features full end-to-end streaming support:
- Real-time display of LLM responses as they're generated
- Immediate visibility of agent calls and responses
- Responsive user experience with token-by-token output

## Agent Call Visibility

The system provides immediate visibility into which agents are being called using the `ƒ(x)` notation. When an agent is invoked, you'll see:

```
you → Say hello in Spanish
ƒ(x) calling hello-agent...
 ↪ runtime → hello in Spanish
 ↪ hello-agent → ¡Hola! ¿Cómo estás?

runtime → The Spanish greeting "¡Hola! ¿Cómo estás?" means "Hello! How are you?"

you → Say hello in Spanish and goodbye in French
ƒ(x) calling hello-agent...
 ↪ runtime → hello in Spanish
 ↪ hello-agent → ¡Hola! ¿Cómo estás?
ƒ(x) calling goodbye-agent...
 ↪ runtime → goodbye in French
 ↪ goodbye-agent → Au revoir et à bientôt!

runtime → In Spanish, you can say hello with "¡Hola! ¿Cómo estás?" and in French, you can say goodbye with "Au revoir et à bientôt!"
```

This real-time visibility with consistent formatting helps you understand how the system routes and processes queries.

## Testing

The project includes a test suite with all external dependencies mocked:

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run a quick demo
make demo
```

For detailed information about testing, see [TESTING.md](docs/TESTING.md).

## Prerequisites

- Python 3.11
- .NET 7.0 or later
- Node.js and npm (for the Web UI)
- `jq` command-line tool for formatting JSON responses (optional but recommended)

## Setup

### 1. Set Up Virtual Environment (Recommended)

```bash
make setup-venv
source .venv/bin/activate
```

### 2. Configure Environment

Set your OpenAI API key:
```bash
# Either in your environment:
export OPENAI_API_KEY=your-key-here

# Or in .env files:
echo "OPENAI_API_KEY=your-key-here" > .env
cp .env agents/hello_agent/.env
cp .env agents/goodbye_agent/.env
```

### 3. Install UI Dependencies (Optional, for Web UI)

```bash
make ui-deps
```

## Running the System

### Quick Start Options

```bash
# Start with CLI interface (terminal-based)
make interactive

# Start with Web UI interface (browser-based)
make interactive-web
```

### Other Run Options

```bash
# Start all backend components
make start-all

# Start all backend components and Web UI
make start-full

# Or start components individually
make start-hello
make start-goodbye
make start-runtime
make ui-dev

# Check component status
make status

# Stop everything
make stop
```

## Using the CLI

The system includes a powerful CLI that supports multiple interaction modes:

### Interactive Mode
```bash
./cli.py interactive
```

Available commands:
- Type your query directly (e.g., "Say hello in German")
- `agents` - List available agents and capabilities
- `direct <agent-id>[:<param>]` - Call specific agent
- `group <agent-id1>,<agent-id2>... <query>` - Use group chat
- `exit` - Quit the CLI

### Direct Commands
```bash
# Process a query
./cli.py query "Say hello in Spanish"

# Use group chat
./cli.py group "hello-agent,goodbye-agent" "Greet and farewell"

# Call agent directly
./cli.py direct hello-agent "Say hello in German"
```

## Using the Web UI

The web-based interface provides a modern, responsive way to interact with the agent system:

1. Start the backend components and web UI:
   ```bash
   make interactive-web
   ```

2. Open your browser to [http://localhost:3000](http://localhost:3000)

3. Type your query in the chat interface and see real-time responses including agent calls and thinking steps

Features:
- Modern, responsive UI with dark mode
- Real-time streaming responses
- Full visibility into agent calls
- Persistent conversation history
- Scrollable chat interface with scroll-to-bottom button

## Developer Documentation

For technical details about the architecture and implementation, see:
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and component details
- [DEVELOPER.md](docs/DEVELOPER.md) - Technical flows and implementation information

## Agent Runtime Implementation

The runtime uses Semantic Kernel to orchestrate agent interactions:

1. **Agent Registration**: Agents are registered as Semantic Kernel functions
2. **Function Calling**: Semantic Kernel determines which agents to call based on the query
3. **Conversation History**: System maintains context using Semantic Kernel's ChatHistory
4. **Streaming Support**: Full end-to-end streaming for responsive user experience
5. **Multiple Interfaces**: API, CLI, and Web UI access points with consistent formatting

### Agent Configuration

Agents are configured in `agents.json`:
```json
{
    "id": "hello-agent",
    "name": "Hello Agent",
    "description": "Generates greetings in different languages",
    "capabilities": ["greeting", "hello_in_different_languages"],
    "conversation_starters": [
        "Say hello in Spanish",
        "Generate a formal greeting in Japanese",
        "How do I greet someone in German?"
    ],
    "endpoint": "http://localhost:5001/api/message"
}
```

Each agent can have up to three "conversation_starters" which are example queries that showcase the agent's capabilities. These will be displayed in the Web UI to help users get started with appropriate queries.

### API Endpoints

Runtime API:
- `POST /api/query` - Process queries (supports streaming)
- `POST /api/group-chat` - Multi-agent coordination
- `GET /api/conversations/{id}` - Chat history
- `GET /api/agents` - List agents

Individual agent endpoints:
- Hello Agent: `http://localhost:5001/api/message`
- Goodbye Agent: `http://localhost:5002/api/message`

For complete API documentation, see [API.md](docs/API.md).