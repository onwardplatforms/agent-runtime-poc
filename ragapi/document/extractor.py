from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import logging

logger = logging.getLogger("ragapi.extractor")


class FileExtractor(ABC):
    """Abstract base class for file text extractors."""
    
    @abstractmethod
    async def extract_text(self, file_path: Union[str, Path]) -> str:
        """
        Extract text from a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Extracted text
        """
        pass
    
    @abstractmethod
    async def get_metadata(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get metadata from a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File metadata
        """
        pass


class TextExtractor(FileExtractor):
    """Extractor for plain text files."""
    
    async def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract text from a plain text file."""
        file_path = Path(file_path)
        logger.info(f"Extracting text from {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with a different encoding
            logger.warning(f"Failed to read {file_path} with utf-8 encoding, trying latin-1")
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()
    
    async def get_metadata(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Get metadata from a plain text file."""
        file_path = Path(file_path)
        stats = file_path.stat()
        
        return {
            "filename": file_path.name,
            "file_size": stats.st_size,
            "mime_type": "text/plain",
            "last_modified": stats.st_mtime,
        }


# Lazy import function for extractors
def get_pdf_extractor():
    """Get the PDF extractor, importing it only when needed."""
    from .file_types.pdf import PDFExtractor
    return PDFExtractor()


# Registry of extractors by file extension
EXTRACTORS = {
    ".txt": TextExtractor(),
    ".md": TextExtractor(),
    # Lazy load PDF extractor to avoid immediate dependency requirement
    ".pdf": get_pdf_extractor,
}


async def get_extractor(file_path: Union[str, Path]) -> FileExtractor:
    """
    Get the appropriate extractor for a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        An extractor instance
    
    Raises:
        ValueError: If no extractor is available for the file type
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()
    
    if ext in EXTRACTORS:
        extractor = EXTRACTORS[ext]
        # Handle lazy-loaded extractors
        if callable(extractor) and not isinstance(extractor, FileExtractor):
            try:
                extractor = extractor()
                # Update the registry so we don't need to re-initialize
                EXTRACTORS[ext] = extractor
            except ImportError as e:
                logger.warning(f"Could not load extractor for {ext}: {str(e)}")
                logger.warning(f"Falling back to text extractor")
                return TextExtractor()
        return extractor
    
    # Default to text extractor
    logger.warning(f"No specific extractor for {ext}, using text extractor")
    return TextExtractor()


async def extract_document(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Extract text and metadata from a document.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary with text and metadata
    """
    file_path = Path(file_path)
    extractor = await get_extractor(file_path)
    
    try:
        text = await extractor.extract_text(file_path)
        metadata = await extractor.get_metadata(file_path)
        
        return {
            "text": text,
            "metadata": metadata,
        }
    except Exception as e:
        logger.error(f"Error extracting text from {file_path}: {str(e)}")
        raise
