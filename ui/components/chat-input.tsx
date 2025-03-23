"use client";

import { useRef, useState, useEffect } from "react";
import { SquareIcon, ArrowUpIcon, XIcon, FileIcon } from "lucide-react";
import { WebSpeechRecognition } from "./web-speech-recognition";
import { FileUpload } from "./file-upload";

type UploadedFile = {
    id: string;
    name: string;
    size: number;
    path?: string;
};

type PendingFile = {
    id: string;
    file: File;
    status: 'uploading' | 'error';
    errorMessage?: string;
};

type ChatInputProps = {
    onSend: (message: string) => void;
    onStop?: () => void;
    onFileUpload?: (files: File[]) => void;
    onFileRemove?: (fileId: string) => void;
    uploadedFiles?: UploadedFile[];
    pendingFiles?: PendingFile[];
    isProcessing?: boolean;
    disabled?: boolean;
    placeholder?: string;
};

export function ChatInput({
    onSend,
    onStop,
    onFileUpload,
    onFileRemove,
    uploadedFiles = [],
    pendingFiles = [],
    isProcessing = false,
    disabled = false,
    placeholder = "Message..."
}: ChatInputProps) {
    const [input, setInput] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileDisplayRef = useRef<HTMLDivElement>(null);
    const [localPendingFiles, setLocalPendingFiles] = useState<PendingFile[]>([]);

    // Update local pending files whenever props change
    useEffect(() => {
        setLocalPendingFiles(pendingFiles);
    }, [pendingFiles]);

    // Log uploads for debugging
    useEffect(() => {
        if (uploadedFiles.length > 0) {
            console.log("ChatInput received uploaded files:", uploadedFiles);
        }
    }, [uploadedFiles]);

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
            // Filter out any files that match those that were locally removed
            const currentPendingNames = new Set(localPendingFiles.map(pf => pf.file.name));
            const filesToUpload = files.filter(file => !currentPendingNames.has(file.name));

            if (filesToUpload.length > 0) {
                onFileUpload(filesToUpload);
            }
        }
    };

    const handleRemoveFile = (fileId: string) => {
        if (onFileRemove) {
            onFileRemove(fileId);
        }
    };

    // Format file size to readable format
    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <form onSubmit={handleSubmit} className="relative">
            {/* File display area */}
            {(uploadedFiles.length > 0 || localPendingFiles.length > 0) && (
                <div
                    ref={fileDisplayRef}
                    className="w-full bg-[#40414f] px-4 pt-3 rounded-t-3xl border-b border-gray-700/30"
                >
                    <div className="flex flex-wrap gap-2 mb-3">
                        {/* Pending files with loading or error status */}
                        {localPendingFiles.map(pendingFile => (
                            <div
                                key={pendingFile.id}
                                className={`${pendingFile.status === 'error'
                                    ? 'bg-red-900/40 border border-red-700/40'
                                    : 'bg-[#4a4b59]'} 
                                    text-white px-3 py-2 rounded-lg flex items-center gap-2 text-sm`}
                            >
                                {pendingFile.status === 'uploading' ? (
                                    <div className="h-4 w-4 text-white animate-spin">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                    </div>
                                ) : (
                                    <FileIcon className="h-4 w-4 text-blue-400" />
                                )}
                                <span className="truncate max-w-[150px]">{pendingFile.file.name}</span>
                                <span className="text-gray-400 text-xs">
                                    {pendingFile.status === 'uploading' ? (
                                        null
                                    ) : (
                                        <span className="text-red-400">{pendingFile.errorMessage || 'error'}</span>
                                    )}
                                </span>
                                <button
                                    type="button"
                                    onClick={() => {
                                        // Just remove from pending state, no need to call API
                                        setLocalPendingFiles(prev => prev.filter(pf => pf.id !== pendingFile.id));
                                    }}
                                    className="text-gray-400 hover:text-white transition-colors"
                                >
                                    <XIcon className="h-4 w-4" />
                                </button>
                            </div>
                        ))}

                        {/* Successfully uploaded files */}
                        {uploadedFiles.map(file => (
                            <div
                                key={file.id}
                                className="bg-[#4a4b59] text-white px-3 py-2 rounded-lg flex items-center gap-2 text-sm"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-4 w-4 text-emerald-400">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                                </svg>
                                <span className="truncate max-w-[150px]">{file.name}</span>
                                <span className="text-gray-400 text-xs">({formatFileSize(file.size)})</span>
                                <button
                                    type="button"
                                    onClick={() => handleRemoveFile(file.id)}
                                    className="text-gray-400 hover:text-white transition-colors"
                                >
                                    <XIcon className="h-4 w-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Message input area */}
            <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                className={`w-full min-h-[120px] max-h-[240px] resize-none border-0 bg-[#40414f] px-6 py-5 text-white text-base placeholder:text-gray-400 focus:outline-none ${(uploadedFiles.length > 0 || localPendingFiles.length > 0) ? 'rounded-b-3xl rounded-t-none' : 'rounded-3xl'}`}
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