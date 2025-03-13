"use client";

import { useEffect, useState } from "react";

export type ChatMessageProps = {
    content: string;
    role: "user" | "agent" | "system";
    agentId?: string;
    timestamp?: string;
    className?: string;
};

export function ChatMessage({
    content,
    role,
    agentId,
    timestamp,
    className,
}: ChatMessageProps) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Keep background consistent for all messages
    const bgColor = "bg-[#343541]";

    return (
        <div className={`py-4 ${bgColor} ${className || ""}`}>
            {role === "user" ? (
                <div className="flex justify-end">
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

                        {mounted && timestamp && (
                            <div className="mt-2 text-xs text-gray-400">
                                <span className="opacity-50">
                                    {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
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
    const timestamp = new Date().toISOString();
    return (
        <ChatMessage
            role="agent"
            content={response}
            agentId={agentId}
            timestamp={timestamp}
            className=""
        />
    );
} 