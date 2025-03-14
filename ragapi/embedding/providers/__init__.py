from ..models import EmbeddingModel

# Import providers
from .local import SentenceTransformerEmbedding
# Only import OpenAI provider if we have the dependency
try:
    from .openai import OpenAIEmbedding
    _has_openai = True
except ImportError:
    _has_openai = False

__all__ = ['SentenceTransformerEmbedding']
if _has_openai:
    __all__.append('OpenAIEmbedding')
