#!/usr/bin/env python
"""
Test script to compare simple and semantic chunking strategies.
This script demonstrates the differences between the two chunking approaches
on a sample document with various structures.
"""

import os
import sys
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chunking_comparison")

# Add the ragapi package to the path if needed
ragapi_path = Path(".").resolve()
if str(ragapi_path) not in sys.path:
    sys.path.append(str(ragapi_path))

from ragapi.document.chunker import get_chunker
from ragapi.document.models import DocumentChunk

# Sample document with various structures to demonstrate chunking differences
SAMPLE_DOCUMENT = """# Advanced Chunking Strategies for RAG Systems

## Introduction

Text chunking is a critical component of Retrieval-Augmented Generation (RAG) systems. 
How documents are split into chunks can dramatically impact retrieval quality and the overall 
performance of a RAG application. This document explores different chunking strategies 
and their implications.

## Simple Chunking

Simple chunking divides text into fixed-size segments with specified overlap. While straightforward 
to implement, this approach has limitations:

* It may split text at arbitrary points, breaking the semantic flow
* Headings might get separated from their content
* Important context might be split across chunks

### Advantages
- Easy to implement
- Computationally efficient
- Works well for homogeneous text

## Semantic Chunking

Semantic chunking preserves the document's structure by respecting natural boundaries such as:

1. Headings and subheadings
2. Paragraphs and sentences
3. List items and tables

This approach maintains the context and coherence of the original document, improving 
retrieval quality and user experience.

### Implementation Challenges

Implementing semantic chunking requires more sophisticated text analysis:

```python
def semantic_chunking(document):
    # Identify document structure
    # Respect semantic boundaries
    # Balance chunk sizes appropriately
    return chunks
```

The complexity increases when dealing with different document formats and structures.

## Comparative Analysis

The following table summarizes the differences between chunking strategies:

| Strategy | Preserves Structure | Implementation Complexity | Retrieval Quality |
|----------|---------------------|---------------------------|-------------------|
| Simple   | No                  | Low                       | Moderate          |
| Semantic | Yes                 | High                      | High              |
| Hybrid   | Partial             | Medium                    | Good              |

## Conclusion

Choosing the right chunking strategy depends on your specific use case, document types, 
and available computational resources. For knowledge-based applications where context 
preservation is critical, semantic chunking offers significant advantages despite its 
implementation complexity.

### Future Directions

As language models continue to evolve, we expect chunking strategies to become more 
sophisticated, possibly incorporating:

* Document-specific chunking rules
* Dynamic chunk sizing based on content density
* ML-based boundary detection algorithms

The ultimate goal is to create chunks that maximize the semantic coherence and retrievability 
of the original document content.
"""

def print_banner(text):
    """Print a banner with the given text."""
    width = 80
    print("\n" + "=" * width)
    print(f"{text.center(width)}")
    print("=" * width + "\n")

def compare_chunking_strategies():
    """Compare the simple and semantic chunking strategies."""
    document_id = "test-comparison"
    
    print_banner("CHUNKING STRATEGY COMPARISON")
    
    # Create chunkers with same size parameters for fair comparison
    simple_chunker = get_chunker(
        chunk_size=300,
        chunk_overlap=50,
        use_semantic_chunking=False
    )
    
    semantic_chunker = get_chunker(
        chunk_size=300,
        chunk_overlap=50,
        use_semantic_chunking=True
    )
    
    # Create chunks using both strategies
    simple_chunks = simple_chunker.split_text(
        SAMPLE_DOCUMENT, 
        document_id, 
        {"source": "comparison_test"}
    )
    
    semantic_chunks = semantic_chunker.split_text(
        SAMPLE_DOCUMENT, 
        document_id, 
        {"source": "comparison_test"}
    )
    
    # Print summary statistics
    print(f"Document size: {len(SAMPLE_DOCUMENT)} characters")
    print(f"Simple chunking: {len(simple_chunks)} chunks generated")
    print(f"Semantic chunking: {len(semantic_chunks)} chunks generated\n")
    
    # Display chunks from both strategies
    print_banner("SIMPLE CHUNKING RESULTS")
    display_chunks(simple_chunks)
    
    print_banner("SEMANTIC CHUNKING RESULTS")
    display_chunks(semantic_chunks)
    
    # Analyze and display differences
    print_banner("ANALYSIS")
    analyze_chunk_differences(simple_chunks, semantic_chunks)

def display_chunks(chunks):
    """Display chunk information in a readable format."""
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}/{len(chunks)}:")
        print(f"  Size: {len(chunk.text)} characters")
        
        # Show metadata
        print(f"  Metadata: ", end="")
        important_metadata = {k: v for k, v in chunk.metadata.items() 
                             if k in ["segment_type", "contains_heading", "split_type"]}
        print(important_metadata)
        
        # Show first line and whether it's a heading
        first_line = chunk.text.split('\n')[0] if '\n' in chunk.text else chunk.text[:50]
        is_heading = first_line.strip().startswith('#') if first_line else False
        heading_indicator = " [HEADING]" if is_heading else ""
        print(f"  First line:{heading_indicator} {first_line[:50]}{'...' if len(first_line) > 50 else ''}")
        
        # Count headings in the chunk
        heading_count = sum(1 for line in chunk.text.split('\n') if line.strip().startswith('#'))
        if heading_count > 0:
            print(f"  Contains {heading_count} heading(s)")
        
        print()

def analyze_chunk_differences(simple_chunks, semantic_chunks):
    """Analyze and display key differences between chunking strategies."""
    # Count headings at chunk beginnings
    simple_heading_starts = sum(1 for c in simple_chunks 
                              if c.text.strip().split('\n')[0].startswith('#'))
    semantic_heading_starts = sum(1 for c in semantic_chunks 
                                if c.text.strip().split('\n')[0].startswith('#'))
    
    # Count headings in the middle of chunks (potential context breaks)
    simple_mid_headings = 0
    for chunk in simple_chunks:
        lines = chunk.text.split('\n')
        if len(lines) > 1:
            for line in lines[1:]:
                if line.strip().startswith('#'):
                    simple_mid_headings += 1
    
    semantic_mid_headings = 0
    for chunk in semantic_chunks:
        lines = chunk.text.split('\n')
        if len(lines) > 1:
            for line in lines[1:]:
                if line.strip().startswith('#'):
                    semantic_mid_headings += 1
    
    # Analyze chunk size distribution
    simple_sizes = [len(c.text) for c in simple_chunks]
    semantic_sizes = [len(c.text) for c in semantic_chunks]
    
    simple_avg_size = sum(simple_sizes) / len(simple_sizes) if simple_sizes else 0
    semantic_avg_size = sum(semantic_sizes) / len(semantic_sizes) if semantic_sizes else 0
    
    simple_size_variance = max(simple_sizes) - min(simple_sizes) if simple_sizes else 0
    semantic_size_variance = max(semantic_sizes) - min(semantic_sizes) if semantic_sizes else 0
    
    # Print analysis
    print("Heading Placement Analysis:")
    print(f"  Simple chunks with headings at start: {simple_heading_starts}/{len(simple_chunks)} " 
          f"({simple_heading_starts/len(simple_chunks)*100:.1f}%)")
    print(f"  Semantic chunks with headings at start: {semantic_heading_starts}/{len(semantic_chunks)} "
          f"({semantic_heading_starts/len(semantic_chunks)*100:.1f}%)")
    print()
    
    print("Context Break Analysis:")
    print(f"  Simple chunks with headings in the middle: {simple_mid_headings}")
    print(f"  Semantic chunks with headings in the middle: {semantic_mid_headings}")
    print()
    
    print("Chunk Size Analysis:")
    print(f"  Simple chunking - Avg size: {simple_avg_size:.1f} chars, Variance: {simple_size_variance} chars")
    print(f"  Semantic chunking - Avg size: {semantic_avg_size:.1f} chars, Variance: {semantic_size_variance} chars")
    print()
    
    print("Key Observations:")
    
    if semantic_heading_starts > simple_heading_starts:
        print("✅ Semantic chunking better preserves heading-content relationships")
    
    if simple_mid_headings > semantic_mid_headings:
        print("✅ Semantic chunking reduces context breaks by avoiding mid-chunk headings")
    
    if semantic_size_variance > simple_size_variance:
        print("ℹ️ Semantic chunking creates more varied chunk sizes to respect content boundaries")
    
    if len(semantic_chunks) != len(simple_chunks):
        print(f"ℹ️ The strategies produced different numbers of chunks " 
              f"({len(simple_chunks)} vs {len(semantic_chunks)})")

if __name__ == "__main__":
    compare_chunking_strategies() 