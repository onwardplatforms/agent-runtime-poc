"use client";

import { useEffect, useState, useRef } from "react";
import { RefreshCw } from "lucide-react";
import { ContentRenderer } from "../lib/formatContent";

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
                        <ContentRenderer content={content} />

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
                                <ContentRenderer content={content} />
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
                        <ContentRenderer content={query} />
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

    // Calculate a preview of the response by getting first two sentences
    const getPreview = () => {
        // Find the end of first two sentences by looking for .!? followed by space or end
        const sentenceRegex = /[.!?](?:\s|$)/g;
        let match;
        let endIndex = 0;
        let count = 0;

        while ((match = sentenceRegex.exec(response)) !== null) {
            count++;
            if (count >= 2) {
                endIndex = match.index + 1;
                break;
            }
        }

        // If we didn't find two sentences, or they're very short, just show first 100 chars
        if (endIndex === 0 || endIndex < 50) {
            return response.length > 100
                ? response.substring(0, 100) + " ..."
                : response;
        }

        return response.substring(0, endIndex) + (response.length > endIndex ? " ..." : "");
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
                                <ContentRenderer content={response} />
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

export function RAGRetrievalMessage({
    documentName,
    relevanceScore,
    content,
    fullContent,
    isError = false,
    errorMessage,
    summary
}: {
    documentName?: string,
    relevanceScore?: number,
    content?: string,
    fullContent?: string,
    isError?: boolean,
    errorMessage?: string,
    summary?: string
}) {
    const [isExpanded, setIsExpanded] = useState(false);

    // Format the relevance score as a percentage
    const formattedScore = relevanceScore !== undefined
        ? `${Math.round(relevanceScore * 100)}%`
        : undefined;

    return (
        <div className="py-2">
            <div className="flex">
                <div className="max-w-[90%] text-base">
                    {/* Header section */}
                    <div className="text-sm font-medium text-emerald-400 mb-1 flex items-center">
                        <span className="mr-1.5">💡</span>
                        {isError ? "Knowledge Search Error" : summary ? "Knowledge Search" : "Knowledge: " + (documentName || "Document")}
                        {formattedScore && !isError && !summary && (
                            <span className="ml-2 text-xs bg-emerald-400/10 px-2 py-0.5 rounded-full text-emerald-300">
                                Relevance: {formattedScore}
                            </span>
                        )}
                    </div>

                    {/* Error message */}
                    {isError && errorMessage && (
                        <div className="p-3 bg-red-900/30 border border-red-800/50 rounded-md text-gray-300">
                            {errorMessage}
                        </div>
                    )}

                    {/* Summary message */}
                    {summary && (
                        <div className="p-3 bg-emerald-900/20 border border-emerald-800/30 rounded-md text-gray-300">
                            {summary}
                        </div>
                    )}

                    {/* Regular document chunk */}
                    {!isError && !summary && (
                        <div className="bg-emerald-900/20 border border-emerald-800/30 rounded-md overflow-hidden">
                            {/* Collapsed view */}
                            {!isExpanded && content && (
                                <div className="p-3">
                                    <div className="text-gray-300 whitespace-pre-wrap line-clamp-2">
                                        {content}
                                    </div>
                                    <button
                                        onClick={() => setIsExpanded(true)}
                                        className="text-xs text-emerald-400 bg-emerald-400/10 hover:bg-emerald-400/20 px-3 py-1 rounded-full mt-2 transition-colors"
                                    >
                                        Show more
                                    </button>
                                </div>
                            )}

                            {/* Expanded view */}
                            {isExpanded && fullContent && (
                                <div className="p-3">
                                    <div className="text-gray-300 whitespace-pre-wrap">
                                        <ContentRenderer content={fullContent} />
                                    </div>
                                    <button
                                        onClick={() => setIsExpanded(false)}
                                        className="text-xs text-emerald-400 bg-emerald-400/10 hover:bg-emerald-400/20 px-3 py-1 rounded-full mt-2 transition-colors"
                                    >
                                        Show less
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="mt-1 text-xs text-gray-500">
                        <span className="opacity-50">
                            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
} 