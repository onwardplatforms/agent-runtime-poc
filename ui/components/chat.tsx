"use client";

import { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { ChatInput } from "@/components/chat-input";
import { AgentCallMessage, AgentResponseMessage, Message } from "@/components/message";
import { StreamChunk, streamQuery } from "@/lib/api";
import { Loader2 } from "lucide-react";

type ChatMessage = {
    id: string;
    content: string;
    role: "user" | "assistant" | "system";
    agentId?: string;
    timestamp: string;
};

type AgentCall = {
    id: string;
    agentId: string;
    query: string;
};

type AgentResponse = {
    id: string;
    agentId: string;
    response: string;
};

export function Chat() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [agentCalls, setAgentCalls] = useState<AgentCall[]>([]);
    const [agentResponses, setAgentResponses] = useState<AgentResponse[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [conversationId, setConversationId] = useState<string>("");
    const [isInitialized, setIsInitialized] = useState(false);

    const messagesContainerRef = useRef<HTMLDivElement>(null);

    // Initialize conversation
    useEffect(() => {
        setConversationId(uuidv4());

        setIsInitialized(true);
    }, []);

    // Scroll to bottom when messages change
    useEffect(() => {
        if (messagesContainerRef.current) {
            messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
        }
    }, [messages, agentCalls, agentResponses]);

    const handleRetry = async (messageId: string) => {
        // Find the index of the message to retry from
        const messageIndex = messages.findIndex(msg => msg.id === messageId);

        if (messageIndex !== -1) {
            const messageToRetry = messages[messageIndex];

            // Keep only messages up to and including the selected message
            const truncatedMessages = messages.slice(0, messageIndex + 1);

            // Reset the conversation state
            setMessages(truncatedMessages);
            setAgentCalls([]);
            setAgentResponses([]);

            // Generate a new conversation ID to start fresh
            const newConversationId = uuidv4();
            setConversationId(newConversationId);

            // Wait a brief moment for state to update
            setTimeout(() => {
                // Resend the message
                if (messageToRetry.content) {
                    handleSendMessage(messageToRetry.content);
                }
            }, 100);
        }
    };

    const handleSendMessage = async (content: string) => {
        if (isProcessing) return;

        // Add user message
        const userMessage: ChatMessage = {
            id: uuidv4(),
            content,
            role: "user",
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setIsProcessing(true);
        setAgentCalls([]);
        setAgentResponses([]);

        try {
            let responseContent = "";

            await streamQuery(
                {
                    query: content,
                    conversation_id: conversationId,
                    stream: true,
                },
                (chunk: StreamChunk) => {
                    // Handle errors
                    if (chunk.error) {
                        setMessages((prev) => [
                            ...prev,
                            {
                                id: uuidv4(),
                                content: `Error: ${chunk.error}`,
                                role: "system",
                                timestamp: new Date().toISOString(),
                            },
                        ]);
                        setIsProcessing(false);
                        return;
                    }

                    // Handle content updates
                    if (chunk.content) {
                        responseContent += chunk.content;
                        updateOrAddAssistantMessage(responseContent);
                    }

                    // Handle agent calls
                    if (chunk.agent_call) {
                        const { agent_id, query } = chunk.agent_call;
                        if (agent_id && query) {
                            const callId = uuidv4();
                            setAgentCalls((prev) => [...prev, { id: callId, agentId: agent_id, query }]);
                        } else {
                            console.warn("Received incomplete agent_call data:", chunk.agent_call);
                        }
                    }

                    // Handle agent responses
                    if (chunk.agent_response) {
                        const { agent_id, response } = chunk.agent_response;
                        if (agent_id && response) {
                            const responseId = uuidv4();
                            setAgentResponses((prev) => [...prev, { id: responseId, agentId: agent_id, response }]);
                        } else {
                            console.warn("Received incomplete agent_response data:", chunk.agent_response);
                        }
                    }

                    // Handle final response
                    if (chunk.complete && chunk.response) {
                        responseContent = chunk.response;
                        updateOrAddAssistantMessage(responseContent, chunk.agents_used?.[0]);
                    }
                }
            );
        } catch (error) {
            console.error("Error processing query:", error);
            setMessages((prev) => [
                ...prev,
                {
                    id: uuidv4(),
                    content: `Error: ${error instanceof Error ? error.message : String(error)}`,
                    role: "system",
                    timestamp: new Date().toISOString(),
                },
            ]);
        } finally {
            setIsProcessing(false);
        }
    };

    const updateOrAddAssistantMessage = (content: string, agentId?: string) => {
        setMessages((prev) => {
            // Check if we already have an assistant message for this response
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant") {
                // Update existing message
                return prev.map((msg) =>
                    msg.id === lastMessage.id
                        ? { ...msg, content, agentId }
                        : msg
                );
            } else {
                // Add new message
                return [
                    ...prev,
                    {
                        id: uuidv4(),
                        content,
                        role: "assistant",
                        agentId,
                        timestamp: new Date().toISOString(),
                    },
                ];
            }
        });
    };

    // Show loading state while initializing
    if (!isInitialized) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Initializing chat...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col">
            {/* Message container with spacing on top and bottom */}
            <div className="flex-1 overflow-hidden py-8">
                <div
                    ref={messagesContainerRef}
                    className="h-full overflow-y-auto px-4 pb-4 space-y-2"
                >
                    <div className="max-w-3xl mx-auto">
                        {messages.map((message) => (
                            <Message
                                key={message.id}
                                content={message.content}
                                role={message.role}
                                agentId={message.agentId}
                                timestamp={message.timestamp}
                                messageId={message.id}
                                onRetry={message.role === "user" ? handleRetry : undefined}
                            />
                        ))}

                        {agentCalls && agentCalls.length > 0 && agentCalls.map((call) => (
                            <AgentCallMessage
                                key={call.id}
                                agentId={call.agentId}
                                query={call.query}
                            />
                        ))}

                        {agentResponses && agentResponses.length > 0 && agentResponses.map((response) => (
                            <AgentResponseMessage
                                key={response.id}
                                agentId={response.agentId}
                                response={response.response}
                            />
                        ))}

                        {isProcessing && !agentCalls.length && !agentResponses.length && (
                            <div className="flex w-full items-center justify-center py-4">
                                <div className="flex items-center gap-1.5 text-xs text-gray-400 w-full">
                                    <div className="flex space-x-1">
                                        <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400/40" style={{ animationDelay: "0s" }}></div>
                                        <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400/40" style={{ animationDelay: "0.2s" }}></div>
                                        <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400/40" style={{ animationDelay: "0.4s" }}></div>
                                    </div>
                                    <span>Thinking</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <ChatInput
                onSend={handleSendMessage}
                disabled={isProcessing}
                placeholder="Ask me anything..."
            />
        </div>
    );
} 