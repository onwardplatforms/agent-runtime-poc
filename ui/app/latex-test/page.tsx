"use client";

import { LatexRenderer } from "../../lib/formatLatex";
import Link from "next/link";
import { ChatExample } from "./chat-example";

const testExamples = [
    "The effective rate at which the tank is being filled is \\(5 - 2 = 3\\) liters per minute. To fill a 60-liter tank at this rate, it will take \\(\\frac{60}{3} = 20\\) minutes.",

    "1. **Calculate the net rate of filling:** You have a faucet pouring in water at 5 liters per minute and a drain removing water at 2 liters per minute. Thus, the net rate is \\(5 - 2 = 3\\) liters per minute.\n\n2. **Determine the time required:** To find out how long it will take to fill the entire 60-liter tank, divide the total volume of the tank by the net rate:\n\\[\n\\text{Time} = \\frac{\\text{Tank Volume}}{\\text{Net Rate}} = \\frac{60 \\text{ liters}}{3 \\text{ liters/min}}\n\\]",

    "The quadratic formula is \\(x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\) and can be used to solve any quadratic equation of the form \\(ax^2 + bx + c = 0\\).\n\nHere is another formula, the binomial theorem:\n\\[\n(x+y)^n = \\sum_{k=0}^n {n \\choose k} x^{n-k} y^k\n\\]"
];

export default function LatexTestPage() {
    return (
        <div className="container mx-auto p-6 max-w-4xl">
            <div className="mb-6">
                <Link href="/" className="text-blue-400 hover:text-blue-300">
                    ← Back to Chat
                </Link>
            </div>

            <h1 className="text-2xl font-bold mb-6">LaTeX Rendering Test</h1>

            <ChatExample />

            <h2 className="text-xl font-bold my-6">Individual Examples</h2>
            <div className="space-y-8">
                {testExamples.map((example, index) => (
                    <div key={index} className="border border-gray-700 rounded-lg p-6 bg-[#40414f]">
                        <h2 className="text-lg font-semibold mb-3">Example {index + 1}</h2>
                        <div className="message-content">
                            <LatexRenderer content={example} />
                        </div>
                        <div className="mt-4 pt-4 border-t border-gray-700">
                            <h3 className="text-sm font-medium text-gray-400 mb-2">Raw Content:</h3>
                            <pre className="bg-gray-800 p-3 rounded text-sm overflow-x-auto">
                                {example}
                            </pre>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
} 