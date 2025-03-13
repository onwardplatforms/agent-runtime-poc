"use client";

import { useEffect, useState } from 'react';
import katex from 'katex';

// Import KaTeX CSS in your main layout or page component
// import 'katex/dist/katex.min.css';

export interface LatexSegment {
    type: 'text' | 'latex-inline' | 'latex-block';
    content: string;
}

/**
 * Splits text into segments of regular text and LaTeX formulas
 */
export function parseLatexContent(content: string): LatexSegment[] {
    if (!content) return [];

    const segments: LatexSegment[] = [];

    // First, let's extract all LaTeX blocks (multiline formulas)
    const blockRegex = /\\[(\\s\\S)*?\\]/g;
    let lastIndex = 0;
    let match;

    // Using a different approach for multiline block LaTeX
    let tempContent = content;
    const blocks: { index: number, formula: string }[] = [];

    // Find all block LaTeX formulas and replace them with placeholders
    let blockMatch;
    const blockPattern = /\\\[([\s\S]*?)\\\]/g;

    while ((blockMatch = blockPattern.exec(content)) !== null) {
        const fullMatch = blockMatch[0]; // The entire match including \[ and \]
        const formula = blockMatch[1]; // Just the formula content
        const startIdx = blockMatch.index;
        const endIdx = startIdx + fullMatch.length;

        blocks.push({
            index: startIdx,
            formula: formula
        });

        // Create a placeholder for this block
        const placeholder = `__LATEX_BLOCK_${blocks.length - 1}__`;

        // Replace the LaTeX block with the placeholder
        tempContent =
            tempContent.substring(0, startIdx) +
            placeholder +
            tempContent.substring(endIdx);

        // Reset the regex to continue from the end of the placeholder
        blockPattern.lastIndex = startIdx + placeholder.length;
    }

    // Now find all inline LaTeX in the modified content
    const inlinePattern = /\\\((.*?)\\\)/g;
    const inlineMatches: { index: number, formula: string }[] = [];
    let inlineMatch;

    while ((inlineMatch = inlinePattern.exec(tempContent)) !== null) {
        const fullMatch = inlineMatch[0]; // The entire match including \( and \)
        const formula = inlineMatch[1]; // Just the formula content
        const startIdx = inlineMatch.index;

        inlineMatches.push({
            index: startIdx,
            formula: formula
        });
    }

    // Now we can rebuild the content with proper segments in order
    let currentIndex = 0;
    const allFormulas = [...blocks, ...inlineMatches].sort((a, b) => a.index - b.index);

    for (const item of allFormulas) {
        // Add text segment before the formula
        if (item.index > currentIndex) {
            const textContent = content.substring(currentIndex, item.index);
            if (textContent) {
                segments.push({
                    type: 'text',
                    content: textContent
                });
            }
        }

        // Check if this is from blocks or inlineMatches
        const isBlock = blocks.some(b => b.index === item.index);

        // Add the formula segment
        segments.push({
            type: isBlock ? 'latex-block' : 'latex-inline',
            content: item.formula
        });

        // Update current index
        const formulaLength = isBlock
            ? `\\[${item.formula}\\]`.length
            : `\\(${item.formula}\\)`.length;

        currentIndex = item.index + formulaLength;
    }

    // Add any remaining text
    if (currentIndex < content.length) {
        segments.push({
            type: 'text',
            content: content.substring(currentIndex)
        });
    }

    return segments;
}

/**
 * Component that renders LaTeX content
 */
export function LatexRenderer({ content }: { content: string }) {
    const [mounted, setMounted] = useState(false);
    const segments = parseLatexContent(content);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) {
        // Return plain content during SSR
        return <div>{content}</div>;
    }

    return (
        <div className="latex-content">
            {segments.map((segment, index) => {
                if (segment.type === 'text') {
                    // Regular text - preserve line breaks
                    return (
                        <span key={index} style={{ whiteSpace: 'pre-wrap' }}>
                            {segment.content}
                        </span>
                    );
                } else if (segment.type === 'latex-inline') {
                    // Inline LaTeX
                    return (
                        <span
                            key={index}
                            dangerouslySetInnerHTML={{
                                __html: katex.renderToString(segment.content, {
                                    throwOnError: false,
                                    displayMode: false
                                })
                            }}
                        />
                    );
                } else {
                    // Block LaTeX - add line breaks before and after
                    return (
                        <div key={index} className="my-2">
                            <div
                                dangerouslySetInnerHTML={{
                                    __html: katex.renderToString(segment.content, {
                                        throwOnError: false,
                                        displayMode: true
                                    })
                                }}
                            />
                        </div>
                    );
                }
            })}
        </div>
    );
} 