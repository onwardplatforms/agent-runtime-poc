# Agent Runtime Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Client Applications                           │
│                                                                         │
│  ┌───────────────┐                                   ┌───────────────┐  │
│  │  Command-line │                                   │   Web Client  │  │
│  │  Interface    │                                   │   (Future)    │  │
│  └───────┬───────┘                                   └───────┬───────┘  │
│          │                                                   │          │
└──────────┼───────────────────────────────────────────────────┼──────────┘
           │                                                   │           
           │                   HTTP Requests                   │           
           │                                                   │           
┌──────────┼───────────────────────────────────────────────────┼──────────┐
│          ▼                                                   ▼          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                  Semantic Kernel Runtime API                    │    │
│  │                         (FastAPI)                               │    │
│  └───────────────────────────────┬─────────────────────────────────┘    │
│                                  │                                      │
│  ┌───────────────────────────────┼─────────────────────────────────┐    │
│  │                               │                                 │    │
│  │                               ▼                                 │    │
│  │  ┌────────────────────────────────────────────────────────┐    │    │
│  │  │              Semantic Kernel Core                      │    │    │
│  │  │                                                        │    │    │
│  │  │  ┌──────────────────┐      ┌─────────────────────┐    │    │    │
│  │  │  │  Agent Plugins   │      │ Function Calling    │    │    │    │
│  │  │  └──────────────────┘      └─────────────────────┘    │    │    │
│  │  │                                                        │    │    │
│  │  │  ┌──────────────────┐      ┌─────────────────────┐    │    │    │
│  │  │  │  OpenAI Service  │      │ Conversation Store  │    │    │    │
│  │  │  └──────────────────┘      └─────────────────────┘    │    │    │
│  │  └────────────────────────────────────────────────────────┘    │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                  │                                      │
│                                  │                                      │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │                                       
                                   │                                       
                                   │                                       
┌──────────────────────────────────┼──────────────────────────────────────┐
│                                  │                                      │
│  ┌────────────────┐    ┌─────────┴──────────┐    ┌─────────────────┐   │
│  │                │    │                    │    │                 │   │
│  │  Hello Agent   │◄───┤  agents.json      ├───►│  Goodbye Agent  │   │
│  │  (Python/Flask)│    │  Configuration    │    │  (.NET)         │   │
│  │                │    │                    │    │                 │   │
│  └────────────────┘    └────────────────────┘    └─────────────────┘   │
│                                                                         │
│                          Standalone Agents                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### Client Applications
- **Command-line Interface**: Interactive terminal-based client for testing and demo purposes
  - Now with `make interactive` command that automatically ensures all components are running
  - Provides commands for listing agents, viewing conversation history, and more
- **Web Client**: (Potential future addition) Browser-based interface

### Semantic Kernel Runtime
- **FastAPI REST Interface**: Exposes runtime capabilities via HTTP endpoints
- **Semantic Kernel Core**: 
  - **Agent Plugins**: Wraps agent endpoints as SK plugins/functions
  - **Function Calling**: Uses Semantic Kernel's function calling capabilities to determine which agent(s) to call
  - **OpenAI Service**: Handles LLM interactions
  - **Conversation Store**: Maintains conversation history using Semantic Kernel's ChatHistory

### Standalone Agents
- **Hello Agent**: Python/Flask-based agent for greetings
- **Goodbye Agent**: .NET-based agent for farewells
- **agents.json**: Configuration file that defines available agents and their capabilities

## Message Flow

1. User sends a query to the runtime API (directly or via CLI)
2. Runtime creates a ChatHistory with the user's query and conversation context
3. Runtime uses Semantic Kernel's function calling to determine which agent(s) to call
4. If Semantic Kernel's function calling is not available, the system falls back to a keyword-based approach
5. Runtime calls the appropriate agent(s) via their REST endpoints
6. Runtime combines agent responses and returns to the user
7. Conversation history is updated in the runtime's storage

## Semantic Kernel Integration

The system uses Semantic Kernel's function calling capabilities to determine which agents to call based on the query:

1. **Agent Registration**: Agents are registered as functions with the Semantic Kernel
2. **ChatHistory**: The system uses Semantic Kernel's ChatHistory class to maintain conversation history
3. **PromptExecutionSettings**: The system uses Semantic Kernel's PromptExecutionSettings to configure function calling behavior
4. **Function Calling**: The system uses Semantic Kernel's function calling to determine which agents to call

## Extensibility

Adding new agents is simple:
1. Create a new standalone agent with a REST endpoint
2. Add the agent's configuration to agents.json
3. Restart the runtime

The runtime will automatically load the new agent's configuration and register it as a Semantic Kernel plugin.

## CLI Interface Features

The CLI interface (`runtime_cli.py`) provides the following capabilities:
- Interactive conversation with the agent runtime
- Listing available agents and their capabilities (`agents` command)
- Viewing conversation history (`history` command)
- Simple, user-friendly terminal interface

The Makefile provides several ways to launch the CLI:
- `make interactive` - One-command solution that checks/starts all required services
- `make cli` - Starts only the CLI interface (assumes services are running)
- `make runtime-cli` - Runs the runtime in the foreground with visible logs (for development) 