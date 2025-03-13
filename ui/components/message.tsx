"use client";

import { useEffect, useState, useRef } from "react";
import { RefreshCw } from "lucide-react";
import { LatexRenderer } from "../lib/formatLatex";

type MessageProps = {
    content: string;
    role: "user" | "assistant" | "agent" | "system";
    agentId?: string;
    timestamp?: string;
    onRetry?: (messageId: string) => void;
    messageId?: string;
    execution_trace?: string[];
};

export function Message({ content, role, agentId, timestamp, onRetry, messageId, execution_trace }: MessageProps) {
    const [mounted, setMounted] = useState(false);
    const [isHovering, setIsHovering] = useState(false);
    const [isButtonHovering, setIsButtonHovering] = useState(false);
    const [showTrace, setShowTrace] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const handleRetry = () => {
        if (onRetry && messageId) {
            onRetry(messageId);
        }
    };

    const toggleTrace = () => {
        setShowTrace(!showTrace);
    };

    return (
        <div className="py-4"
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
                            <div className={`rounded-full ${isButtonHovering ? 'bg-gray-500/30' : ''} p-2`}>
                                <RefreshCw
                                    size={18}
                                    className={`${isButtonHovering ? 'text-white' : 'text-gray-400'} transition-colors`}
                                />
                            </div>
                        </button>
                    )}
                    <div className="max-w-[80%] user-bubble">
                        <LatexRenderer content={content} />

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
                        <div>
                            <div className="text-sm text-gray-400 mb-2">
                                {role === "assistant" ? "Runtime" : (agentId ? `Agent: ${agentId}` : "System")}
                            </div>
                            <div className="mt-1">
                                <LatexRenderer content={content} />
                            </div>
                        </div>

                        {execution_trace && execution_trace.length > 0 && (
                            <div className="mt-3">
                                <button
                                    onClick={toggleTrace}
                                    className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                                >
                                    {showTrace ? "Hide reasoning" : "Show reasoning"}
                                </button>

                                {showTrace && (
                                    <div className="mt-2 p-3 bg-gray-800 rounded-md text-sm text-gray-300 border border-gray-700">
                                        <div className="font-semibold mb-1 text-gray-400">Agent Reasoning:</div>
                                        <ul className="list-disc pl-5 space-y-1">
                                            {execution_trace.map((trace, index) => (
                                                <li key={index} className="text-gray-400">
                                                    <span className="text-gray-300">{trace}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}

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
        <div className="py-3">
            <div className="flex">
                <div className="max-w-[90%] text-base message-content">
                    <div className="text-sm font-medium text-gray-400 mb-2">Runtime to {agentId}</div>
                    <div className="text-gray-300">
                        <LatexRenderer content={query} />
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                        <span className="opacity-50">
                            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export function AgentResponseMessage({ agentId, response }: { agentId: string; response: string }) {
    const [isExpanded, setIsExpanded] = useState(false);

    // Calculate a preview of the response (first 50 characters)
    const getPreview = () => {
        return response.length > 50
            ? response.substring(0, 50) + " ..."
            : response;
    };

    return (
        <div className="py-3">
            <div className="flex">
                <div className="max-w-[90%] text-base message-content">
                    <div className="text-sm font-medium text-blue-400 mb-2">Agent: {agentId}</div>

                    {/* Collapsed view with preview */}
                    {!isExpanded && (
                        <div className="p-2 -ml-2">
                            <div className="text-gray-200 whitespace-pre-wrap line-clamp-2">
                                {getPreview()}
                            </div>
                            <button
                                onClick={() => setIsExpanded(true)}
                                className="text-xs text-blue-400 bg-blue-400/10 hover:bg-blue-400/20 px-3 py-1 rounded-full mt-2 transition-colors"
                            >
                                Expand
                            </button>
                        </div>
                    )}

                    {/* Expanded view with full content */}
                    {isExpanded && (
                        <div>
                            <div className="text-gray-200 whitespace-pre-wrap p-2 -ml-2">
                                <LatexRenderer content={response} />
                            </div>
                            <button
                                onClick={() => setIsExpanded(false)}
                                className="text-xs text-blue-400 bg-blue-400/10 hover:bg-blue-400/20 px-3 py-1 rounded-full mt-2 transition-colors"
                            >
                                Collapse
                            </button>
                        </div>
                    )}

                    <div className="mt-2 text-xs text-gray-500">
                        <span className="opacity-50">
                            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
} 