"use client";

import { useRef, useState, useEffect } from "react";
import { StopCircleIcon, AudioWaveformIcon } from "lucide-react";

// TypeScript definitions for the Web Speech API
interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
    resultIndex: number;
    error: any;
}

interface SpeechRecognitionResultList {
    readonly length: number;
    item(index: number): SpeechRecognitionResult;
    [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
    readonly length: number;
    item(index: number): SpeechRecognitionAlternative;
    [index: number]: SpeechRecognitionAlternative;
    isFinal?: boolean;
}

interface SpeechRecognitionAlternative {
    transcript: string;
    confidence: number;
}

interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start(): void;
    stop(): void;
    abort(): void;
    onresult: (event: SpeechRecognitionEvent) => void;
    onerror: (event: SpeechRecognitionEvent) => void;
    onstart: (event: Event) => void;
    onend: (event: Event) => void;
}

interface SpeechRecognitionConstructor {
    new(): SpeechRecognition;
}

// Extend the Window interface to include the Speech Recognition API
declare global {
    interface Window {
        SpeechRecognition?: SpeechRecognitionConstructor;
        webkitSpeechRecognition?: SpeechRecognitionConstructor;
    }
}

type WebSpeechRecognitionProps = {
    onTranscriptionComplete: (text: string) => void;
    disabled?: boolean;
};

export function WebSpeechRecognition({
    onTranscriptionComplete,
    disabled = false
}: WebSpeechRecognitionProps) {
    const [isListening, setIsListening] = useState(false);
    const [isInitializing, setIsInitializing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showTooltip, setShowTooltip] = useState(false);
    const recognitionRef = useRef<SpeechRecognition | null>(null);

    // Initialize speech recognition when component mounts
    useEffect(() => {
        // Check if the browser supports SpeechRecognition
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            setError("Speech recognition is not supported in this browser.");
            return;
        }

        const initRecognition = () => {
            // Initialize SpeechRecognition
            const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognitionAPI) {
                setError("Speech recognition is not supported in this browser.");
                return;
            }

            const recognition = new SpeechRecognitionAPI();
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onstart = () => {
                setIsListening(true);
                setIsInitializing(false);
                setError(null); // Clear any errors when starting
            };

            recognition.onresult = (event: SpeechRecognitionEvent) => {
                const transcript = Array.from(event.results)
                    .map(result => result[0])
                    .map(result => result.transcript)
                    .join('');

                if (event.results[0].isFinal) {
                    onTranscriptionComplete(transcript);
                }
            };

            recognition.onerror = (event: SpeechRecognitionEvent) => {
                // Only log and set error for non-aborted cases
                if (event.error !== 'aborted') {
                    console.error('Speech recognition error:', event.error);
                    setError(`Error: ${event.error}`);
                }
                setIsListening(false);
                setIsInitializing(false);
            };

            recognition.onend = () => {
                setIsListening(false);
                // We don't set an error here, so the button stays enabled
            };

            recognitionRef.current = recognition;
        };

        initRecognition();

        // Clean up on unmount
        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.abort();
            }
        };
    }, [onTranscriptionComplete]);

    const toggleListening = () => {
        if (isListening) {
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
        } else {
            setIsInitializing(true);
            setError(null); // Clear any errors when starting

            try {
                if (recognitionRef.current) {
                    recognitionRef.current.start();
                }
            } catch (err) {
                console.error('Failed to start speech recognition:', err);
                setError('Failed to start speech recognition');
                setIsInitializing(false);
            }
        }
    };

    // Only disable based on props or initialization state, not error
    const isButtonDisabled = disabled || isInitializing;

    const buttonTitle = error
        ? error
        : isInitializing
            ? "Initializing..."
            : isListening
                ? "Stop listening"
                : "Start voice input";

    return (
        <div className="relative">
            {/* Tooltip */}
            {showTooltip && !isListening && (
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-white text-[#343541] text-xs rounded whitespace-nowrap shadow-md">
                    Use Voice Mode
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-white"></div>
                </div>
            )}

            <button
                type="button"
                onClick={toggleListening}
                disabled={isButtonDisabled}
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                className={`rounded-full h-10 w-10 flex items-center justify-center 
                    ${isListening
                        ? 'bg-white text-[#343541] hover:bg-gray-200'
                        : 'bg-[#565869] text-white hover:bg-[#676980]'} 
                    ${isButtonDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
                    transition-colors`}
                title={buttonTitle}
            >
                {isListening ? (
                    <StopCircleIcon className="h-5 w-5" />
                ) : (
                    <AudioWaveformIcon className="h-5 w-5" />
                )}
            </button>
        </div>
    );
} 