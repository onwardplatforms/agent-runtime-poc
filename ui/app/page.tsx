"use client";

import { useEffect, useState } from "react";
import { Chat } from "@/components/chat";
import { testApiConnection } from "@/lib/api";
import { AlertCircle, Info } from "lucide-react";

export default function Home() {
    const [apiAvailable, setApiAvailable] = useState<boolean | null>(null);
    const [apiStatusMessage, setApiStatusMessage] = useState<string>("");

    useEffect(() => {
        const checkApi = async () => {
            const result = await testApiConnection();
            setApiAvailable(result.success);
            setApiStatusMessage(result.message);
        };

        checkApi();
        const interval = setInterval(checkApi, 30000);
        return () => clearInterval(interval);
    }, []);

    return (
        <main className="flex min-h-screen flex-col bg-[#343541]">
            <header className="h-10 flex items-center border-b border-[#4d4d4d] bg-[#343541]">
                <div className="max-w-3xl mx-auto px-4 w-full flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-300">Agent Chat</span>
                    <div className="flex items-center gap-1.5 text-xs text-gray-400">
                        <div className={`h-1.5 w-1.5 rounded-full ${apiAvailable === null ? 'bg-yellow-500' :
                            apiAvailable ? 'bg-[#19c37d]' : 'bg-red-500'
                            }`} />
                        <span className="opacity-70">
                            {apiAvailable === null && "Checking API..."}
                            {apiAvailable === true && "Connected"}
                            {apiAvailable === false && "API unavailable"}
                        </span>
                    </div>
                </div>
            </header>

            <div className="flex-1 relative">
                {apiAvailable === false && (
                    <div className="py-2 flex items-center justify-center gap-1.5 text-xs text-red-400">
                        <AlertCircle className="h-3.5 w-3.5" />
                        <span>API server is not available: {apiStatusMessage}</span>
                    </div>
                )}
                <Chat />
            </div>
        </main>
    );
}
