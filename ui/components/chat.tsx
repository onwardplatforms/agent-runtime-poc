"use client";

import { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { ChatInput } from "@/components/chat-input";
import { AgentCallMessage, AgentResponseMessage, Message } from "@/components/message";
import { StreamChunk, streamQuery } from "@/lib/api";
import { Loader2, ArrowDown } from "lucide-react";

// Inline simplified LoadingDots component since we're removing dependencies
function LoadingDots() {
    return (
        <div className="flex items-center space-x-1">
            <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "-0.3s" }}></div>
            <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "-0.15s" }}></div>
            <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce"></div>
        </div>
    );
}

type ChatMessage = {
    id: string;
    content: string;
    role: "user" | "assistant" | "system";
    agentId?: string;
    timestamp: string;
    execution_trace?: string[];
};

type AgentCall = {
    id: string;
    agentId: string;
    query: string;
    userMessageId: string;
};

type AgentResponse = {
    id: string;
    agentId: string;
    response: string;
    userMessageId: string;
};

export function Chat() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [agentCalls, setAgentCalls] = useState<AgentCall[]>([]);
    const [agentResponses, setAgentResponses] = useState<AgentResponse[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [processingMessageIds, setProcessingMessageIds] = useState<Set<string>>(new Set());
    const [conversationId, setConversationId] = useState<string>("");
    const [isInitialized, setIsInitialized] = useState(false);
    const [currentMessageId, setCurrentMessageId] = useState<string | null>(null);
    const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
    const [isAtBottom, setIsAtBottom] = useState(true);
    const [shouldShowScrollButton, setShouldShowScrollButton] = useState(false);
    const [lastUserMessageTimestamp, setLastUserMessageTimestamp] = useState<number>(0);
    const welcomeTitleRef = useRef<HTMLHeadingElement>(null);
    const messagesContainerRef = useRef<HTMLDivElement>(null);

    // Initialize conversation
    useEffect(() => {
        setConversationId(uuidv4());
        setIsInitialized(true);
    }, []);

    // Listen for scroll events to update button state
    useEffect(() => {
        const container = messagesContainerRef.current;
        if (container) {
            const handleScroll = () => {
                if (container) {
                    const isNearBottom = container.scrollHeight - container.clientHeight - container.scrollTop < 100;
                    setIsAtBottom(isNearBottom);

                    // Don't show the scroll button right after adding a user message,
                    // and use a small debounce for showing/hiding to prevent flickering
                    const now = Date.now();
                    const timeSinceLastUserMessage = now - lastUserMessageTimestamp;
                    const shouldShow = !isNearBottom && timeSinceLastUserMessage > 300;

                    // Only update state if it would change
                    if (shouldShow !== shouldShowScrollButton) {
                        setShouldShowScrollButton(shouldShow);
                    }
                }
            };

            // Also observe size changes to recalculate scroll position
            const resizeObserver = new ResizeObserver(() => {
                console.log("Content size changed, checking scroll position");
                // When content size changes, check if we're still at the bottom
                if (container) {
                    const isNearBottom = container.scrollHeight - container.clientHeight - container.scrollTop < 100;
                    setIsAtBottom(isNearBottom);

                    // Only show scroll button if we're not at the bottom and not right after a user message
                    const now = Date.now();
                    const timeSinceLastUserMessage = now - lastUserMessageTimestamp;
                    const shouldShow = !isNearBottom && timeSinceLastUserMessage > 300;

                    setShouldShowScrollButton(shouldShow);
                }
            });

            // Observe both the container and its first child (which contains all messages)
            resizeObserver.observe(container);
            if (container.firstElementChild) {
                resizeObserver.observe(container.firstElementChild);
            }

            container.addEventListener('scroll', handleScroll);

            // Run once to initialize
            handleScroll();

            // Set up a mutation observer to detect DOM changes like expanding details
            const mutationObserver = new MutationObserver(() => {
                // Delay check slightly to allow DOM to finish updating
                setTimeout(handleScroll, 50);
            });

            // Watch for changes in the entire chat container
            mutationObserver.observe(container, {
                childList: true,
                subtree: true,
                attributes: true,
                characterData: false
            });

            return () => {
                container.removeEventListener('scroll', handleScroll);
                resizeObserver.disconnect();
                mutationObserver.disconnect();
            };
        }
    }, [messagesContainerRef.current, shouldShowScrollButton, lastUserMessageTimestamp]);

    // Handle mouse movement for parallax effect
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (messages.length > 0 || !welcomeTitleRef.current) return;

            // Get the title element's position and dimensions
            const titleElement = welcomeTitleRef.current;
            const titleRect = titleElement.getBoundingClientRect();

            // Calculate mouse position relative to the title element center
            const titleCenterX = titleRect.left + titleRect.width / 2;
            const titleCenterY = titleRect.top + titleRect.height / 2;

            // Calculate offset from center (-1 to 1 range)
            const offsetX = (e.clientX - titleCenterX) / (titleRect.width / 2);
            const offsetY = (e.clientY - titleCenterY) / (titleRect.height / 2);

            // Create gradient that follows mouse directly
            // Transform the mouse position into gradient parameters
            const gradientDirection = `${Math.round(150 + offsetX * 30)}deg`;
            const purplePosition = Math.min(Math.max(50 + offsetY * 20 + offsetX * 10, 30), 70); // Constrain between 30-70%

            // Apply only the gradient effect, no movement
            titleElement.style.backgroundImage =
                `linear-gradient(${gradientDirection}, #3b82f6 0%, #8b5cf6 ${purplePosition}%, #a855f7 100%)`;
        };

        // Reset when mouse leaves
        const handleMouseLeave = () => {
            if (welcomeTitleRef.current) {
                welcomeTitleRef.current.style.backgroundImage = 'linear-gradient(150deg, #3b82f6 0%, #8b5cf6 50%, #a855f7 100%)';
            }
        };

        window.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseleave', handleMouseLeave);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseleave', handleMouseLeave);
        };
    }, [messages.length]);

    const handleRetry = async (messageId: string) => {
        // Find the index of the message to retry from
        const messageIndex = messages.findIndex(msg => msg.id === messageId);

        if (messageIndex !== -1) {
            const messageToRetry = messages[messageIndex];

            // Reset the conversation state but don't include the message we're retrying
            // This prevents duplication when we resend
            const truncatedMessages = messages.slice(0, messageIndex);

            // Also remove any agent calls and responses associated with messages we're removing
            const messagesToKeep = new Set(truncatedMessages.map(m => m.id));
            const filteredAgentCalls = agentCalls.filter(call => messagesToKeep.has(call.userMessageId));
            const filteredAgentResponses = agentResponses.filter(resp => messagesToKeep.has(resp.userMessageId));

            setMessages(truncatedMessages);
            setAgentCalls(filteredAgentCalls);
            setAgentResponses(filteredAgentResponses);

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
        // Remove the blocking behavior if isProcessing is true
        // if (isProcessing) return;

        // Record when user message is sent to prevent button flickering
        setLastUserMessageTimestamp(Date.now());

        // Add user message
        const userMessageId = uuidv4();
        const userMessage: ChatMessage = {
            id: userMessageId,
            content,
            role: "user",
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);

        // Always force scroll to bottom when sending a new message
        setTimeout(scrollToBottom, 50);

        // Mark this specific message as processing
        setCurrentMessageId(userMessageId);
        setIsProcessing(true);
        setProcessingMessageIds(prev => {
            const newSet = new Set(prev);
            newSet.add(userMessageId);
            return newSet;
        });

        // Don't clear previous agent calls and responses
        // We'll associate new ones with the current message

        console.log("Starting to process query:", content);

        try {
            let responseContent = "";
            let executionTrace: string[] = [];

            await streamQuery(
                {
                    query: content,
                    conversation_id: conversationId,
                    stream: true,
                    verbose: true, // Enable verbose mode to get execution trace
                },
                (chunk: StreamChunk) => {
                    console.log("Received chunk:", JSON.stringify(chunk, null, 2));

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
                        // Mark this message as no longer processing
                        setProcessingMessageIds(prev => {
                            const newSet = new Set(prev);
                            newSet.delete(userMessageId);
                            if (newSet.size === 0) setIsProcessing(false);
                            return newSet;
                        });
                        return;
                    }

                    // Collect execution trace
                    if (chunk.execution_trace) {
                        executionTrace = [...executionTrace, ...chunk.execution_trace];
                        console.log("Updated execution trace:", executionTrace);
                    }

                    // Handle content updates
                    if (chunk.content) {
                        responseContent += chunk.content;
                        updateOrAddAssistantMessage(responseContent, chunk.agents_used?.[0], executionTrace);
                    }

                    // Handle agent calls - support both formats
                    if (chunk.agent_call) {
                        // Handle the object format
                        if (typeof chunk.agent_call === 'object') {
                            const { agent_id, query } = chunk.agent_call;
                            if (agent_id && query) {
                                const callId = uuidv4();
                                console.log("Adding agent call (object format):", { agent_id, query, userMessageId });
                                setAgentCalls((prev) => {
                                    const updated = [...prev, {
                                        id: callId,
                                        agentId: agent_id,
                                        query,
                                        userMessageId
                                    }];
                                    console.log("Updated agent calls:", updated);
                                    return updated;
                                });
                            } else {
                                console.warn("Received incomplete agent_call data:", chunk.agent_call);
                            }
                        }
                        // Handle the string format with agent_query
                        else if (typeof chunk.agent_call === 'string') {
                            const agent_id = chunk.agent_call;
                            // Use agent_query if available, otherwise use a default message
                            const query = chunk.agent_query || `Query to ${agent_id}`;
                            const callId = uuidv4();
                            console.log("Adding agent call (string format):", { agent_id, query, userMessageId });
                            setAgentCalls((prev) => {
                                const updated = [...prev, {
                                    id: callId,
                                    agentId: agent_id,
                                    query,
                                    userMessageId
                                }];
                                console.log("Updated agent calls:", updated);
                                return updated;
                            });
                        } else {
                            console.warn("Received unrecognized agent_call format:", chunk.agent_call);
                        }
                    }

                    // Handle agent responses - support both formats
                    if (chunk.agent_response) {
                        // Handle the object format
                        if (typeof chunk.agent_response === 'object') {
                            const { agent_id, response } = chunk.agent_response;
                            if (agent_id && response) {
                                const responseId = uuidv4();
                                console.log("Adding agent response (object format):", { agent_id, response, userMessageId });
                                setAgentResponses((prev) => {
                                    const updated = [...prev, {
                                        id: responseId,
                                        agentId: agent_id,
                                        response,
                                        userMessageId
                                    }];
                                    console.log("Updated agent responses:", updated);
                                    return updated;
                                });
                            } else {
                                console.warn("Received incomplete agent_response data:", chunk.agent_response);
                            }
                        }
                        // Handle the string format with agent_id
                        else if (typeof chunk.agent_response === 'string') {
                            // If agent_id is provided, use it, otherwise try to extract from previous agent_call
                            const agent_id = chunk.agent_id ||
                                (agentCalls.length > 0 ? agentCalls[agentCalls.length - 1].agentId : "unknown-agent");
                            const response = chunk.agent_response;
                            const responseId = uuidv4();
                            console.log("Adding agent response (string format):", { agent_id, response, userMessageId });
                            setAgentResponses((prev) => {
                                const updated = [...prev, {
                                    id: responseId,
                                    agentId: agent_id,
                                    response,
                                    userMessageId
                                }];
                                console.log("Updated agent responses:", updated);
                                return updated;
                            });
                        } else {
                            console.warn("Received unrecognized agent_response format:", chunk.agent_response);
                        }
                    }

                    // Handle final response
                    if (chunk.complete && chunk.response) {
                        responseContent = chunk.response;
                        updateOrAddAssistantMessage(responseContent, chunk.agents_used?.[0], executionTrace);
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
            console.log("Final state - Agent calls:", agentCalls);
            console.log("Final state - Agent responses:", agentResponses);

            // Mark this message as no longer processing
            setProcessingMessageIds(prev => {
                const newSet = new Set(prev);
                newSet.delete(userMessageId);
                if (newSet.size === 0) setIsProcessing(false);
                return newSet;
            });

            setCurrentMessageId(null);
        }
    };

    const updateOrAddAssistantMessage = (content: string, agentId?: string, executionTrace?: string[]) => {
        setMessages((prev) => {
            // Check if we already have an assistant message for this response
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant") {
                // Update existing message
                return prev.map((msg) =>
                    msg.id === lastMessage.id
                        ? { ...msg, content, agentId, execution_trace: executionTrace }
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
                        execution_trace: executionTrace,
                    },
                ];
            }
        });
    };

    // Group messages and agent interactions by the user message they're associated with
    const renderMessageGroups = () => {
        console.log("Rendering message groups with:", {
            messages: messages.length,
            agentCalls: agentCalls.length,
            agentResponses: agentResponses.length
        });

        const result = [];

        for (let i = 0; i < messages.length; i++) {
            const message = messages[i];

            // Add the message
            result.push(
                <Message
                    key={message.id}
                    content={message.content}
                    role={message.role}
                    agentId={message.agentId}
                    timestamp={message.timestamp}
                    messageId={message.id}
                    onRetry={message.role === "user" ? handleRetry : undefined}
                    execution_trace={message.execution_trace}
                />
            );

            // If this is a user message, show any agent calls and responses associated with it
            if (message.role === "user") {
                // Find agent calls and responses for this specific user message
                const callsForThisMessage = agentCalls.filter(call => call.userMessageId === message.id);
                const responsesForThisMessage = agentResponses.filter(resp => resp.userMessageId === message.id);

                if (callsForThisMessage.length > 0 || responsesForThisMessage.length > 0) {
                    console.log(`Displaying ${callsForThisMessage.length} agent calls and ${responsesForThisMessage.length} responses for message:`, message.content);

                    // For each agent call, display it followed by its corresponding response (if any)
                    callsForThisMessage.forEach(call => {
                        // Add the agent call
                        result.push(
                            <AgentCallMessage
                                key={call.id}
                                agentId={call.agentId}
                                query={call.query}
                            />
                        );

                        // Find and add any responses from this agent
                        const agentResponsesToShow = responsesForThisMessage.filter(
                            resp => resp.agentId === call.agentId
                        );

                        agentResponsesToShow.forEach(response => {
                            result.push(
                                <AgentResponseMessage
                                    key={response.id}
                                    agentId={response.agentId}
                                    response={response.response}
                                />
                            );
                        });
                    });

                    // Display any remaining responses that don't have a matching call
                    const displayedAgentIds = new Set(callsForThisMessage.map(call => call.agentId));
                    const remainingResponses = responsesForThisMessage.filter(
                        resp => !displayedAgentIds.has(resp.agentId)
                    );

                    remainingResponses.forEach(response => {
                        result.push(
                            <AgentResponseMessage
                                key={response.id}
                                agentId={response.agentId}
                                response={response.response}
                            />
                        );
                    });
                }
            }
        }

        return result;
    };

    // Improved scroll function with console debugging
    const scrollToBottom = () => {
        if (messagesContainerRef.current) {
            const container = messagesContainerRef.current;

            // Using a smoother scroll behavior
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });

            // Update button state after scrolling
            setIsAtBottom(true);
            setShouldShowScrollButton(false);
        }
    };

    // Auto-scroll when new messages are added
    useEffect(() => {
        // Only auto-scroll if we were already at the bottom or within 300ms of a new user message
        const timeSinceLastUserMessage = Date.now() - lastUserMessageTimestamp;
        const isUserMessageRecent = timeSinceLastUserMessage < 300;

        if ((isAtBottom || isUserMessageRecent) && messagesContainerRef.current) {
            scrollToBottom();
        }
    }, [messages, agentCalls, agentResponses, isAtBottom, lastUserMessageTimestamp]);

    // Log container dimensions on mount and when messages change
    useEffect(() => {
        if (messagesContainerRef.current) {
            const container = messagesContainerRef.current;
            console.log("Container dimensions on mount/update:", {
                scrollHeight: container.scrollHeight,
                clientHeight: container.clientHeight,
                offsetHeight: container.offsetHeight,
                containerHeight: container.getBoundingClientRect().height,
                messages: messages.length
            });
        }
    }, [messages.length, messagesContainerRef.current]);

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
        // Simplified container structure for better height control
        <div className="flex flex-col h-full">
            {/* Direct reference to scrollable container */}
            <div
                ref={messagesContainerRef}
                className="flex-1 overflow-y-auto px-4 pb-72 pt-4 space-y-2"
                id="messages-container"
            >
                <div className="max-w-3xl mx-auto">
                    {messages.length === 0 ? (
                        <div className="flex items-center justify-center h-[calc(100vh-200px)]">
                            <div className="text-center max-w-md p-8 relative">
                                <h2
                                    ref={welcomeTitleRef}
                                    className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent pb-1 tracking-tight"
                                >
                                    Welcome to Agent Chat
                                </h2>
                                <p className="text-xl text-gray-400 mt-4 leading-relaxed">
                                    Start a conversation by sending a message below.
                                </p>
                                <div className="mt-6 text-sm text-gray-500">
                                    <div className="flex items-center justify-center gap-2 opacity-70">
                                        <span>Try asking about math, coding, or general knowledge</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        renderMessageGroups()
                    )}

                    {/* In-line thinking indicator while processing */}
                    {isProcessing && (
                        <div className="py-4 flex">
                            <div className="max-w-[90%] text-base message-content">
                                <div className="text-sm font-medium text-blue-400 mb-2">
                                    {agentCalls.length > 0 && currentMessageId ?
                                        `Agent: ${agentCalls.filter(call => call.userMessageId === currentMessageId).slice(-1)[0]?.agentId || ""}` :
                                        "Runtime"}
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <div className="flex space-x-1.5">
                                        <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400/80" style={{ animationDelay: "0s" }}></div>
                                        <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400/80" style={{ animationDelay: "0.2s" }}></div>
                                        <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400/80" style={{ animationDelay: "0.4s" }}></div>
                                    </div>
                                    <span className="text-gray-300">Thinking</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Scroll to bottom button with styling matching the send button */}
            {messages.length > 0 && shouldShowScrollButton && (
                <div className="fixed bottom-[180px] left-1/2 transform -translate-x-1/2 z-30">
                    <button
                        id="scroll-to-bottom-button"
                        onClick={scrollToBottom}
                        className="rounded-full h-10 w-10 flex items-center justify-center bg-white text-[#343541] hover:bg-gray-200 shadow-md transition-colors"
                        aria-label="Scroll to bottom"
                        type="button"
                    >
                        <ArrowDown className="h-5 w-5 stroke-[3]" />
                    </button>
                </div>
            )}

            {/* Position the input at the bottom with a fixed position */}
            <div className="fixed bottom-0 left-0 right-0">
                {/* Improved gradient fade with multiple steps for a seamless transition */}
                <div className="absolute inset-0 pointer-events-none bg-gradient-to-t from-[#343541] via-[#343541]/95 via-[#343541]/80 via-[#343541]/50 via-[#343541]/30 to-transparent h-48"></div>

                {/* Input container */}
                <div className="border-t border-[#40414f] bg-[#343541] pt-4 pb-6">
                    <div className="max-w-3xl mx-auto px-4">
                        <ChatInput
                            onSend={handleSendMessage}
                            placeholder="Ask me anything..."
                        />
                    </div>
                </div>
            </div>
        </div>
    );
} 