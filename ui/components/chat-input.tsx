"use client";

import { useRef, useState } from "react";
import { SquareIcon, ArrowUpIcon } from "lucide-react";
import { WebSpeechRecognition } from "./web-speech-recognition";
import { FileUpload } from "./file-upload";

type ChatInputProps = {
    onSend: (message: string) => void;
    onStop?: () => void;
    onFileUpload?: (files: File[]) => void;
    isProcessing?: boolean;
    disabled?: boolean;
    placeholder?: string;
};

export function ChatInput({
    onSend,
    onStop,
    onFileUpload,
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

    const handleTranscription = (text: string) => {
        // Append new transcription to existing text instead of replacing
        setInput(currentInput => {
            // If there's existing text, add a space before new text
            const separator = currentInput.trim() ? ' ' : '';
            return currentInput + separator + text;
        });

        // Auto-resize textarea after updating with transcription
        if (textareaRef.current) {
            setTimeout(() => {
                textareaRef.current!.style.height = "80px";
                const newHeight = Math.min(textareaRef.current!.scrollHeight, 200);
                textareaRef.current!.style.height = `${newHeight}px`;
            }, 0);
        }
    };

    const handleFileSelect = (files: File[]) => {
        if (onFileUpload) {
            onFileUpload(files);
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

            {/* Left side - Upload button */}
            {onFileUpload && (
                <div className="absolute left-4 bottom-[22px]">
                    <FileUpload
                        onFileSelect={handleFileSelect}
                        disabled={disabled || isProcessing}
                    />
                </div>
            )}

            {/* Right side - Speech and Submit buttons */}
            <div className="absolute right-4 bottom-[22px] flex space-x-2">
                {/* Web Speech Recognition Button */}
                <WebSpeechRecognition
                    onTranscriptionComplete={handleTranscription}
                    disabled={disabled || isProcessing}
                />

                {isProcessing ? (
                    <button
                        type="button"
                        onClick={handleStop}
                        className="rounded-full h-10 w-10 flex items-center justify-center bg-white text-[#343541] hover:bg-gray-200 transition-colors"
                        title="Stop processing"
                    >
                        <SquareIcon className="h-4 w-4 stroke-[3]" />
                    </button>
                ) : (
                    <button
                        type="submit"
                        disabled={disabled || !input.trim()}
                        className="rounded-full h-10 w-10 flex items-center justify-center bg-white text-[#343541] hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                        <ArrowUpIcon className="h-5 w-5 stroke-[3]" />
                    </button>
                )}
            </div>
        </form>
    );
} 