"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

type MessageProps = {
    content: string;
    role: "user" | "assistant" | "agent" | "system";
    agentId?: string;
    timestamp?: string;
    onRetry?: (messageId: string) => void;
    messageId?: string;
};

export function Message({ content, role, agentId, timestamp, onRetry, messageId }: MessageProps) {
    const [mounted, setMounted] = useState(false);
    const [isHovering, setIsHovering] = useState(false);
    const [isButtonHovering, setIsButtonHovering] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Determine message class based on role
    const messageClass = "bg-[#343541]"; // Keep background consistent for all messages

    const handleRetry = () => {
        if (onRetry && messageId) {
            onRetry(messageId);
        }
    };

    return (
        <div className={`py-4 ${messageClass}`}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
        >
            {role === "user" ? (
                <div className="flex justify-end items-center">
                    {isHovering && onRetry && messageId && (
                        <button
                            onClick={handleRetry}
                            className="mr-2 p-1 rounded-full transition-colors"
                            title="Retry from this message"
                            aria-label="Retry from this message"
                            onMouseEnter={() => setIsButtonHovering(true)}
                            onMouseLeave={() => setIsButtonHovering(false)}
                        >
                            <div className={`rounded-full ${isButtonHovering ? 'bg-gray-500/30' : ''} p-1`}>
                                <RefreshCw
                                    size={18}
                                    className={`${isButtonHovering ? 'text-white' : 'text-gray-400'} transition-colors`}
                                />
                            </div>
                        </button>
                    )}
                    <div className="max-w-[80%] user-bubble">
                        {content}

                        {mounted && timestamp && (
                            <div className="mt-1 text-xs text-gray-400">
                                <span className="opacity-50">
                                    {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="flex">
                    <div className="max-w-[90%] text-base message-content">
                        {content}

                        {mounted && (agentId || timestamp) && (
                            <div className="mt-2 text-xs text-gray-400">
                                {agentId && (role === "assistant" || role === "agent") && (
                                    <span className="opacity-70 mr-2">Agent: {agentId}</span>
                                )}
                                {timestamp && (
                                    <span className="opacity-50">
                                        {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export function AgentCallMessage({ agentId, query }: { agentId: string; query: string }) {
    return (
        <div className="py-2">
            <div className="text-sm text-gray-400">
                <span className="font-medium text-gray-300">{agentId}</span>: {query}
            </div>
        </div>
    );
}

export function AgentResponseMessage({ agentId, response }: { agentId: string; response: string }) {
    return (
        <Message
            role="agent"
            content={response}
            agentId={agentId}
            timestamp={new Date().toISOString()}
        />
    );
} 