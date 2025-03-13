// API service for communicating with the runtime API

export type Message = {
    messageId: string;
    conversationId: string;
    senderId: string;
    recipientId: string;
    content: string;
    timestamp: string;
    type: string;
    execution_trace?: any[];
    agents_used?: string[];
};

export type StreamChunk = {
    content?: string;
    chunk?: string;
    complete?: boolean;
    agent_call?: {
        agent_id: string;
        query: string;
    } | string;  // Can be either an object or a string
    agent_query?: string;  // Used when agent_call is a string
    agent_response?: {
        agent_id: string;
        response: string;
    } | string;  // Can be either an object or a string
    agent_id?: string;  // Used when agent_response is a string
    response?: string;
    conversation_id?: string;
    processing_time?: number;
    agents_used?: string[];
    execution_trace?: string[];
    error?: string;
};

export type ChatRequest = {
    query: string;
    user_id?: string;
    conversation_id?: string;
    verbose?: boolean;
    stream?: boolean;
};

export type GroupChatRequest = {
    query: string;
    user_id?: string;
    conversation_id?: string;
    agent_ids?: string[];
    max_iterations?: number;
    verbose?: boolean;
    stream?: boolean;
};

const API_BASE_URL = 'http://localhost:5003';

// Check if the API is available
export async function checkApiAvailability(): Promise<boolean> {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second timeout

        // Try a GET request to /api/agents which should be lightweight
        const response = await fetch(`${API_BASE_URL}/api/agents`, {
            method: 'GET',
            signal: controller.signal,
            headers: {
                'Accept': 'application/json',
            },
            credentials: 'omit',
            mode: 'cors',
        });

        clearTimeout(timeoutId);
        return response.ok;
    } catch (error) {
        console.error('API availability check failed:', error);
        return false;
    }
}

export async function streamQuery(request: ChatRequest, onChunk: (chunk: StreamChunk) => void): Promise<void> {
    try {
        // Check API availability first
        const isAvailable = await checkApiAvailability();
        if (!isAvailable) {
            throw new Error('API server is not available. Please make sure it is running at ' + API_BASE_URL);
        }

        const response = await fetch(`${API_BASE_URL}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify({
                ...request,
                stream: true,
            }),
            credentials: 'omit',
            mode: 'cors',
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is not readable');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') break;

                    try {
                        const chunk = JSON.parse(data) as StreamChunk;
                        onChunk(chunk);
                    } catch (e) {
                        console.error('Error parsing chunk:', e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Stream query error:', error);
        onChunk({
            error: error instanceof Error ? error.message : String(error),
            complete: true
        });
    }
}

export async function streamGroupChat(request: GroupChatRequest, onChunk: (chunk: StreamChunk) => void): Promise<void> {
    try {
        // Check API availability first
        const isAvailable = await checkApiAvailability();
        if (!isAvailable) {
            throw new Error('API server is not available. Please make sure it is running at ' + API_BASE_URL);
        }

        const response = await fetch(`${API_BASE_URL}/api/group-chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify({
                ...request,
                stream: true,
            }),
            credentials: 'omit',
            mode: 'cors',
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is not readable');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') break;

                    try {
                        const chunk = JSON.parse(data) as StreamChunk;
                        onChunk(chunk);
                    } catch (e) {
                        console.error('Error parsing chunk:', e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Stream group chat error:', error);
        onChunk({
            error: error instanceof Error ? error.message : String(error),
            complete: true
        });
    }
}

// Simple test function to check if the API is running
export async function testApiConnection(): Promise<{ success: boolean; message: string }> {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(`${API_BASE_URL}/api/agents`, {
            method: 'GET',
            signal: controller.signal,
            headers: {
                'Accept': 'application/json',
            },
            credentials: 'omit',
            mode: 'cors',
        });

        clearTimeout(timeoutId);

        if (response.ok) {
            return {
                success: true,
                message: `API is connected and ready.`
            };
        } else {
            return {
                success: false,
                message: `API responded with status: ${response.status} ${response.statusText}`
            };
        }
    } catch (error) {
        return {
            success: false,
            message: `Error connecting to API: ${error instanceof Error ? error.message : String(error)}`
        };
    }
} 