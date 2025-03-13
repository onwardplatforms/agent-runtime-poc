"use client";

import { Message } from "../../components/message";
import { useEffect, useState } from "react";

// Sample messages with LaTeX content
const sampleMessages = [
    {
        role: "user" as const,
        content: "How do I solve a quadratic equation?",
        timestamp: new Date().toISOString()
    },
    {
        role: "assistant" as const,
        content: "A quadratic equation in the form \\(ax^2 + bx + c = 0\\) can be solved using the quadratic formula:\n\n\\[\nx = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\n\\]\n\nThis formula gives you the two possible solutions for x, which are the roots of the quadratic equation.",
        timestamp: new Date().toISOString()
    },
    {
        role: "user" as const,
        content: "Can you explain this tank filling problem? If water flows in at 5 liters per minute, and drains at 2 liters per minute, how long will it take to fill a 60-liter tank?",
        timestamp: new Date().toISOString()
    },
    {
        role: "assistant" as const,
        content: "I'll solve this step-by-step:\n\n1. **Calculate the net rate of filling:** You have water flowing in at 5 liters per minute and draining at 2 liters per minute. The net rate is \\(5 - 2 = 3\\) liters per minute.\n\n2. **Determine the time required:** To find out how long it will take to fill the entire 60-liter tank, divide the total volume by the net rate:\n\\[\n\\text{Time} = \\frac{\\text{Tank Volume}}{\\text{Net Rate}} = \\frac{60 \\text{ liters}}{3 \\text{ liters/min}} = 20 \\text{ minutes}\n\\]\n\nTherefore, it will take 20 minutes to fill the tank.",
        timestamp: new Date().toISOString()
    }
];

export function ChatExample() {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;

    return (
        <div className="border border-gray-700 rounded-lg bg-[#343541] p-4 max-w-4xl mx-auto my-8">
            <h2 className="text-lg font-semibold mb-4 px-3">Chat Interface Preview</h2>

            <div className="space-y-0">
                {sampleMessages.map((msg, index) => (
                    <Message
                        key={index}
                        role={msg.role}
                        content={msg.content}
                        timestamp={msg.timestamp}
                    />
                ))}
            </div>
        </div>
    );
} 