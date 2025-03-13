# Agent Runtime Web UI

This is the web-based user interface for the Agent Runtime system. The UI provides a modern, responsive chat interface where users can interact with the agent system and see real-time responses, including agent calls and thinking steps.

## Features

- Modern, responsive UI with dark mode
- Real-time streaming responses
- Full visibility into agent calls and execution traces
- Persistent conversation history
- Scrollable chat interface with scroll-to-bottom button
- Elegant welcome screen with interactive gradient effect
- Agent messaging system with clear visual distinction between components
- Smart conversation starters based on agent capabilities

## Getting Started

### Prerequisites

- Node.js and npm
- Agent Runtime backend running (see main README.md for instructions)

### Installation

Install dependencies:

```bash
npm install
# or from the project root
make ui-deps
```

### Development

Start the development server:

```bash
npm run dev
# or from the project root
make ui-dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

### Production Build

Build for production:

```bash
npm run build
# or from the project root
make ui-build
```

Start the production server:

```bash
npm run start
# or from the project root
make ui-start
```

## Integrated Startup

For convenience, you can start both the backend agents and the UI with a single command from the project root:

```bash
make interactive-web
# or
make start-full
```

## Technical Details

The UI is built with:

- [Next.js](https://nextjs.org) - React framework
- [Tailwind CSS](https://tailwindcss.com) - Utility-first CSS framework
- [Lucide React](https://lucide.dev) - Icon set
- [UUID](https://github.com/uuidjs/uuid) - For generating unique IDs
- Custom streaming API integration with Agent Runtime

## Conversation Starters

When starting a new chat, the UI displays suggested conversation starters to help users interact with the system. These starters come from:

1. A general "What can you do?" prompt that gives an overview of system capabilities
2. Agent-specific starters defined in `agents.json` for each agent
   
Each agent can define up to three conversation starters that showcase its capabilities. These are displayed as clickable buttons that automatically populate and send the query, providing an interactive onboarding experience.

## API Integration

The UI communicates with the Agent Runtime API at `http://localhost:5003/api/query` for processing queries. It handles:

- User message submissions
- Real-time streaming responses
- Agent call visibility
- Error handling and recovery

For full API documentation, see the main project's [API.md](../docs/API.md).
