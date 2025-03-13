"use client";

import { useRef, useState } from "react";
import { ArrowUpIcon, SquareIcon } from "lucide-react";

type ChatInputProps = {
    onSend: (message: string) => void;
    onStop?: () => void;
    isProcessing?: boolean;
    disabled?: boolean;
    placeholder?: string;
};

export function ChatInput({
    onSend,
    onStop,
    isProcessing = false,
    disabled = false,
    placeholder = "Message..."
}: ChatInputProps) {
    const [input, setInput] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || disabled || isProcessing) return;

        onSend(input);
        setInput("");

        // Reset textarea height
        if (textareaRef.current) {
            textareaRef.current.style.height = "80px";
        }
    };

    const handleStop = () => {
        if (onStop) {
            onStop();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e as unknown as React.FormEvent);
        }
    };

    const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setInput(e.target.value);

        // Auto-resize textarea
        if (textareaRef.current) {
            textareaRef.current.style.height = "80px";
            const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
            textareaRef.current.style.height = `${newHeight}px`;
        }
    };

    return (
        <form onSubmit={handleSubmit} className="relative">
            <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                className="w-full min-h-[120px] max-h-[240px] resize-none rounded-3xl border-0 bg-[#40414f] px-6 py-5 pr-14 text-white text-base placeholder:text-gray-400 focus:outline-none"
                rows={1}
                style={{ height: "80px" }}
            />
            {isProcessing ? (
                <button
                    type="button"
                    onClick={handleStop}
                    className="absolute right-4 bottom-[22px] rounded-full h-10 w-10 flex items-center justify-center bg-white text-[#343541] hover:bg-gray-200 transition-colors"
                    title="Stop processing"
                >
                    <SquareIcon className="h-4 w-4 stroke-[3]" />
                </button>
            ) : (
                <button
                    type="submit"
                    disabled={disabled || !input.trim()}
                    className="absolute right-4 bottom-[22px] rounded-full h-10 w-10 flex items-center justify-center bg-white text-[#343541] hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                    <ArrowUpIcon className="h-5 w-5 stroke-[3]" />
                </button>
            )}
        </form>
    );
} 