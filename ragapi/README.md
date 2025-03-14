# RAG API Service

This service provides a RESTful API for Retrieval-Augmented Generation (RAG) functionality. It allows you to:

1. Upload documents for processing and embedding
2. Query for relevant document chunks based on semantic similarity
3. Delete documents when they're no longer needed

## Configuration

The service can be configured using environment variables or a `.env` file. Copy the `.env.example` file to `.env` and modify the settings as needed.

### Embedding Providers

The RAG API supports multiple embedding providers that you can configure:

#### Local (SentenceTransformers)

This is the default provider that uses the SentenceTransformers library to generate embeddings locally.

```
RAG_EMBEDDING_PROVIDER=local
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

You can use any model from the [SentenceTransformers model hub](https://huggingface.co/sentence-transformers).

#### OpenAI

To use OpenAI's embeddings API, set the following in your `.env` file:

```
RAG_EMBEDDING_PROVIDER=openai
RAG_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-your-api-key-here
```

Available OpenAI embedding models:
- `text-embedding-3-small` (default, recommended)
- `text-embedding-3-large` (higher quality but more expensive)
- `text-embedding-ada-002` (legacy model)

## API Endpoints

### Documents

- `POST /rag/documents`: Upload a document for processing
- `GET /rag/documents/{document_id}`: Get document status
- `DELETE /rag/documents/{document_id}`: Delete a document and its embeddings

### Query

- `POST /rag/query`: Query for relevant document chunks

## Usage with the UI

The UI components in this project have been integrated with the RAG API for document upload and deletion functionality. When files are uploaded through the UI, they are automatically sent to both the regular file storage API and the RAG API for processing.

## Extending the Service

### Adding New Embedding Providers

To add a new embedding provider:

1. Create a new file in `ragapi/embedding/providers/` (e.g., `my_provider.py`)
2. Implement a class that extends the `EmbeddingModel` abstract base class
3. Update the `get_embedding_model` function in `ragapi/embedding/models.py` to support your provider
4. Update the configuration in `ragapi/config.py` to include settings for your provider 