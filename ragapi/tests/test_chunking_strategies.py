import pytest
from unittest.mock import MagicMock
import re

from ragapi.document.chunker import (
    TextChunker, 
    SimpleChunkingStrategy, 
    SemanticChunkingStrategy,
    get_chunker
)


def test_simple_chunking_strategy():
    """Test basic functionality of SimpleChunkingStrategy."""
    strategy = SimpleChunkingStrategy(chunk_size=20, chunk_overlap=5)
    
    # Test with a paragraph of text
    text = "This is a test paragraph. It should be split into multiple chunks."
    document_id = "test-doc-1"
    metadata = {"source": "test", "title": "Test Document"}
    
    chunks = strategy.split_text(text, document_id, metadata)
    
    # Verify we got multiple chunks
    assert len(chunks) > 1
    
    # Check that each chunk has the correct metadata
    for i, chunk in enumerate(chunks):
        assert chunk.document_id == document_id
        assert chunk.metadata["source"] == metadata["source"]
        assert chunk.metadata["title"] == metadata["title"]
        assert "chunk_index" in chunk.metadata
        assert chunk.metadata["chunk_index"] == i
        assert "total_chunks" in chunk.metadata
        assert chunk.metadata["total_chunks"] == len(chunks)


def test_simple_chunking_with_paragraphs():
    """Test simple chunking strategy with multiple paragraphs."""
    strategy = SimpleChunkingStrategy(chunk_size=30, chunk_overlap=10)
    
    # Create test text with multiple paragraphs
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    document_id = "test-doc-2"
    
    chunks = strategy.split_text(text, document_id, {})
    
    # Verify the number of chunks
    assert len(chunks) > 1
    
    # For chunks other than the first, check that they start with content
    # from the previous chunk (showing overlap is working)
    for i in range(1, len(chunks)):
        prev_chunk = chunks[i-1].text
        curr_chunk = chunks[i].text
        
        # Some content from the previous chunk should appear at the beginning of this chunk
        prev_content = prev_chunk[-10:] if len(prev_chunk) > 10 else prev_chunk
        assert len(prev_content) > 0
        
        # Either the previous content is in the current chunk or
        # both chunks end/start with a segment boundary
        found_overlap = prev_content in curr_chunk
        segment_boundary = prev_chunk.endswith('\n') and curr_chunk.startswith('\n')
        assert found_overlap or segment_boundary


def test_semantic_chunking_strategy():
    """Test that SemanticChunkingStrategy respects document structure."""
    strategy = SemanticChunkingStrategy(chunk_size=150, chunk_overlap=20)
    
    # Create text with a heading and content
    text = """# Introduction
This is an introduction to the document. It should be kept together with its heading.

# Section 1
This is the first section of the document. It contains important information.

# Section 2
This is the second section with more details."""
    
    document_id = "test-doc-3"
    
    chunks = strategy.split_text(text, document_id, {})
    
    # Verify we have chunks
    assert len(chunks) > 0
    
    # Check that headings aren't on their own
    for chunk in chunks:
        chunk_text = chunk.text
        if "# " in chunk_text:
            lines = chunk_text.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("# ") and i < len(lines) - 1:
                    # The heading should have some content with it
                    next_line = lines[i+1].strip()
                    assert next_line, "Heading should have content with it"


def test_semantic_chunking_with_long_paragraphs():
    """Test semantic chunking with very long paragraphs."""
    # Create a chunker with a very small chunk size to force splitting
    strategy = SemanticChunkingStrategy(chunk_size=50, chunk_overlap=10)
    
    # Create a long paragraph that exceeds the chunk size
    long_paragraph = "This is a very long paragraph that should be split into multiple chunks because it exceeds the chunking size limit."
    
    text = f"""# Short Section
Short content.

# Long Section
{long_paragraph}"""
    
    document_id = "test-doc-4"
    
    chunks = strategy.split_text(text, document_id, {})
    
    # Verify we have multiple chunks
    assert len(chunks) >= 2
    
    # Verify the heading appears in at least one chunk
    heading_chunks = [c for c in chunks if "# Long Section" in c.text]
    assert len(heading_chunks) > 0
    
    # Verify the long paragraph content appears in the chunks
    content_parts = ["This is a very long paragraph", "should be split", "chunking size limit"]
    for part in content_parts:
        found = False
        for chunk in chunks:
            if part in chunk.text:
                found = True
                break
        assert found, f"Content part '{part}' not found in any chunk"


def test_text_chunker_factory():
    """Test that TextChunker creates the right chunking strategies."""
    # Simple chunker
    chunker = TextChunker(
        chunk_size=100,
        chunk_overlap=20,
        use_semantic_chunking=False
    )
    assert isinstance(chunker.strategy, SimpleChunkingStrategy)
    
    # Semantic chunker
    semantic_chunker = TextChunker(
        chunk_size=100,
        chunk_overlap=20,
        use_semantic_chunking=True
    )
    assert isinstance(semantic_chunker.strategy, SemanticChunkingStrategy)


def test_chunking_with_headings_detection():
    """Test that semantic chunking correctly identifies headings."""
    strategy = SemanticChunkingStrategy(chunk_size=200, chunk_overlap=20)
    
    # Text with markdown headings
    text = """# Markdown Heading 1
Content under heading 1.

## Markdown Heading 2
Content under heading 2."""
    
    document_id = "test-doc-5"
    
    chunks = strategy.split_text(text, document_id, {})
    
    # Verify chunks with markdown headings have the correct metadata
    for chunk in chunks:
        if "# " in chunk.text:
            assert "segment_type" in chunk.metadata
            assert chunk.metadata["segment_type"] == "heading" or "heading" in chunk.metadata.get("segment_types", [])


def test_get_chunker_function():
    """Test the get_chunker function."""
    # Test with default parameters
    chunker = get_chunker(chunk_size=100, chunk_overlap=20)
    assert isinstance(chunker, TextChunker)
    assert isinstance(chunker.strategy, SimpleChunkingStrategy)
    
    # Test with semantic chunking enabled
    semantic_chunker = get_chunker(
        chunk_size=100,
        chunk_overlap=20,
        use_semantic_chunking=True
    )
    assert isinstance(semantic_chunker, TextChunker)
    assert isinstance(semantic_chunker.strategy, SemanticChunkingStrategy)


def test_semantic_chunker_metadata():
    """Test that semantic chunking adds detailed metadata."""
    strategy = SemanticChunkingStrategy(chunk_size=150, chunk_overlap=20)
    
    text = """# Introduction
This is the introduction.

# Section 1
This is section 1 with important content.

# Section 2
This section has a bullet list:
* First item
* Second item"""
    
    document_id = "test-doc-6"
    metadata = {"source": "test", "author": "Test Author"}
    
    chunks = strategy.split_text(text, document_id, metadata)
    
    # Check that the chunks have detailed metadata
    for chunk in chunks:
        assert chunk.document_id == document_id
        assert chunk.metadata["source"] == metadata["source"]
        assert chunk.metadata["author"] == metadata["author"]
        assert "chunk_index" in chunk.metadata
        assert "total_chunks" in chunk.metadata
        assert "segment_type" in chunk.metadata 