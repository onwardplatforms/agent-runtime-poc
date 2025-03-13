import React from 'react';

export function LoadingDots() {
    return (
        <div className="flex items-center space-x-1">
            <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
            <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
            <div className="h-1.5 w-1.5 bg-blue-400 rounded-full animate-bounce"></div>
        </div>
    );
} 