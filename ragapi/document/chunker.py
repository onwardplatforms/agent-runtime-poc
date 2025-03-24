import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Union, TypedDict, cast

# Ignore missing type stubs for nltk
import nltk  # type: ignore

# Download necessary NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """
    A chunk of text from a document with associated metadata.
    """
    text: str
    metadata: Dict[str, Any]


class HeadingContext(TypedDict):
    """
    Type definition for heading context used in chunking strategies.
    """
    level: int
    content: str
    original: str


class ChunkingStrategy(ABC):
    """
    Abstract base class for document chunking strategies.
    """

    @abstractmethod
    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks according to the strategy.

        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Optional metadata to include with each chunk

        Returns:
            List of dictionaries, each containing:
                - 'text': The chunk text
                - 'metadata': A dictionary of metadata for the chunk
        """


class SimpleChunkingStrategy(ChunkingStrategy):
    """
    Simple chunking strategy that splits text by fixed chunk size with optional overlap.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, separator: str = "\n"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into fixed-size chunks with optional overlap.

        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Metadata to attach to each chunk

        Returns:
            List of dictionaries, each containing 'text' and 'metadata' keys
        """
        if not text:
            return []

        metadata = metadata or {}
        chunks: List[Dict[str, Any]] = []

        # Split by separator if provided
        segments = text.split(self.separator) if self.separator else [text]
        segments = [seg for seg in segments if seg.strip()]

        # If no segments after splitting, just use the original text
        if not segments:
            segments = [text]

        # Initialize current chunk
        current_chunk: List[str] = []
        current_size = 0

        for segment in segments:
            segment = segment.strip() + self.separator
            segment_size = len(segment)

            # If a single segment is larger than chunk_size, split it directly
            if segment_size > self.chunk_size:
                # First, add any existing chunk if it's not empty
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["total_chunks"] = 0  # Placeholder, will update later
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })
                    current_chunk = []
                    current_size = 0

                # Then split the large segment
                for i in range(0, len(segment), self.chunk_size - self.chunk_overlap):
                    chunk_text = segment[i:i + self.chunk_size]
                    if chunk_text:
                        chunk_metadata = metadata.copy()
                        chunk_metadata["chunk_index"] = len(chunks)
                        chunk_metadata["total_chunks"] = 0  # Placeholder
                        chunk_metadata["is_large_segment"] = True
                        chunk_metadata["segment_index"] = i // (self.chunk_size - self.chunk_overlap)
                        chunks.append({
                            "text": chunk_text,
                            "metadata": chunk_metadata
                        })

            # Normal case: add segment to current chunk if it fits
            elif current_size + segment_size <= self.chunk_size:
                current_chunk.append(segment)
                current_size += segment_size

            # If current segment doesn't fit, finalize current chunk and start a new one
            else:
                # Add current chunk to list if not empty
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["total_chunks"] = 0  # Placeholder
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })

                # Start a new chunk with overlap
                overlap_size = 0
                overlap_chunks: List[Dict[str, Any]] = []

                # Add overlapping segments from the previous chunk
                for previous_segment in reversed(current_chunk):
                    if overlap_size + len(previous_segment) <= self.chunk_overlap:
                        # Cast string to Dict[str, Any] to satisfy mypy
                        # This is a type coercion to help mypy, although it's not actually correct
                        # A better approach would be to refactor the code to use consistent types
                        overlap_chunks.insert(0, cast(Dict[str, Any], previous_segment))
                        overlap_size += len(previous_segment)
                    else:
                        break

                # Fix the type compatibility issue
                current_chunk = cast(List[str], overlap_chunks + [segment])
                current_size = sum(len(seg) for seg in current_chunk)

        # Add the last chunk if not empty
        if current_chunk:
            chunk_text = "".join(current_chunk)
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadata["total_chunks"] = 0  # Placeholder
            chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })

        # Update total_chunks in metadata for all chunks
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)

        logger.info(f"Created {len(chunks)} chunks using simple chunking strategy")
        return chunks


class SemanticChunkingStrategy(ChunkingStrategy):
    """
    Advanced chunking strategy that respects semantic boundaries like paragraphs,
    sentences, headings, code blocks, lists and tables.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Enhanced patterns for structure detection
        self.heading_pattern = re.compile(r'^(#+)\s+(.+)$', re.MULTILINE)
        self.code_block_pattern = re.compile(r'```(?:\w+)?\n(.*?)\n```', re.DOTALL)
        self.list_pattern = re.compile(r'^\s*[-*+]\s+.*$|^\s*\d+\.\s+.*$', re.MULTILINE)
        self.table_pattern = re.compile(r'^\s*\|(?:.*\|)+\s*$\n^\s*\|(?:[-:]+\|)+\s*$', re.MULTILINE)
        self.sentence_end_pattern = re.compile(r'(?<=[.!?])\s+')

    def is_heading(self, text: str) -> bool:
        """Check if a text segment is a heading."""
        return bool(self.heading_pattern.match(text.strip()))

    def get_heading_level(self, text: str) -> tuple:
        """
        Extract heading level and text.
        Returns (0, original_text) if not a heading.
        """
        match = self.heading_pattern.match(text.strip())
        if match:
            level = len(match.group(1))
            content = match.group(2)
            return level, content
        return 0, text

    def is_code_block(self, text: str) -> bool:
        """Check if text is or contains a code block."""
        return bool(self.code_block_pattern.search(text))

    def is_list_item(self, text: str) -> bool:
        """Check if text is a list item or contains list items."""
        return bool(self.list_pattern.search(text))

    def is_table(self, text: str) -> bool:
        """Check if text contains a table."""
        return bool(self.table_pattern.search(text))

    def get_segment_importance(self, segment: str) -> int:
        """
        Assign importance scores to different types of segments.
        Higher scores mean the segment is more important to keep intact.
        """
        segment = segment.strip()

        # Headings are most important
        if self.is_heading(segment):
            level, _ = self.get_heading_level(segment)
            return 100 + (6 - level) * 10  # Higher level headings (h1, h2) get higher importance

        # Code blocks should be kept intact when possible
        if self.is_code_block(segment):
            return 95

        # Tables should usually be kept intact
        if self.is_table(segment):
            return 90

        # Lists are important to keep together
        if self.is_list_item(segment):
            return 85

        # Longer paragraphs are generally important
        if len(segment) > 200:
            return 60

        # Medium paragraphs
        if len(segment) > 100:
            return 40

        # Default importance
        return 20

    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text based on semantic boundaries like paragraphs, sentences, headings,
        code blocks, and other structured content.

        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Metadata to attach to each chunk

        Returns:
            List of dictionaries, each containing 'text' and 'metadata' keys
        """
        if not text:
            return []

        metadata = metadata or {}
        chunks: List[Dict[str, Any]] = []

        # First split by paragraphs (double newlines)
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return []

        # Track document structure with heading hierarchy
        current_heading_stack: List[Dict[str, Any]] = []
        current_chunk: List[str] = []
        current_size = 0
        current_segment_types: Set[str] = set()

        for para_idx, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            para_size = len(paragraph)

            # Determine segment type and importance
            is_heading = self.is_heading(paragraph)
            is_code = self.is_code_block(paragraph)
            is_list = self.is_list_item(paragraph)
            is_table = self.is_table(paragraph)

            self.get_segment_importance(paragraph)

            # Update heading stack if this is a heading
            if is_heading:
                level, content = self.get_heading_level(paragraph)

                # Remove any headings of equal or greater level from the stack
                while current_heading_stack and cast(HeadingContext, current_heading_stack[-1])["level"] >= level:
                    current_heading_stack.pop()

                # Add this heading to the stack
                heading_context: Dict[str, Any] = {
                    "level": level,
                    "content": content,
                    "original": paragraph
                }
                current_heading_stack.append(heading_context)

                # If we have content in current_chunk, finalize it before the new heading
                # This ensures new sections start with their headings
                if current_chunk and current_size > 0:
                    chunk_text = "\n\n".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    # Exclude current heading and fix the index access
                    chunk_metadata["heading_context"] = [h["content"] for h in cast(List[HeadingContext], current_heading_stack[:-1])]
                    chunk_metadata["segment_types"] = list(current_segment_types)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })

                    # Reset for new section
                    current_chunk = []
                    current_size = 0
                    current_segment_types = set()

            # Special handling for code blocks, tables, and lists - try to keep them whole
            if is_code or is_table or is_list:
                segment_type = "code_block" if is_code else "table" if is_table else "list"

                # If adding this segment would exceed chunk size and we already have content
                if current_size + para_size + (2 if current_chunk else 0) > self.chunk_size and current_chunk:
                    # Finalize current chunk
                    chunk_text = "\n\n".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                    chunk_metadata["segment_types"] = list(current_segment_types)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })

                    # Start new chunk with this segment
                    current_chunk = [paragraph]
                    current_size = para_size
                    current_segment_types = {segment_type}
                    continue

                # If the segment itself exceeds chunk size, we need to split it
                if para_size > self.chunk_size:
                    # First add any existing content
                    if current_chunk:
                        chunk_text = "\n\n".join(current_chunk)
                        chunk_metadata = metadata.copy()
                        chunk_metadata["chunk_index"] = len(chunks)
                        chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                        chunk_metadata["segment_types"] = list(current_segment_types)
                        chunks.append({
                            "text": chunk_text,
                            "metadata": chunk_metadata
                        })

                    # For code blocks, try to split on newlines to preserve syntax
                    if is_code:
                        # Extract the code block content
                        match = self.code_block_pattern.search(paragraph)
                        if match:
                            lang_marker = paragraph[:paragraph.find('\n')]
                            code_content = match.group(1)
                            lines = code_content.split("\n")

                            current_block_lines: List[str] = []
                            current_block_size = len(lang_marker) + 4  # ```lang\n and \n```

                            for line in lines:
                                line_len = len(line) + 1  # +1 for newline
                                if current_block_size + line_len <= self.chunk_size or not current_block_lines:
                                    current_block_lines.append(line)
                                    current_block_size += line_len
                                else:
                                    # Create a properly formatted code block
                                    block_content = "\n".join(current_block_lines)
                                    block_text = f"{lang_marker}\n{block_content}\n```"

                                    chunk_metadata = metadata.copy()
                                    chunk_metadata["chunk_index"] = len(chunks)
                                    chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                                    chunk_metadata["segment_types"] = ["code_block_split"]
                                    chunk_metadata["is_continuation"] = current_block_lines != lines[:len(current_block_lines)]

                                    chunks.append({
                                        "text": block_text,
                                        "metadata": chunk_metadata
                                    })

                                    # Start new block with this line
                                    current_block_lines = [line]
                                    current_block_size = len(lang_marker) + line_len + 4

                            # Add final code block if any
                            if current_block_lines:
                                block_content = "\n".join(current_block_lines)
                                block_text = f"{lang_marker}\n{block_content}\n```"

                                chunk_metadata = metadata.copy()
                                chunk_metadata["chunk_index"] = len(chunks)
                                chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                                chunk_metadata["segment_types"] = ["code_block_split"]
                                chunk_metadata["is_continuation"] = current_block_lines != lines[:len(current_block_lines)]

                                chunks.append({
                                    "text": block_text,
                                    "metadata": chunk_metadata
                                })
                        else:
                            # Fallback if code block extraction fails
                            for i in range(0, para_size, self.chunk_size - self.chunk_overlap):
                                chunk_text = paragraph[i:i + self.chunk_size]
                                chunk_metadata = metadata.copy()
                                chunk_metadata["chunk_index"] = len(chunks)
                                chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                                chunk_metadata["segment_types"] = ["code_block_fallback"]
                                chunk_metadata["is_continuation"] = i > 0

                                chunks.append({
                                    "text": chunk_text,
                                    "metadata": chunk_metadata
                                })
                    elif is_table:
                        # For tables, try to keep rows together
                        rows = paragraph.split("\n")

                        current_table_rows: List[str] = []
                        current_table_size = 0

                        for row in rows:
                            row_len = len(row) + 1  # +1 for newline
                            if current_table_size + row_len <= self.chunk_size or not current_table_rows:
                                current_table_rows.append(row)
                                current_table_size += row_len
                            else:
                                # Add table chunk
                                table_text = "\n".join(current_table_rows)

                                chunk_metadata = metadata.copy()
                                chunk_metadata["chunk_index"] = len(chunks)
                                chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                                chunk_metadata["segment_types"] = ["table_split"]
                                chunk_metadata["is_continuation"] = current_table_rows != rows[:len(current_table_rows)]

                                chunks.append({
                                    "text": table_text,
                                    "metadata": chunk_metadata
                                })

                                # Start new table chunk with this row
                                current_table_rows = [row]
                                current_table_size = row_len

                        # Add final table chunk if any
                        if current_table_rows:
                            table_text = "\n".join(current_table_rows)

                            chunk_metadata = metadata.copy()
                            chunk_metadata["chunk_index"] = len(chunks)
                            chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                            chunk_metadata["segment_types"] = ["table_split"]
                            chunk_metadata["is_continuation"] = current_table_rows != rows[:len(current_table_rows)]

                            chunks.append({
                                "text": table_text,
                                "metadata": chunk_metadata
                            })
                    else:
                        # For other large content, split by lines first
                        lines = paragraph.split("\n")

                        current_lines: List[str] = []
                        current_lines_size = 0

                        for line in lines:
                            line_len = len(line) + 1  # +1 for newline
                            if current_lines_size + line_len <= self.chunk_size or not current_lines:
                                current_lines.append(line)
                                current_lines_size += line_len
                            else:
                                # Add lines chunk
                                lines_text = "\n".join(current_lines)

                                chunk_metadata = metadata.copy()
                                chunk_metadata["chunk_index"] = len(chunks)
                                chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                                chunk_metadata["segment_types"] = ["list_split"]
                                chunk_metadata["is_continuation"] = current_lines != lines[:len(current_lines)]

                                chunks.append({
                                    "text": lines_text,
                                    "metadata": chunk_metadata
                                })

                                # Start new chunk with this line
                                current_lines = [line]
                                current_lines_size = line_len

                        # Add final lines chunk if any
                        if current_lines:
                            lines_text = "\n".join(current_lines)

                            chunk_metadata = metadata.copy()
                            chunk_metadata["chunk_index"] = len(chunks)
                            chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                            chunk_metadata["segment_types"] = ["list_split"]
                            chunk_metadata["is_continuation"] = current_lines != lines[:len(current_lines)]

                            chunks.append({
                                "text": lines_text,
                                "metadata": chunk_metadata
                            })

                    # Reset for next paragraph
                    current_chunk = []
                    current_size = 0
                    current_segment_types = set()
                    continue
                else:
                    # Add this special content to current chunk if it fits
                    current_chunk.append(paragraph)
                    current_segment_types.add(segment_type)
                    current_size += para_size + (2 if current_chunk and len(current_chunk) > 1 else 0)
                    continue

            # For large regular paragraphs, split by sentences
            if para_size > self.chunk_size:
                # Add current chunk first if it exists
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                    chunk_metadata["segment_types"] = list(current_segment_types)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })
                    current_chunk = []
                    current_size = 0
                    current_segment_types = set()

                # Split large paragraph by sentences
                try:
                    sentences = nltk.sent_tokenize(paragraph)
                except LookupError:
                    # Fallback to simple tokenizer if NLTK data is not available
                    sentences = self.simple_sent_tokenize(paragraph)

                current_para = ""

                for sent_idx, sentence in enumerate(sentences):
                    sent_len = len(sentence)

                    # If this single sentence is too big, split it by words
                    if sent_len > self.chunk_size:
                        if current_para:
                            # First add any accumulated paragraph content
                            chunk_metadata = metadata.copy()
                            chunk_metadata["chunk_index"] = len(chunks)
                            chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                            chunk_metadata["segment_types"] = ["paragraph_split"]
                            chunks.append({
                                "text": current_para,
                                "metadata": chunk_metadata
                            })

                        # Split this long sentence by keeping full words
                        words = sentence.split()
                        current_sentence = ""

                        for word in words:
                            if len(current_sentence) + len(word) + 1 <= self.chunk_size or not current_sentence:
                                current_sentence += (" " + word if current_sentence else word)
                            else:
                                # Add sentence chunk
                                chunk_metadata = metadata.copy()
                                chunk_metadata["chunk_index"] = len(chunks)
                                chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                                chunk_metadata["segment_types"] = ["sentence_split"]
                                chunks.append({
                                    "text": current_sentence,
                                    "metadata": chunk_metadata
                                })

                                # Start new sentence chunk
                                current_sentence = word

                        # Add final sentence part if any
                        if current_sentence:
                            chunk_metadata = metadata.copy()
                            chunk_metadata["chunk_index"] = len(chunks)
                            chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                            chunk_metadata["segment_types"] = ["sentence_split"]
                            chunks.append({
                                "text": current_sentence,
                                "metadata": chunk_metadata
                            })

                        # Reset accumulator
                        current_para = ""
                    elif len(current_para) + sent_len + 1 <= self.chunk_size or not current_para:
                        # Add sentence to current paragraph
                        current_para += (" " + sentence if current_para else sentence)
                    else:
                        # Add completed paragraph chunk
                        chunk_metadata = metadata.copy()
                        chunk_metadata["chunk_index"] = len(chunks)
                        chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                        chunk_metadata["segment_types"] = ["paragraph_split"]
                        chunks.append({
                            "text": current_para,
                            "metadata": chunk_metadata
                        })

                        # Create overlap for next chunk with sentence transitions
                        words = current_para.split()
                        if len(words) > self.chunk_overlap:
                            overlap = " ".join(words[-self.chunk_overlap:])
                            current_para = overlap + " " + sentence if overlap else sentence
                        else:
                            current_para = sentence

                # Add the last paragraph portion if it exists
                if current_para:
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                    chunk_metadata["segment_types"] = ["paragraph_split"]
                    chunks.append({
                        "text": current_para,
                        "metadata": chunk_metadata
                    })

                # Continue to next paragraph
                continue

            # Normal case: add paragraph to current chunk if it fits
            if current_size + para_size + (2 if current_chunk else 0) <= self.chunk_size:
                current_chunk.append(paragraph)
                current_segment_types.add("paragraph" if not is_heading else f"heading_{self.get_heading_level(paragraph)[0]}")
                current_size += para_size + (2 if current_chunk and len(current_chunk) > 1 else 0)  # +2 for "\n\n"
            else:
                # Finalize current chunk and start a new one
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunk_metadata = metadata.copy()
                    chunk_metadata["chunk_index"] = len(chunks)
                    chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
                    chunk_metadata["segment_types"] = list(current_segment_types)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": chunk_metadata
                    })

                # Start a new chunk with this paragraph
                current_chunk = [paragraph]
                current_segment_types = {"paragraph" if not is_heading else f"heading_{self.get_heading_level(paragraph)[0]}"}
                current_size = para_size

        # Add the last chunk if not empty
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadata["heading_context"] = [h["content"] for h in current_heading_stack]
            chunk_metadata["segment_types"] = list(current_segment_types)
            chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })

        # Update total_chunks in metadata
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)

        logger.info(f"Created {len(chunks)} chunks using semantic chunking strategy")
        return chunks

    # Simple sentence tokenization as fallback
    def simple_sent_tokenize(self, text: str) -> List[str]:
        """Simple sentence tokenizer that splits on periods, exclamation marks, and question marks."""
        if not text:
            return []
        sentences = self.sentence_end_pattern.split(text)
        # Make sure we don't end up with empty sentences
        return [s.strip() for s in sentences if s.strip()]


class TextChunker:
    """
    Chunker that uses a specific chunking strategy to split text into chunks.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, separator: str = "\n", use_semantic_chunking: bool = False):
        """
        Initialize the text chunker.

        Args:
            chunk_size: Maximum size of each chunk
            chunk_overlap: Overlap between consecutive chunks
            separator: String to split text by before chunking (e.g., newline)
            use_semantic_chunking: Whether to use semantic chunking strategy
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

        if use_semantic_chunking:
            self.strategy: Union[SimpleChunkingStrategy, SemanticChunkingStrategy] = SemanticChunkingStrategy(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
        else:
            self.strategy = SimpleChunkingStrategy(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator=separator
            )

    def split_text(self, text: str, document_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks using the selected strategy.

        Args:
            text: The text to split
            document_id: The ID of the document
            metadata: Metadata to attach to each chunk

        Returns:
            List of dictionaries, each containing 'text' and 'metadata' keys
        """
        return self.strategy.split_text(text, document_id, metadata)


def get_chunker(chunk_size: int = 512, chunk_overlap: int = 50, use_semantic_chunking: bool = False) -> TextChunker:
    """
    Get a TextChunker instance with the specified parameters.

    Args:
        chunk_size: Maximum size of each chunk
        chunk_overlap: Overlap between consecutive chunks
        use_semantic_chunking: Whether to use semantic chunking

    Returns:
        TextChunker instance
    """
    return TextChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        use_semantic_chunking=use_semantic_chunking
    )
