import os
import pytest
import pytest_asyncio
import tempfile
import uuid
import shutil
from pathlib import Path

from ragapi.storage.providers.filesystem import FilesystemStorage
from ragapi.embedding.models import get_embedding_model
from ragapi.document.chunker import get_chunker
from ragapi.document.extractor import extract_document
from ragapi.storage.base import Chunk


@pytest_asyncio.fixture
async def temp_storage_dir():
    """Create a temporary directory for test storage."""
    temp_dir = tempfile.mkdtemp(prefix="ragapi_test_")
    try:
        yield temp_dir
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def storage(temp_storage_dir):
    """Set up a filesystem storage instance for testing."""
    storage = FilesystemStorage(base_dir=temp_storage_dir)
    await storage.initialize()
    return storage


@pytest_asyncio.fixture
async def embedding_model():
    """Get the configured embedding model."""
    # Force local provider for tests
    os.environ["RAG_EMBEDDING_PROVIDER"] = "local"
    os.environ["RAG_EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
    
    model = get_embedding_model()
    await model.initialize()
    
    return model


@pytest.fixture
def test_document():
    """Create a temporary test document."""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
        content = """
        This is a test document for the RAG API.
        It contains multiple sentences to test chunking.
        The RAG API should be able to find relevant chunks based on semantic similarity.
        We need to test both local and OpenAI embedding providers.
        """
        tmp.write(content.encode('utf-8'))
        tmp.flush()
        
        try:
            yield tmp.name
        finally:
            # Clean up
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


@pytest.mark.asyncio
async def test_document_processing_pipeline(test_document, storage, embedding_model):
    """Test the complete document processing pipeline with the local embedding provider."""
    # 1. Extract text from document
    doc_data = await extract_document(test_document)
    assert "text" in doc_data
    assert "metadata" in doc_data
    assert len(doc_data["text"]) > 0
    
    # 2. Create chunker and split text
    chunker = get_chunker(chunk_size=100, chunk_overlap=20)
    document_id = str(uuid.uuid4())
    chunks_data = chunker.split_text(doc_data["text"], document_id=document_id, metadata=doc_data["metadata"])
    
    assert len(chunks_data) > 0
    
    # 3. Generate embeddings for chunks
    chunk_objects = []
    for chunk_data in chunks_data:
        text = chunk_data["text"]
        metadata = chunk_data["metadata"]
        
        # Generate embedding
        embeddings = await embedding_model.get_embeddings([text])
        embedding = embeddings[0]
        
        # Create Chunk object
        chunk = Chunk(
            text=text,
            embedding=embedding,
            metadata=metadata,
            document_id=document_id
        )
        
        chunk_objects.append(chunk)
    
    # 4. Store chunks in storage
    conversation_id = "test-conversation"
    chunk_ids = await storage.add_chunks(chunk_objects, conversation_id=conversation_id)
    
    assert len(chunk_ids) == len(chunk_objects)
    
    # 5. Retrieve a chunk to verify storage
    for chunk_id in chunk_ids:
        retrieved_chunk = await storage.get_chunk(chunk_id, conversation_id=conversation_id)
        assert retrieved_chunk is not None
        assert retrieved_chunk.document_id == document_id
        assert retrieved_chunk.text is not None
        assert retrieved_chunk.embedding is not None
    
    # 6. Test semantic search
    query_text = "test semantic similarity with embeddings"
    query_embedding = (await embedding_model.get_embeddings([query_text]))[0]
    
    search_results = await storage.search_chunks(
        query_embedding,
        top_k=2,
        conversation_id=conversation_id
    )
    
    assert len(search_results) > 0
    # The chunk mentioning "semantic similarity" should be in results
    semantic_chunk_found = any("semantic similarity" in chunk.text.lower() for chunk in search_results)
    assert semantic_chunk_found
    
    # 7. Test document deletion
    deleted_count = await storage.delete_document(document_id, conversation_id=conversation_id)
    assert deleted_count > 0
    
    # Verify document is gone
    for chunk_id in chunk_ids:
        retrieved_chunk = await storage.get_chunk(chunk_id, conversation_id=conversation_id)
        assert retrieved_chunk is None


@pytest.mark.asyncio
async def test_multiple_documents(storage, embedding_model):
    """Test storing and retrieving multiple documents."""
    # Create two test documents
    doc1_id = str(uuid.uuid4())
    doc1_chunks = [
        Chunk(
            text="Machine learning is an approach to artificial intelligence.",
            embedding=(await embedding_model.get_embeddings(["Machine learning is an approach to artificial intelligence."]))[0],
            metadata={"source": "doc1", "page": 1},
            document_id=doc1_id
        ),
        Chunk(
            text="Neural networks are a popular machine learning technique.",
            embedding=(await embedding_model.get_embeddings(["Neural networks are a popular machine learning technique."]))[0],
            metadata={"source": "doc1", "page": 2},
            document_id=doc1_id
        )
    ]
    
    doc2_id = str(uuid.uuid4())
    doc2_chunks = [
        Chunk(
            text="Vector databases store embeddings for semantic search.",
            embedding=(await embedding_model.get_embeddings(["Vector databases store embeddings for semantic search."]))[0],
            metadata={"source": "doc2", "page": 1},
            document_id=doc2_id
        ),
        Chunk(
            text="Retrieval-augmented generation enhances LLM responses with relevant documents.",
            embedding=(await embedding_model.get_embeddings(["Retrieval-augmented generation enhances LLM responses with relevant documents."]))[0],
            metadata={"source": "doc2", "page": 2},
            document_id=doc2_id
        )
    ]
    
    # Store both documents
    conversation_id = "multi-doc-test"
    await storage.add_chunks(doc1_chunks, conversation_id=conversation_id)
    await storage.add_chunks(doc2_chunks, conversation_id=conversation_id)
    
    # Test retrieval by document filters
    query_embedding = (await embedding_model.get_embeddings(["machine learning neural networks"]))[0]
    
    # Search only doc1
    results_doc1 = await storage.search_chunks(
        query_embedding,
        top_k=2,
        conversation_id=conversation_id,
        filters={"document_id": doc1_id}
    )
    
    assert len(results_doc1) > 0
    assert all(chunk.document_id == doc1_id for chunk in results_doc1)
    
    # Search only doc2
    results_doc2 = await storage.search_chunks(
        query_embedding,
        top_k=2,
        conversation_id=conversation_id,
        filters={"document_id": doc2_id}
    )
    
    assert len(results_doc2) > 0
    assert all(chunk.document_id == doc2_id for chunk in results_doc2)
    
    # List all documents
    documents = await storage.list_documents(conversation_id=conversation_id)
    assert len(documents) == 2
    doc_ids = {doc["document_id"] for doc in documents}
    assert doc1_id in doc_ids
    assert doc2_id in doc_ids 