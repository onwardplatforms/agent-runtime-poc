import os
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for the RAG API service."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 5003  # Updated to 5003 to match the new port scheme
    debug: bool = False

    # Storage paths
    documents_path: str = "./.data/documents"
    embeddings_path: str = "./.data/embeddings"

    # Embedding settings
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"  # For local provider
    embedding_dimension: int = 384  # Based on the model

    # OpenAI settings (used when embedding_provider is "openai")
    openai_embedding_model: str = "text-embedding-3-small"

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: int = 50
    use_semantic_chunking: bool = True  # Enable semantic chunking by default

    # Processing settings
    embedding_batch_size: int = 10  # Number of chunks to process in one batch
    processing_timeout: int = 300  # Timeout for document processing in seconds

    # Storage settings
    max_documents_per_conversation: int = 1000  # Maximum number of documents per conversation

    # Similarity search settings
    default_top_k: int = 5

    # Model performance settings
    use_gpu: bool = True  # Whether to use GPU for embedding generation if available

    # Configuration for environment variables
    class Config:
        env_prefix = "RAG_"
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env file


# Create a singleton instance
settings = Settings()

# Set environment variables from settings for easier access in other modules
os.environ["RAG_EMBEDDING_PROVIDER"] = settings.embedding_provider
os.environ["RAG_OPENAI_EMBEDDING_MODEL"] = settings.openai_embedding_model
