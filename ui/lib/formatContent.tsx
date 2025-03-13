"use client";

import { useEffect, useState } from 'react';
import katex from 'katex';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface ContentSegment {
    type: 'text' | 'latex-inline' | 'latex-block';
    content: string;
}

/**
 * Splits text into segments of regular text and LaTeX formulas
 */
export function parseContent(content: string): ContentSegment[] {
    if (!content) return [];

    const segments: ContentSegment[] = [];

    // Using an approach for multiline block LaTeX
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
    const inlinePattern = /\\\(([^]*?)\\\)/g;
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

        // If this is a block LaTeX and there's content after it, check for newlines to trim
        if (isBlock && currentIndex < content.length) {
            // Check if the next character is a newline, and skip it to avoid extra spacing
            if (content[currentIndex] === '\n') {
                currentIndex++;
                // If there's a second consecutive newline, keep it (only trim one)
                if (currentIndex < content.length && content[currentIndex] === '\n') {
                    currentIndex--;
                }
            }
        }
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
 * Component that renders content with both Markdown and LaTeX support
 */
export function ContentRenderer({ content }: { content: string }) {
    const [mounted, setMounted] = useState(false);

    // Pre-process the content to protect inline LaTeX from Markdown processing
    // This is crucial for preventing line breaks in variables
    let processedContent = content;
    if (content) {
        // Replace inline LaTeX with custom markers that won't be affected by markdown
        const uniqueId = Math.random().toString(36).substring(2, 10);
        const inlineLatexMap: Record<string, string> = {};

        // First, extract and store all inline LaTeX
        let inlineCount = 0;
        processedContent = content.replace(/\\\(([^]*?)\\\)/g, (match, latexContent) => {
            const marker = `INLINE_LATEX_${uniqueId}_${inlineCount++}`;
            inlineLatexMap[marker] = latexContent;
            return marker;
        });

        // Helper function to replace LaTeX markers with rendered LaTeX
        const replaceLatexMarkers = (text: string, componentIndex: number, id: string, latexMap: Record<string, string>) => {
            const parts: React.ReactNode[] = [];
            let lastIndex = 0;

            // Pattern to find our LaTeX markers
            const markerPattern = new RegExp(`INLINE_LATEX_${id}_\\d+`, 'g');
            let match;

            while ((match = markerPattern.exec(text)) !== null) {
                // Add text before the marker
                if (match.index > lastIndex) {
                    parts.push(text.substring(lastIndex, match.index));
                }

                // Add the LaTeX
                const marker = match[0];
                const latex = latexMap[marker];

                if (latex) {
                    // Check if it's a simple variable
                    const isSimpleVar = /^\s*[a-zA-Z0-9]\s*$/.test(latex.trim());

                    parts.push(
                        <span
                            key={`latex-${componentIndex}-${parts.length}`}
                            className={`inline-latex-wrapper ${isSimpleVar ? 'simple-var' : ''}`}
                            style={{ display: 'inline', whiteSpace: 'nowrap' }}
                        >
                            <span
                                className="inline-latex"
                                style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    verticalAlign: 'baseline',
                                    margin: '0 0.1em'
                                }}
                                dangerouslySetInnerHTML={{
                                    __html: katex.renderToString(latex, {
                                        throwOnError: false,
                                        displayMode: false
                                    })
                                }}
                            />
                        </span>
                    );
                }

                lastIndex = match.index + marker.length;
            }

            // Add remaining text
            if (lastIndex < text.length) {
                parts.push(text.substring(lastIndex));
            }

            return parts.length > 0 ? parts : text;
        };

        // Process as normal
        const segments = parseContent(processedContent);

        useEffect(() => {
            setMounted(true);

            // Add a small delay to ensure all elements are rendered before fixing layout
            setTimeout(() => {
                // After render, find all inline LaTeX elements and fix their display
                document.querySelectorAll('.inline-latex').forEach(el => {
                    el.classList.add('rendered');
                });
            }, 100);
        }, []);

        if (!mounted) {
            // Return plain content during SSR
            return <div>{content}</div>;
        }

        // Components for ReactMarkdown to keep formatting consistent
        const MarkdownComponents = {
            // Override so that we use our own styles for code blocks
            code({ node, inline, className, children, ...props }: any) {
                return (
                    <code
                        className={`${className || ''} ${inline ? 'inline-code' : 'block-code'}`}
                        {...props}
                    >
                        {children}
                    </code>
                );
            },
            // Control heading sizes to match our UI scale
            h1({ children }: any) {
                return <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>;
            },
            h2({ children }: any) {
                return <h2 className="text-lg font-bold mt-3 mb-2">{children}</h2>;
            },
            h3({ children }: any) {
                return <h3 className="text-md font-bold mt-3 mb-1">{children}</h3>;
            },
            // Handle our custom LaTeX markers
            p({ children }: any) {
                if (!children) return <p></p>;

                // Convert children to array if it's not
                const childrenArray = Array.isArray(children) ? children : [children];

                // Process each child to handle LaTeX markers
                const processedChildren = childrenArray.map((child, index) => {
                    if (typeof child !== 'string') return child;

                    // Check if this text contains any of our LaTeX markers
                    return replaceLatexMarkers(child, index, uniqueId, inlineLatexMap);
                });

                return <p>{processedChildren}</p>;
            },
            // Handle list items with LaTeX markers
            li({ children }: any) {
                if (!children) return <li></li>;

                // Convert children to array if it's not
                const childrenArray = Array.isArray(children) ? children : [children];

                // Process each child to handle LaTeX markers
                const processedChildren = childrenArray.map((child, index) => {
                    if (typeof child !== 'string') return child;

                    // Check if this text contains any of our LaTeX markers
                    return replaceLatexMarkers(child, index, uniqueId, inlineLatexMap);
                });

                return <li>{processedChildren}</li>;
            },
            // Handle table cells with LaTeX markers
            td({ children }: any) {
                if (!children) return <td></td>;

                // Convert children to array if it's not
                const childrenArray = Array.isArray(children) ? children : [children];

                // Process each child to handle LaTeX markers
                const processedChildren = childrenArray.map((child, index) => {
                    if (typeof child !== 'string') return child;

                    // Check if this text contains any of our LaTeX markers
                    return replaceLatexMarkers(child, index, uniqueId, inlineLatexMap);
                });

                return <td>{processedChildren}</td>;
            },
            // Handle table header cells with LaTeX markers
            th({ children }: any) {
                if (!children) return <th></th>;

                // Convert children to array if it's not
                const childrenArray = Array.isArray(children) ? children : [children];

                // Process each child to handle LaTeX markers
                const processedChildren = childrenArray.map((child, index) => {
                    if (typeof child !== 'string') return child;

                    // Check if this text contains any of our LaTeX markers
                    return replaceLatexMarkers(child, index, uniqueId, inlineLatexMap);
                });

                return <th>{processedChildren}</th>;
            }
        };

        return (
            <div className="latex-content markdown-content">
                {segments.map((segment, index) => {
                    if (segment.type === 'text') {
                        // Regular text with Markdown - now with our custom handling
                        return (
                            <ReactMarkdown
                                key={index}
                                remarkPlugins={[remarkGfm]}
                                components={MarkdownComponents}
                            >
                                {segment.content}
                            </ReactMarkdown>
                        );
                    } else if (segment.type === 'latex-block') {
                        // Block LaTeX - add line breaks before and after
                        return (
                            <div key={index} className="mt-2 mb-0" style={{ lineHeight: 0 }}>
                                <div style={{ lineHeight: 'normal' }}
                                    dangerouslySetInnerHTML={{
                                        __html: katex.renderToString(segment.content, {
                                            throwOnError: false,
                                            displayMode: true
                                        })
                                    }}
                                />
                            </div>
                        );
                    } else {
                        // For completeness, though we should not reach here
                        // as inline LaTeX is handled by our custom markers
                        return null;
                    }
                })}
            </div>
        );
    }

    // Default return if no content
    return <div></div>;
} 