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

// Define a new file type for uploads
export type UploadedFile = {
    id: string;
    name: string;
    size: number;
    path: string;
    original_name: string;
    stored_name: string;
};

export type UploadResponse = {
    message: string;
    files: UploadedFile[];
    error?: string;
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

export async function streamQuery(
    request: ChatRequest,
    onChunk: (chunk: StreamChunk) => void,
    abortController?: AbortController
): Promise<void> {
    // Use the provided abortController or create a new one
    const controller = abortController || new AbortController();

    try {
        // Check API availability first
        const isAvailable = await checkApiAvailability();
        if (!isAvailable) {
            throw new Error('API server is not available. Please make sure it is running at ' + API_BASE_URL);
        }

        // Add abort listener to send cancellation signal to the server
        controller.signal.addEventListener('abort', async () => {
            try {
                console.log('Sending cancellation signal to server...');
                // Try to send cancellation signal to the backend
                await fetch(`${API_BASE_URL}/api/cancel`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        conversation_id: request.conversation_id
                    }),
                    mode: 'cors',
                    // Don't use the same abort controller for this request
                }).catch(err => console.warn('Failed to send cancellation signal:', err));
            } catch (error) {
                console.warn('Error sending cancellation to server:', error);
            }
        });

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
            signal: controller.signal, // Add the abort signal to the fetch request
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
        // Check if this was an abort error
        if (error instanceof DOMException && error.name === 'AbortError') {
            console.log('Request aborted by user');
            onChunk({
                error: 'Request aborted by user',
                complete: true
            });
        } else {
            console.error('Stream query error:', error);
            onChunk({
                error: error instanceof Error ? error.message : String(error),
                complete: true
            });
        }
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

// Add the file upload function to the API client
export async function uploadFiles(files: File[], conversationId?: string): Promise<UploadResponse> {
    try {
        console.log(`Starting file upload process for ${files.length} files`);

        // Check API availability first
        console.log("Checking API availability...");
        const isAvailable = await checkApiAvailability();
        console.log("API availability check result:", isAvailable);

        if (!isAvailable) {
            throw new Error('API server is not available. Please make sure it is running at ' + API_BASE_URL);
        }

        // Create FormData to send files
        const formData = new FormData();

        // Add each file to the form data
        for (const file of files) {
            console.log(`Adding file to FormData: ${file.name} (${file.size} bytes)`);
            formData.append('files', file);
        }

        // Add conversation ID if provided
        if (conversationId) {
            console.log(`Adding conversation_id to FormData: ${conversationId}`);
            formData.append('conversation_id', conversationId);
        }

        // Log the FormData contents
        console.log("FormData created with:",
            Array.from(formData.entries()).map(entry => {
                if (entry[1] instanceof File) {
                    return `${entry[0]}: File(${(entry[1] as File).name})`;
                }
                return `${entry[0]}: ${entry[1]}`;
            })
        );

        // First, test API accessibility with a simple GET request
        try {
            const testResponse = await fetch(`${API_BASE_URL}/`, {
                method: 'GET',
                mode: 'cors',
            });
            console.log("API reachability test:", testResponse.status, testResponse.statusText);
            if (!testResponse.ok) {
                console.warn("API is reachable but returned non-200 status");
            }
        } catch (error) {
            console.error("API reachability test failed:", error);
        }

        console.log(`Sending upload request to ${API_BASE_URL}/api/upload`);

        // Send files directly to the runtime API
        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData,
            mode: 'cors',
        });

        console.log("Upload response status:", response.status, response.statusText);

        let data;
        try {
            const textResponse = await response.text();
            console.log("Raw response text:", textResponse);
            data = JSON.parse(textResponse);
        } catch (error) {
            console.error("Failed to parse response as JSON:", error);
            throw new Error(`Failed to parse server response: ${error instanceof Error ? error.message : String(error)}`);
        }

        console.log("Upload response data:", data);

        if (!response.ok) {
            throw new Error(data.detail || data.error || `Upload failed with status: ${response.status}`);
        }

        return data as UploadResponse;
    } catch (error) {
        console.error('Error uploading files:', error);
        console.error('Error details:', error instanceof Error ? error.stack : 'No stack trace available');
        return {
            message: `Error: ${error instanceof Error ? error.message : String(error)}`,
            files: []
        };
    }
}

// Delete an uploaded file
export async function deleteFile(fileId: string, conversationId?: string): Promise<{ success: boolean; message: string }> {
    try {
        console.log(`Deleting file ${fileId} ${conversationId ? `from conversation ${conversationId}` : ''}`);

        // Build the URL with optional query parameter
        let url = `${API_BASE_URL}/api/upload/${fileId}`;
        if (conversationId) {
            url += `?conversation_id=${encodeURIComponent(conversationId)}`;
        }

        // Send the delete request
        const response = await fetch(url, {
            method: 'DELETE',
            mode: 'cors',
        });

        const data = await response.json();
        console.log("Delete response:", data);

        if (!response.ok) {
            throw new Error(data.error || `Delete failed with status: ${response.status}`);
        }

        return {
            success: true,
            message: data.message || 'File deleted successfully'
        };
    } catch (error) {
        console.error('Error deleting file:', error);
        return {
            success: false,
            message: `Error: ${error instanceof Error ? error.message : String(error)}`
        };
    }
} 