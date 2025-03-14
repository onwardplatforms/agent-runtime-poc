from typing import Dict, Any, Union
from pathlib import Path
import logging

from ..extractor import FileExtractor

logger = logging.getLogger("ragapi.extractor.pdf")


class PDFExtractor(FileExtractor):
    """Extractor for PDF files."""
    
    async def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract text from a PDF file."""
        file_path = Path(file_path)
        logger.info(f"Extracting text from PDF: {file_path}")
        
        try:
            # Try to import PyPDF2
            from PyPDF2 import PdfReader
        except ImportError:
            logger.error("PyPDF2 not installed. Please install with 'pip install PyPDF2'")
            raise
            
        try:
            reader = PdfReader(file_path)
            
            # Extract text from each page
            text_parts = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
                    
            # Join all text with newlines
            full_text = "\n\n".join(text_parts)
            
            logger.info(f"Extracted {len(full_text)} characters from PDF with {len(reader.pages)} pages")
            return full_text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
            raise
    
    async def get_metadata(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Get metadata from a PDF file."""
        file_path = Path(file_path)
        
        try:
            # Try to import PyPDF2
            from PyPDF2 import PdfReader
        except ImportError:
            logger.error("PyPDF2 not installed. Please install with 'pip install PyPDF2'")
            raise
            
        try:
            reader = PdfReader(file_path)
            
            # Get basic file stats
            stats = file_path.stat()
            
            # Get PDF metadata
            metadata = {
                "filename": file_path.name,
                "file_size": stats.st_size,
                "mime_type": "application/pdf",
                "last_modified": stats.st_mtime,
                "page_count": len(reader.pages),
            }
            
            # Try to get document info
            if reader.metadata:
                pdf_info = reader.metadata
                # Add relevant metadata
                for key in ["title", "author", "creator", "producer", "subject"]:
                    if hasattr(pdf_info, key) and getattr(pdf_info, key):
                        metadata[key] = str(getattr(pdf_info, key))
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting metadata from PDF {file_path}: {str(e)}")
            # Return basic metadata if we can't extract PDF-specific info
            return {
                "filename": file_path.name,
                "file_size": file_path.stat().st_size,
                "mime_type": "application/pdf",
                "last_modified": file_path.stat().st_mtime,
            }
