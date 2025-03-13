"use client";

import { useRef, useState, useEffect } from "react";
import { MicIcon, StopCircleIcon } from "lucide-react";

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
    const recognitionRef = useRef<SpeechRecognition | null>(null);

    // Initialize speech recognition when component mounts
    useEffect(() => {
        // Check if the browser supports SpeechRecognition
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            setError("Speech recognition is not supported in this browser.");
            return;
        }

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
            console.error('Speech recognition error:', event.error);
            setError(`Error: ${event.error}`);
            setIsListening(false);
            setIsInitializing(false);
        };

        recognition.onend = () => {
            setIsListening(false);
        };

        recognitionRef.current = recognition;

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
            setError(null);

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

    const isButtonDisabled = disabled || isInitializing || !!error;
    const buttonTitle = error
        ? error
        : isInitializing
            ? "Initializing..."
            : isListening
                ? "Stop listening"
                : "Start voice input";

    return (
        <button
            type="button"
            onClick={toggleListening}
            disabled={isButtonDisabled}
            className={`rounded-full h-10 w-10 flex items-center justify-center text-white 
        ${isListening
                    ? 'bg-red-500 hover:bg-red-600'
                    : 'bg-[#565869] hover:bg-[#676980]'} 
        ${isButtonDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
        transition-colors`}
            title={buttonTitle}
        >
            {isListening ? (
                <StopCircleIcon className="h-5 w-5" />
            ) : (
                <MicIcon className="h-5 w-5" />
            )}
        </button>
    );
} 