# Import local provider by default
from .local import SentenceTransformerEmbedding

# Define the default exports
__all__ = ['SentenceTransformerEmbedding']

# Conditionally import and export OpenAI provider
try:
    # Only import and expose if available
    from .openai import OpenAIEmbedding  # noqa: F401
    __all__.append('OpenAIEmbedding')
except ImportError:
    pass
