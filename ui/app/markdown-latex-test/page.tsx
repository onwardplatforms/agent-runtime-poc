"use client";

import { ContentRenderer } from "../../lib/formatContent";
import Link from "next/link";

// Sample content with both Markdown and LaTeX
const sampleContent = `
# Testing Markdown with LaTeX

This example demonstrates how **Markdown** formatting works *alongside* LaTeX equations.

## Basic Markdown Features

- **Bold text** and *italic text*
- [Links](https://example.com)
- \`inline code\`

## LaTeX Examples

Inline equations like \\(E = mc^2\\) can be included within regular text.

Block equations are displayed on their own line:

\\[
\\frac{d}{dx}\\left( \\int_{a}^{x} f(t) \\, dt \\right) = f(x)
\\]

## Combined Example

Here's a table with some LaTeX equations:

| Description | Equation |
| ----------- | -------- |
| Pythagorean theorem | \\(a^2 + b^2 = c^2\\) |
| Quadratic formula | \\(x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\) |

### Code Example with Math

\`\`\`python
def calculate_area(radius):
    # Area = πr²
    return math.pi * (radius ** 2)
\`\`\`

The time complexity of quicksort is \\(O(n \\log n)\\) on average.
`;

export default function MarkdownLatexTestPage() {
    return (
        <div className="container mx-auto p-6 max-w-4xl">
            <div className="mb-6">
                <Link href="/" className="text-blue-400 hover:text-blue-300">
                    ← Back to Chat
                </Link>
            </div>

            <h1 className="text-2xl font-bold mb-6">Markdown + LaTeX Test</h1>

            <div className="border border-gray-700 rounded-lg p-6 bg-[#40414f]">
                <ContentRenderer content={sampleContent} />
            </div>

            <div className="mt-8 border-t border-gray-700 pt-6">
                <h2 className="text-xl font-bold mb-4">Raw Content</h2>
                <pre className="bg-gray-800 p-4 rounded-md text-sm overflow-x-auto whitespace-pre-wrap">
                    {sampleContent}
                </pre>
            </div>
        </div>
    );
} 