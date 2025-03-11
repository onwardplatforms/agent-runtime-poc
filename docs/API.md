# API Documentation

This document details the REST APIs provided by the Agent Runtime system.

## Runtime API Endpoints

### Process Query
```http
POST /api/query
```

Process a user query through the runtime.

**Request:**
```json
{
  "query": "Say hello in Spanish and then say goodbye in French",
  "user_id": "user123",
  "conversation_id": "conv-456", // Optional
  "verbose": true // Optional, shows execution trace
}
```

**Response:**
```json
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

### Group Chat
```http
POST /api/group-chat
```

Process a query using multiple agents.

### List Agents
```http
GET /api/agents
```

List all available agents and their capabilities.

### Get Conversation History
```http
GET /api/conversations/{conversation_id}
```

Retrieve the history of a specific conversation.

**Note**: The runtime only stores the final responses from agents, not their internal conversation histories. Each agent may maintain its own internal state and conversation history, but this is not shared back to the runtime.

## Individual Agent APIs

Each agent exposes its own REST API endpoint for direct communication.

### Hello Agent
**Endpoint:** `http://localhost:5001/api/message`

**Request:**
```json
{
  "messageId": "msg-123",
  "conversationId": "conv-456",
  "senderId": "user",
  "recipientId": "hello-agent",
  "content": "Say hello in Spanish",
  "timestamp": "2023-03-10T12:00:00Z",
  "type": "Text"
}
```

**Response:**
```json
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
**Endpoint:** `http://localhost:5002/api/message`

**Request:**
```json
{
  "messageId": "msg-789",
  "conversationId": "conv-456",
  "senderId": "user",
  "recipientId": "goodbye-agent",
  "content": "Say goodbye in French",
  "timestamp": "2023-03-10T12:00:00Z",
  "type": 0
}
```

**Response:**
```json
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

## Message Format

All messages in the system follow this standard format:

| Field            | Type          | Description                                |
| ---------------- | ------------- | ------------------------------------------ |
| `messageId`      | string        | Unique identifier for the message          |
| `conversationId` | string        | Identifier for the conversation thread     |
| `senderId`       | string        | ID of the sender (user, agent, or runtime) |
| `recipientId`    | string        | ID of the intended recipient               |
| `content`        | string        | The actual message content                 |
| `timestamp`      | string        | ISO 8601 timestamp                         |
| `type`           | string/number | Message type (Text or 0 for Goodbye Agent) |

Optional fields in responses:
- `execution_trace`: List of steps taken during processing
- `agents_used`: List of agents that contributed to the response 